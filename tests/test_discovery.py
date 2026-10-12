import asyncio
import json
import time
import pytest
from fastapi.testclient import TestClient
from app import core, discovery
from app.main import app

def test_freshness_and_date_provenance():
    now=time.time()
    cfg=dict(days=7,topics='AI,工具',content_type='all')
    original=dict(title='New AI tool',text='AI tool. '*500)
    assert discovery.score(dict(published=now-86400,priority=20),original,cfg,now)[0]>=55
    assert discovery.score(dict(published=now-86400*8),original,cfg,now)[0]==0
    assert discovery.score(dict(published=None),original,cfg,now)[0]==0
    assert discovery.score(dict(published=now+86400),original,cfg,now)[0]==0
    stamp,label=discovery.publication('<script type="application/ld+json">{"datePublished":"2026-10-09T12:00:00Z"}</script>')
    assert stamp and label=='结构化发布日期'

def test_reject_unrelated_and_incomplete():
    cfg=dict(days=7,topics='AI',content_type='all')
    candidate=dict(published=time.time())
    assert discovery.score(candidate,dict(title='Sports',text='football '*500),cfg)[0]==0
    assert discovery.score(candidate,dict(title='AI',text='tiny'),cfg)[0]==0

def test_dedup_and_tracking_parameters():
    assert discovery.canonical('https://example.com/a/?utm_source=mail&id=4#x')=='https://example.com/a?id=4'
    assert discovery.near_duplicate('OpenAI launches a new model!',['OpenAI launches a new model'])
    assert not discovery.near_duplicate('AI tools for images',['Industry funding announcement'])

def test_chinese_priority_and_foreign_fallback():
    assert discovery.is_chinese('OpenAI 发布全新人工智能模型，支持中文。')
    assert not discovery.is_chinese('OpenAI launches a new AI model')
    candidates=[dict(title='人工智能工具新发布'+str(i),source='中文来源') for i in range(10)]
    candidates+=[dict(title='New AI tool '+str(i),source='English') for i in range(5)]
    ordered=discovery.reading_order(candidates,5)
    assert len(ordered)==5
    assert sum(discovery.is_chinese(c['title']) for c in ordered)==4
    assert len(discovery.reading_order(candidates[:2],5))==2
    ranked=discovery.selection_order([dict(language='other',score=99),dict(language='zh',score=60)])
    assert ranked[0]['language']=='zh'

def test_discovery_only_does_not_call_model(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    core.init()
    def discover(jid,cfg):
        discovery.persist(jid,[dict(url='https://example.com/a',status='selected')])
        return [(dict(url='https://example.com/a'),dict(title='AI',text='full text'),'https://example.com/a')]
    monkeypatch.setattr(discovery,'run',discover)
    async def public(url): return url
    monkeypatch.setattr(core,'public_url',public)
    async def forbidden(*args):raise AssertionError('must not generate')
    monkeypatch.setattr(core,'generate',forbidden)
    cfg=dict(mode='discover',urls=[],discover_only=True,limit=2)
    with core.db() as c:
        jid=c.execute('INSERT INTO jobs(name,config) VALUES(?,?)',('test',json.dumps(cfg))).lastrowid
    asyncio.run(core.run_job(jid))
    with core.db() as c:
        assert c.execute('SELECT status FROM jobs').fetchone()[0]=='completed'
        assert c.execute('SELECT COUNT(*) FROM articles').fetchone()[0]==1
        article=c.execute('SELECT * FROM articles').fetchone()
        assert article['status']=='collected'
        assert json.loads(article['original'])['text']=='full text'
        assert json.loads(c.execute('SELECT value FROM discoveries').fetchone()[0])[0]['status']=='selected'

def test_automatic_default_and_manual_validation(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    async def no_work(*args):pass
    monkeypatch.setattr(core,'run_job',no_work)
    with TestClient(app) as client:
        assert client.post('/api/jobs',json={'discover_only':True}).status_code==200
        assert client.post('/api/jobs',json={}).status_code==200
        assert client.post('/api/jobs',json={'mode':'articles','urls':[]}).status_code==400
        assert client.post('/api/jobs',json={'discover_only':True,'sources':['https://unknown.example']}).status_code==400
        assert client.post('/api/jobs',json={'days':90}).status_code==422
