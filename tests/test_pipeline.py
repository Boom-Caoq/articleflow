import asyncio
import json
import pytest
from app import core,pipeline,discovery

@pytest.fixture
def saved(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    core.init()
    with core.db() as c:
        jid=c.execute('INSERT INTO jobs(name,config) VALUES(?,?)',('任务','{}')).lastrowid
    original={'title':'AI 原文','text':'必须保留的原文。'*100,'images':['https://example.com/a.jpg']}
    aid=pipeline.save_source(jid,'https://example.com/article',original,{'seo':['AI'],'geo':[]})
    return aid

def test_missing_key_keeps_original(saved,monkeypatch):
    async def forbidden(*args):raise AssertionError('must not generate')
    monkeypatch.setattr(core,'generate',forbidden)
    assert asyncio.run(pipeline.advance(saved,sync_after=True))['status']=='collected'
    with core.db() as c:
        row=c.execute('SELECT * FROM articles WHERE id=?',(saved,)).fetchone()
        assert '必须保留' in json.loads(row['original'])['text']
        assert 'API Key' in row['error']
    with pytest.raises(ValueError,match='改写'):
        asyncio.run(core.sync_article(saved))

def test_rewrite_failure_preserves_and_retry_updates_same_article(saved,monkeypatch):
    core.save_settings({'api_key':'test-key'})
    async def fail(*args):raise ValueError('质检未通过')
    monkeypatch.setattr(core,'generate',fail)
    assert asyncio.run(pipeline.advance(saved))['status']=='rewrite_failed'
    async def generate(*args):
        return dict(title='AI 成稿',content_html='<p>AI 完整成稿</p>',excerpt='摘要',tags=['AI'],categories=['技术']),dict(verdict='pass')
    async def media(*args):return []
    monkeypatch.setattr(core,'generate',generate)
    monkeypatch.setattr(core,'media_files',media)
    result=asyncio.run(pipeline.advance(saved,sync_after=True))
    assert result['status']=='ready'
    with core.db() as c:
        row=c.execute('SELECT * FROM articles').fetchone()
        assert row['id']==saved and row['title']=='AI 成稿'
        assert json.loads(row['original'])['images']==['https://example.com/a.jpg']
        assert 'WordPress' in row['error']
        assert c.execute('SELECT COUNT(*) FROM articles').fetchone()[0]==1
    # Resuming ready content must not rewrite or charge the model again.
    monkeypatch.setattr(core,'generate',fail)
    core.save_settings({'wp_url':'https://example.com','wp_user':'test','wp_password':'test'})
    async def sync(aid):pipeline.mark(aid,'synced','已同步')
    monkeypatch.setattr(core,'sync_article',sync)
    assert asyncio.run(pipeline.advance(saved,sync_after=True))['status']=='synced'

def test_legacy_selections_are_backfilled_idempotently(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path);core.init()
    with core.db() as c:
        jid=c.execute('INSERT INTO jobs(name,config) VALUES(?,?)',('旧任务','{}')).lastrowid
        c.execute('INSERT INTO discoveries VALUES(?,?)',(jid,json.dumps([{'status':'selected','url':'https://example.com/a','title':'旧入选'}])))
    core.init();core.init()
    with core.db() as c:
        rows=c.execute('SELECT * FROM articles').fetchall()
        assert len(rows)==1 and rows[0]['stage']=='待补采原文'
        aid=rows[0]['id']
    monkeypatch.setattr(discovery,'read_article',lambda url:dict(title='原文',text='补采正文',images=[]))
    assert asyncio.run(pipeline.advance(aid,capture_only=True))['status']=='collected'
    with core.db() as c:
        assert json.loads(c.execute('SELECT original FROM articles').fetchone()[0])['text']=='补采正文'

def test_saved_draft_survives_media_failure_without_regeneration(saved,monkeypatch):
    core.save_settings({'api_key':'test'})
    calls=[]
    async def generate(*args):
        calls.append(1)
        return dict(title='成稿',content_html='<p>正文</p>',excerpt='摘要',tags=[],categories=[]),dict(verdict='pass')
    async def fail_media(*args):raise ValueError('配图暂不可用')
    monkeypatch.setattr(core,'generate',generate)
    monkeypatch.setattr(core,'media_files',fail_media)
    assert asyncio.run(pipeline.advance(saved))['status']=='rewrite_failed'
    with core.db() as c:
        assert json.loads(c.execute('SELECT draft FROM articles').fetchone()[0])['article']['title']=='成稿'
    async def media(*args):return []
    monkeypatch.setattr(core,'media_files',media)
    assert asyncio.run(pipeline.advance(saved))['status']=='ready'
    assert len(calls)==1

def test_process_rejects_missing_key_before_enqueue(saved):
    from fastapi.testclient import TestClient
    from app.main import app,pending_articles
    with TestClient(app) as client:
        response=client.post(f'/api/articles/{saved}/process',json={'action':'rewrite'})
        assert response.status_code==400
        assert '尚未开始改写' in response.json()['detail']
        assert saved not in pending_articles
        article=client.get(f'/api/articles/{saved}').json()
        assert article['status']=='collected'
        assert article['stage']!='已加入处理队列'
        assert article['original']['text']
