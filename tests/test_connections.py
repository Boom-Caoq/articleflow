import asyncio
import json
import pytest
from fastapi.testclient import TestClient
from app import core,connections,skill_runtime
from app.main import app

@pytest.fixture
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    core.init()

def test_success_saves_only_tested_group(isolated,monkeypatch):
    async def probe(group,s):
        assert s['api_key']=='new-secret'
        return '连接成功'
    monkeypatch.setattr(connections,'probe',probe)
    with TestClient(app) as client:
        r=client.post('/api/connections/siliconflow/test',json={'api_key':'new-secret','wp_user':'not-tested'}).json()
        assert r['ok']
        saved=client.get('/api/settings').json()
        assert saved['api_key']=='' and saved['api_key_configured']
        assert saved['wp_user']==''
        assert saved['connection_checks']['siliconflow']['ok']

def test_failure_does_not_overwrite_valid_credentials(isolated,monkeypatch):
    core.save_settings({'api_key':'old-secret'})
    async def probe(*args): raise ValueError('检测失败')
    monkeypatch.setattr(connections,'probe',probe)
    result=asyncio.run(connections.verify('siliconflow',{'api_key':'bad-secret'}))
    assert not result['ok']
    assert core.settings()['api_key']=='old-secret'
    assert 'bad-secret' not in json.dumps(result)

def test_blank_password_uses_saved_secret(isolated,monkeypatch):
    core.save_settings({'wp_password':'previous'})
    async def probe(group,s):
        assert s['wp_password']=='previous'
        return '连接成功'
    monkeypatch.setattr(connections,'probe',probe)
    assert asyncio.run(connections.verify('wordpress',{'wp_password':''}))['ok']

def test_cannot_bypass_detection(isolated):
    with TestClient(app) as client:
        assert client.put('/api/settings',json={'api_key':'unverified'}).status_code==400
        assert client.put('/api/settings',json={'auto_sync':True,'wp_status':'draft'}).status_code==200
    assert core.settings()['api_key']==''

def test_real_installed_npm_cli():
    report=skill_runtime.validate('首先，我们需要理解这个问题。其次，我会检查数据。最后，我们再决定怎么做。')
    assert report['engine']['installed']
    assert report['engine']['engine']=='npm CLI'
    assert report['checks']['ban_list']['found']
    assert report['summary']['passed'] is False
