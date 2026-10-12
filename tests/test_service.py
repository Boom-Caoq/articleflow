import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app import core
from app.main import app

@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    (tmp_path/'media').mkdir()
    core.init()
    return tmp_path

def test_secret_not_returned_or_stored_as_plaintext(isolated):
    with TestClient(app) as client:
        core.save_settings({'api_key':'test-private-secret','wp_password':'private-wp'})
        s=client.get('/api/settings').json()
        assert s['api_key']=='' and s['api_key_configured']
        assert s['wp_password']=='' and s['wp_password_configured']
        client.put('/api/settings',json={'api_key':''})
        assert core.settings()['api_key']=='test-private-secret'
    assert b'test-private-secret' not in (isolated/'app.db').read_bytes()

def test_blocks_local_targets_and_cross_origin(isolated):
    with pytest.raises(ValueError):
        asyncio.run(core.public_url('http://127.0.0.1/test'))
    with pytest.raises(ValueError):
        asyncio.run(core.public_url('file:///etc/passwd'))
    with TestClient(app) as client:
        assert client.put('/api/settings',headers={'Origin':'https://attacker.example'},json={}).status_code==403
        assert client.get('/',headers={'Host':'attacker.example'}).status_code==403

def test_sanitization():
    value=core.clean('<p onclick="evil()">正文<a href="javascript:evil()">链接</a><img src=x onerror=evil()><script>evil()</script></p>')
    assert 'onclick' not in value and 'javascript:' not in value and '<script' not in value and '<img' not in value

def test_missing_configuration_and_missing_record(isolated):
    with TestClient(app) as client:
        assert client.post('/api/jobs',json={'mode':'articles','urls':[]}).status_code==400
        assert client.get('/api/articles/999').status_code==404
        assert client.post('/api/jobs/999/retry').status_code==404

def test_pipeline_persists_article_and_deduplicates(isolated,monkeypatch):
    core.save_settings({'api_key':'test-key'})
    async def public(url): return url
    async def crawl(url): return '<html></html>',url
    async def generate(jid,original,cfg,progress=None):
        return dict(title='测试文章',content_html='<p>Python 自动化内容</p>',excerpt='摘要',tags=['Python'],categories=['技术']),dict(verdict='pass',content_preserved=True)
    async def media(original,url): return [dict(path='/media/cover.jpg',generated=True,alt='封面',original='')]
    async def sleep(*args): pass
    monkeypatch.setattr(core,'public_url',public)
    monkeypatch.setattr(core,'crawl',crawl)
    monkeypatch.setattr(core,'extract',lambda *args:dict(title='原文',text='正文',images=[]))
    monkeypatch.setattr(core,'generate',generate)
    monkeypatch.setattr(core,'media_files',media)
    monkeypatch.setattr(core.asyncio,'sleep',sleep)
    with core.db() as c:
        jid=c.execute('INSERT INTO jobs(name,config,created) VALUES(?,?,0)',('任务',json.dumps(dict(urls=['https://example.com/a'],mode='articles',selector='',limit=5,seo=['Python'],geo=[])))).lastrowid
    asyncio.run(core.run_job(jid))
    asyncio.run(core.run_job(jid))
    with core.db() as c:
        assert c.execute('SELECT COUNT(*) FROM articles').fetchone()[0]==1
        row=c.execute('SELECT * FROM articles').fetchone()
        assert json.loads(row['keywords'])==[dict(word='Python',count=1)]
        assert c.execute('SELECT status FROM jobs').fetchone()[0]=='completed'

def test_quality_gate_refuses_failed_article(isolated,monkeypatch):
    async def llm(system,payload):
        if '检查原文与成稿' in system:
            return dict(verdict='revise',content_preserved=False,improvements=['遗漏事实'])
        return dict(title='测试',content_html='<p>正文</p>',excerpt='摘要',tags=[],categories=[])
    monkeypatch.setattr(core,'llm',llm)
    monkeypatch.setattr(core,'update_job',lambda *args,**kwargs:None)
    with pytest.raises(ValueError,match='质检'):
        asyncio.run(core.generate(1,dict(title='原文',text='完整事实'),dict(seo=[],geo=[])))

def test_restart_marks_interrupted(isolated):
    with core.db() as c:
        c.execute("INSERT INTO jobs(name,config,status) VALUES('x','{}','running')")
    core.init()
    with core.db() as c:
        assert c.execute('SELECT status FROM jobs').fetchone()[0]=='interrupted'

@pytest.mark.parametrize('route',['pretty','query'])
def test_wordpress_sync_and_idempotency(isolated,monkeypatch,route):
    core.save_settings(dict(wp_url='https://example.com',wp_user='writer',wp_password='test',wp_route=route))
    (isolated/'media'/'cover.jpg').write_bytes(b'jpeg-placeholder')
    with core.db() as c:
        aid=c.execute('INSERT INTO articles(source,title,content,excerpt,tags,categories,images) VALUES(?,?,?,?,?,?,?)',('https://source.example/a','文章','<p>正文</p><img src="/media/cover.jpg">','摘要','["标签"]','["分类"]',json.dumps([dict(path='/media/cover.jpg',alt='封面')]))).lastrowid
    async def public(url): return url
    monkeypatch.setattr(core,'public_url',public)
    calls=[]
    class Response:
        is_error=False
        def __init__(self,data): self.data=data
        def json(self): return self.data
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def request(self,method,url,**kwargs):
            calls.append((method,url,kwargs))
            if route=='query':
                assert url=='https://example.com/'
                url=kwargs['params']['rest_route']
            if method=='GET': return Response([])
            if url.endswith('/posts'):
                assert kwargs['json']['status']=='draft'
                assert kwargs['json']['featured_media']==10
                assert '/media/cover.jpg' not in kwargs['json']['content']
                assert kwargs['json']['tags']==[10] and kwargs['json']['categories']==[10]
                return Response(dict(id=99,link='https://example.com/article'))
            return Response(dict(id=10,source_url='https://example.com/uploads/cover.jpg'))
    monkeypatch.setattr(core.httpx,'AsyncClient',Client)
    asyncio.run(core.sync_article(aid))
    count=len(calls)
    asyncio.run(core.sync_article(aid))
    assert len(calls)==count
    with core.db() as c:
        a=c.execute('SELECT * FROM articles').fetchone()
        assert a['wp_id']==99 and a['status']=='synced'

def test_wordpress_recovers_remote_created_post(isolated,monkeypatch):
    core.save_settings(dict(wp_url='https://example.com',wp_user='writer',wp_password='test'))
    with core.db() as c:
        aid=c.execute("INSERT INTO articles(source,title,status) VALUES('https://source.example/a','文章','sync_failed')").lastrowid
    async def public(url): return url
    monkeypatch.setattr(core,'public_url',public)
    class Client:
        def __init__(self,**kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): pass
        async def request(self,method,url,**kwargs):
            assert method=='GET' and url.endswith('/posts')
            class Response:
                is_error=False
                def json(self): return [dict(id=123,link='https://example.com/existing')]
            return Response()
    monkeypatch.setattr(core.httpx,'AsyncClient',Client)
    result=asyncio.run(core.sync_article(aid))
    assert result['id']==123
