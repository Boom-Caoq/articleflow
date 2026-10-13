import asyncio
import json
from contextlib import contextmanager
import pytest
from fastapi.testclient import TestClient
from app import core,navigation,nav_database,nav_browser,nav_upload
from app.main import app


@pytest.fixture
def local(tmp_path,monkeypatch):
    monkeypatch.setattr(core,'DATA',tmp_path)
    (tmp_path/'media').mkdir()
    core.init();navigation.init()
    return navigation.add('https://example.com/tool','工具')


def generated():
    return dict(is_tool=True,is_official=True,title='示例 AI 工具',summary='用于整理用户输入内容的 AI 工具。',content_html='<p>'+('根据官网介绍，工具可以辅助整理内容。'*10)+'</p>',categories=['AI办公'],tags=['AI','效率工具'])


def original():return dict(url='https://example.com/tool',title='官网',text='官网提供的可核实信息'*100,links=[],logo='/media/logo.png',screenshot='/media/screen.png')


def test_source_survives_without_model_key(local,monkeypatch):
    monkeypatch.setattr(nav_browser,'capture',lambda *args:original())
    tid=navigation.enqueue('generate',{'ids':[local]})
    asyncio.run(navigation.collect(local,tid,preserve_failed=True))
    row=navigation.item(local)
    assert row['status']=='failed' and row['original']['text']
    assert row['data']['screenshot']=='/media/screen.png'
    assert 'API Key' in row['error']


def test_generated_data_and_duplicate_before_paid_call(local,monkeypatch):
    core.save_settings({'api_key':'unit-test'})
    monkeypatch.setattr(nav_browser,'capture',lambda *args:original())
    calls=[]
    async def llm(*args):calls.append(1);return generated()
    monkeypatch.setattr(core,'llm',llm)
    tid=navigation.enqueue('generate',{'ids':[local]})
    asyncio.run(navigation.collect(local,tid))
    row=navigation.item(local)
    assert row['status']=='ready' and row['data']['categories']==['AI办公']
    assert len(calls)==1


def test_unobserved_official_link_never_visited(local,monkeypatch):
    core.save_settings({'api_key':'unit-test'})
    visited=[]
    def capture(url,log):visited.append(url);return original()
    async def llm(*args):return generated()|{'is_official':False,'official_link':'https://invented.invalid'}
    monkeypatch.setattr(nav_browser,'capture',capture);monkeypatch.setattr(core,'llm',llm)
    tid=navigation.enqueue('generate',{'ids':[local]})
    asyncio.run(navigation.collect(local,tid,preserve_failed=True))
    assert navigation.item(local)['status']=='failed' and len(visited)==1


def test_upload_secrets_redacted_and_publish_preflight(local):
    core.save_settings({'navigation_upload':{'host':'server','password':'secret-test'}})
    with TestClient(app) as client:
        assert 'secret-test' not in client.get('/api/settings').text
        upload=client.get('/api/navigation/upload')
        assert 'secret-test' not in upload.text and upload.json()['password_configured']
        assert client.post('/api/navigation/publish',json={'ids':[local]}).status_code==400
        assert not navigation.item(local)['busy']


def test_restart_retains_source_and_unlocks(local):
    navigation.save_data(local,generated(),original())
    tid=navigation.enqueue('generate',{'ids':[local]})
    with core.db() as c:c.execute("UPDATE nav_tasks SET status='running' WHERE id=?",(tid,))
    navigation.init()
    assert not navigation.item(local)['busy']
    assert navigation.item(local)['original']['text']
    with core.db() as c:assert c.execute('SELECT status FROM nav_tasks').fetchone()[0]=='interrupted'


def test_duplicate_enqueue_and_validation(local):
    navigation.enqueue('generate',{'ids':[local]})
    with pytest.raises(ValueError,match='处理任务'):navigation.enqueue('generate',{'ids':[local]})
    assert nav_database.identity('https://www.example.com/tool/?utm_source=a')==nav_database.identity('http://example.com/tool')
    with pytest.raises(ValueError):nav_database.identity('javascript:alert(1)')
    data=navigation.validate_data(generated()|{'url':'https://example.com','content_html':'<script>alert(1)</script>'+generated()['content_html']})
    assert '<script>' not in data['content_html']


class Cursor:
    def __init__(self,fail=False,prior=None):self.calls=[];self.lastrowid=501;self.fail=fail;self.prior=prior
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def execute(self,sql,args=None):
        self.calls.append((sql,args))
        if 'GET_LOCK' in sql:self.one={'acquired':1}
        elif 'information_schema.TABLES' in sql:self.many=[{'TABLE_NAME':'wp_'+t,'ENGINE':'InnoDB'} for t in ('posts','postmeta','terms','term_taxonomy','term_relationships')]
        elif 'SELECT ID FROM' in sql:self.one={'ID':1}
        elif "meta_key='_articleflow_nav_key'" in sql:self.one=self.prior
        else:self.one=None
    def executemany(self,sql,args):
        if self.fail:raise RuntimeError('simulated metadata failure')
        self.calls.append((sql,args))
    def fetchone(self):return self.one
    def fetchall(self):return self.many


class Connection:
    def __init__(self,cursor):self.q=cursor;self.commits=0;self.rollbacks=0
    def cursor(self):return self.q
    def commit(self):self.commits+=1
    def rollback(self):self.rollbacks+=1


