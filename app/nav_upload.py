"""Pinned-host SFTP image transfer; secrets stay in encrypted local settings."""
import base64
import hashlib
import socket
import stat
import uuid
from contextlib import contextmanager
from urllib.parse import urlsplit

import httpx
import paramiko
from . import core


class HostKeyRequired(ValueError):
    def __init__(self, fingerprint):
        self.fingerprint = fingerprint
        super().__init__('请核对服务器 SSH 指纹后确认，再检测上传权限')


def config(values=None):
    value = core.settings().get('navigation_upload', {}).copy()
    for k, v in (values or {}).items():
        if k not in ('host', 'port', 'username', 'password', 'root', 'public_url', 'fingerprint'):
            continue
        if k == 'password' and not v:
            continue
        if k == 'port':
            try:
                v = int(v)
            except (ValueError, TypeError):
                raise ValueError('SFTP 端口无效') from None
            if not 1 <= v <= 65535:
                raise ValueError('SFTP 端口无效')
        elif not isinstance(v, str) or len(v) > 2000:
            raise ValueError('上传配置格式错误')
        value[k] = v.strip() if isinstance(v, str) and k != 'password' else v
    if not all(value.get(k) for k in ('host', 'username', 'password', 'root', 'public_url')):
        raise ValueError('请完整填写 SFTP 主机、用户名、密码、上传目录和公开 URL')
    root = value['root']
    if not root.startswith('/') or '..' in root.split('/') or '\\' in root or root == '/':
        raise ValueError('SFTP 上传目录必须是服务器绝对路径，例如 /var/www/example.com/wp-content/uploads')
    p = urlsplit(value['public_url'])
    if p.scheme != 'https' or not p.hostname or p.query or p.fragment or p.username:
        raise ValueError('图片公开地址需为不带参数的 HTTPS 目录')
    return value


@contextmanager
def session(value):
    sock = socket.create_connection((value['host'], int(value.get('port') or 22)), timeout=20)
    transport = paramiko.Transport(sock)
    try:
        transport.start_client(timeout=20)
        fingerprint = 'SHA256:' + base64.b64encode(hashlib.sha256(transport.get_remote_server_key().asbytes()).digest()).decode().rstrip('=')
        if not value.get('fingerprint'):
            raise HostKeyRequired(fingerprint)
        if value['fingerprint'] != fingerprint:
            raise ValueError('SSH 主机指纹与保存值不一致，已停止连接；请核实服务器身份')
        transport.auth_password(value['username'], value['password'])
        with paramiko.SFTPClient.from_transport(transport) as client:
            client.get_channel().settimeout(30)
            if not stat.S_ISDIR(client.stat(value['root']).st_mode):
                raise ValueError('上传目录不存在')
            yield client
    finally:
        transport.close()
        sock.close()


def check(value):
    token = uuid.uuid4().hex
    name = 'articleflow-check-' + token + '.txt'
    with session(value) as client:
        remote = value['root'].rstrip('/') + '/' + name
        try:
            with client.open(remote, 'wb') as fp:
                fp.write(token.encode())
            from .discovery import public_url_sync
            url = value['public_url'].rstrip('/') + '/' + name
            public_url_sync(url)
            with httpx.Client(timeout=20, trust_env=False) as web:
                response = web.get(url)
                if response.status_code != 200 or response.text.strip() != token:
                    raise ValueError('SFTP 可写，但公开 URL 与上传目录不对应，请检查路径')
        finally:
            try:
                client.remove(remote)
            except OSError:
                pass
    return 'SFTP 上传与公开图片目录检测通过'


def upload(paths):
    value = config()
    result = {}
    with session(value) as client:
        for kind, path in paths.items():
            name = 'articleflow-' + hashlib.sha256(path.read_bytes()).hexdigest() + path.suffix
            remote = value['root'].rstrip('/') + '/' + name
            try:
                present = client.stat(remote).st_size == path.stat().st_size
            except FileNotFoundError:
                present = False
            if not present:
                temp = remote + '.' + uuid.uuid4().hex + '.tmp'
                try:
                    client.put(str(path), temp)
                    client.rename(temp, remote)
                finally:
                    try:
                        client.remove(temp)
                    except OSError:
                        pass
            result[kind] = value['public_url'].rstrip('/') + '/' + name
    return result
