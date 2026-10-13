import asyncio
import json
import pytest
from app import core, pipeline, navigation

@pytest.fixture
def local(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    (tmp_path/'media').mkdir()
    core.init();navigation.init()
    core.save_settings({'wp_url':'https://example.com','wp_user':'test','wp_password':'test'})
    return tmp_path

def article(status='ready',report=None):
    with core.db() as c:
        return c.execute("INSERT INTO articles(source,title,status,pipeline_config,report) VALUES(?,?,?,?,?)",('https://example.org/article','test',status,json.dumps({'automated_publish':True}),json.dumps(report or {}))).lastrowid

def test_automation_overrides_capture_only_and_sync_disabled(local,monkeypatch):
    aid=article(report={'verdict':'pass','content_preserved':True})
    calls=[]
    async def sync(value):calls.append(value);return {'status':'publish'}
    monkeypatch.setattr(core,'sync_article',sync)
    result=asyncio.run(pipeline.advance(aid,sync_after=False,capture_only=True))
    assert result['status']=='synced' and calls==[aid]

def test_failed_quality_never_calls_wordpress(local,monkeypatch):
    aid=article(report={'verdict':'revise','content_preserved':False})
    async def public(url):return url
    monkeypatch.setattr(core,'public_url',public)
    def forbidden(*args,**kwargs):raise AssertionError('No WordPress request is allowed')
    monkeypatch.setattr(core.httpx,'AsyncClient',forbidden)
    with pytest.raises(ValueError,match='质检'):
        asyncio.run(core.sync_article(aid))

def test_unprocessed_navigation_never_uploads(local,monkeypatch):
    aid=navigation.add('https://example.com/tool')
    tid=navigation.enqueue('generate',{'ids':[aid]})
    def forbidden(*args,**kwargs):raise AssertionError('Must not upload unprocessed data')
    monkeypatch.setattr(navigation.nav_upload,'upload',forbidden)
    asyncio.run(navigation.publish(aid,tid,1,'publish'))
    assert navigation.item(aid)['status']=='publish_failed'
    assert '尚未处理成功' in navigation.item(aid)['error']

def test_automated_job_disables_capture_only(local,monkeypatch):
    from app import main
    captured=[]
    async def create(value):captured.append(value);return {'id':999}
    monkeypatch.setattr(main,'create_job',create)
    asyncio.run(main.create_automated_job({'mode':'discover','discover_only':True}))
    assert captured[0].automated_publish is True
    assert captured[0].discover_only is False