@pytest.mark.parametrize('fail',[False,True])
def test_sql_publication_transaction_and_field_mapping(local,monkeypatch,fail):
    q=Cursor(fail);db=Connection(q)
    @contextmanager
    def connection():yield db
    monkeypatch.setattr(nav_database,'connection',connection)
    monkeypatch.setattr(nav_database,'schema',lambda q:('wp_',{'home':'https://example.com','timezone_string':'Asia/Shanghai'}))
    monkeypatch.setattr(nav_database,'existing',lambda *args:[])
    monkeypatch.setattr(nav_database,'term',lambda q,p,name,tax:101 if tax=='favorites' else 102)
    data=generated()|{'url':'https://tool.example.com'}
    if fail:
        with pytest.raises(RuntimeError):nav_database.publish({'data':data},{'logo':'https://media/logo.png','screenshot':'https://media/screen.png'},1,'draft')
        assert db.rollbacks==1 and db.commits==1 # Initial snapshot release only.
    else:
        result=nav_database.publish({'data':data},{'logo':'https://media/logo.png','screenshot':'https://media/screen.png'},1,'draft')
        assert result['id']==501 and db.commits==2
        meta=next(args for sql,args in q.calls if 'INSERT INTO `wp_postmeta`' in sql)
        fields={x[1]:x[2] for x in meta}
        assert fields['_sites_sescribe']==data['summary'] and fields['_thumbnail']=='https://media/logo.png'
        assert fields['_sites_preview']=='https://media/screen.png'
        assert any('term_relationships' in sql for sql,_ in q.calls)
    assert 'RELEASE_LOCK' in q.calls[-1][0]


def test_sftp_config_retains_password_and_rejects_unsafe_paths(local):
    cfg={'protocol':'sftp','host':'server','username':'u','password':'private','root':'/var/www/uploads','public_url':'https://example.com/uploads','port':22}
    core.save_settings({'navigation_upload':cfg})
    assert nav_upload.config({'password':''})['password']=='private'
    with pytest.raises(ValueError):nav_upload.config({'root':'/var/../etc'})
    with pytest.raises(ValueError):nav_upload.config({'public_url':'http://example.com/uploads'})


def test_retry_recovers_remote_committed_id(local,monkeypatch):
    q=Cursor(prior={'ID':77,'post_status':'draft'});db=Connection(q)
    @contextmanager
    def connection():yield db
    monkeypatch.setattr(nav_database,'connection',connection)
    monkeypatch.setattr(nav_database,'schema',lambda q:('wp_',{'home':'https://example.com'}))
    result=nav_database.publish({'data':{'url':'https://tool.example.com'}},{},1,'draft')
    assert result['id']==77 and result['recovered']
    assert not any('INSERT' in sql for sql,_ in q.calls)


def test_changed_url_requires_recapture(local,monkeypatch):
    async def public(url):return url
    monkeypatch.setattr(core,'public_url',public)
    navigation.save_data(local,generated()|{'url':'https://example.com/tool','logo':'/media/logo.png','screenshot':'/media/screen.png'},original())
    navigation.mark(local,'可发布','ready')
    with TestClient(app) as client:
        r=client.put(f'/api/navigation/items/{local}',json={k:v for k,v in (generated()|{'url':'https://new.example.com'}).items() if k not in ('is_tool','is_official')})
        assert r.status_code==200
        row=navigation.item(local)
        assert row['status']=='collected' and not row['original'] and not row['data']['screenshot']


def test_sftp_checks_host_key_before_sending_password(local,monkeypatch):
    events=[]
    class Socket:
        def close(self):pass
    class Key:
        def asbytes(self):return b'host-key'
    class Transport:
        def __init__(self,sock):pass
        def start_client(self,**kw):pass
        def get_remote_server_key(self):return Key()
        def auth_password(self,*args):events.append('password sent')
        def close(self):pass
    monkeypatch.setattr(nav_upload.socket,'create_connection',lambda *a,**kw:Socket())
    monkeypatch.setattr(nav_upload.paramiko,'Transport',Transport)
    with pytest.raises(nav_upload.HostKeyRequired):
        with nav_upload.session({'protocol':'sftp','host':'server','username':'u','password':'secret','root':'/var/www/uploads','public_url':'https://example.com/uploads'}):pass
    with pytest.raises(ValueError,match='不一致'):
        with nav_upload.session({'protocol':'sftp','host':'server','username':'u','password':'secret','root':'/var/www/uploads','public_url':'https://example.com/uploads','fingerprint':'wrong'}):pass
    assert events==[]


def test_logo_retry_does_not_regenerate(local,monkeypatch):
    navigation.save_data(local,generated()|{'url':'https://example.com/tool','logo':'','screenshot':'/media/screen.png'},original())
    navigation.mark(local,'待补图','needs_logo')
    monkeypatch.setattr(nav_browser,'download_logo',lambda *args:'/media/new-logo.png')
    async def forbidden(*args):raise AssertionError('must not call model to repair images')
    monkeypatch.setattr(core,'llm',forbidden)
    tid=navigation.enqueue('generate',{'ids':[local]})
    asyncio.run(navigation.collect(local,tid))
    assert navigation.item(local)['status']=='ready'
    assert navigation.item(local)['data']['logo']=='/media/new-logo.png'


def test_logo_download_normalizes_image(local,monkeypatch):
    import io,httpx
    from PIL import Image
    stream=io.BytesIO();Image.new('RGB',(80,80),'red').save(stream,format='PNG')
    client_type=httpx.Client
    transport=httpx.MockTransport(lambda request:httpx.Response(200,content=stream.getvalue()))
    monkeypatch.setattr(nav_browser.httpx,'Client',lambda **kwargs:client_type(transport=transport))
    monkeypatch.setattr(nav_browser.discovery,'public_url_sync',lambda u:u)
    result=nav_browser.download_logo(['https://example.com/logo.ico'],'https://example.com')
    assert result.endswith('.png') and (core.DATA/'media'/result.split('/')[-1]).exists()
