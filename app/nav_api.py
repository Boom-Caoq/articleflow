import asyncio
import io
import json
import hashlib
from fastapi import APIRouter
from pydantic import BaseModel,Field
from PIL import Image
from . import core,navigation,nav_database,nav_upload

router=APIRouter(prefix='/api/navigation')


@router.get('')
async def listing():
    with core.db() as c:
        items=[dict(x) for x in c.execute('SELECT id,url,data,status,stage,error,busy,wp_id,wp_url,created FROM nav_items ORDER BY id DESC LIMIT 500')]
        tasks=[dict(x) for x in c.execute('SELECT * FROM nav_tasks ORDER BY id DESC LIMIT 30')]
    for row in items:row['data']=json.loads(row['data'])
    for row in tasks:
        row['logs']=json.loads(row['logs']);row.pop('config')
    return {'items':items,'tasks':tasks}


@router.get('/structure')
async def structure():
    try:
        value=await asyncio.to_thread(nav_database.inspect)
        value['existing_count']=len(value.pop('existing'))
        return {'ok':True,**value}
    except Exception as e:return {'ok':False,'message':core.safe_error(e)}


@router.get('/upload')
async def upload_settings():
    value=core.settings().get('navigation_upload',{}).copy()
    value['password_configured']=bool(value.pop('password',None))
    return value


class UploadInput(BaseModel):
    host:str=Field(max_length=255)
    port:int=Field(default=22,ge=1,le=65535)
    username:str=Field(max_length=255)
    password:str=Field(default='',max_length=2000)
    root:str=Field(max_length=1000)
    public_url:str=Field(max_length=1000)
    fingerprint:str=Field(default='',max_length=200)


@router.post('/upload/test')
async def test_upload(value:UploadInput):
    try:
        candidate=nav_upload.config(value.model_dump())
        message=await asyncio.to_thread(nav_upload.check,candidate)
        core.save_settings({'navigation_upload':candidate})
        return {'ok':True,'message':message}
    except nav_upload.HostKeyRequired as e:return {'ok':False,'needs_host_key':True,'fingerprint':e.fingerprint,'message':str(e)}
    except Exception as e:return {'ok':False,'message':core.safe_error(e)}


class DiscoverInput(BaseModel):
    topic:str=Field(default='中文 AI 写作 编程 办公 工具',min_length=1,max_length=200)
    limit:int=Field(default=5,ge=1,le=20)


@router.post('/discover')
async def discover(value:DiscoverInput):
    return {'id':navigation.enqueue('discover',value.model_dump())}


class AddInput(BaseModel):
    urls:list[str]=Field(min_length=1,max_length=20)


@router.post('/items')
async def add(value:AddInput):
    for url in value.urls:await core.public_url(url)
    ids=list(dict.fromkeys(navigation.add(url) for url in value.urls))
    ids=[aid for aid in ids if not navigation.item(aid)['busy'] and navigation.item(aid)['status'] not in ('published','draft','ready')]
    return {'id':navigation.enqueue('generate',{'ids':ids})} if ids else {'message':'网址已存在，无需重复采集'}


@router.get('/items/{aid}')
async def detail(aid:int):return navigation.item(aid)


class EditInput(BaseModel):
    title:str=Field(min_length=1,max_length=120)
    url:str=Field(min_length=1,max_length=2000)
    summary:str=Field(min_length=1,max_length=240)
    content_html:str=Field(min_length=1,max_length=40000)
    categories:list[str]=Field(min_length=1,max_length=10)
    tags:list[str]=Field(min_length=1,max_length=10)
    logo_url:str=Field(default='',max_length=2000)


@router.put('/items/{aid}')
async def edit(aid:int,value:EditInput):
    row=navigation.item(aid)
    if row['busy'] or row['status'] in ('published','draft'):raise ValueError('正在处理或已发布的网址不能在本地修改')
    await core.public_url(value.url)
    data=navigation.validate_data(row['data']|value.model_dump(exclude={'logo_url'}))
    if value.logo_url:
        raw,_,_=await core.fetch(value.logo_url,2_000_000)
        path=core.DATA/'media'/('nav-logo-'+hashlib.sha256(raw).hexdigest()[:24]+'.png')
        with Image.open(io.BytesIO(raw)) as image:
            image.load();image.thumbnail((512,512));image.convert('RGBA').save(path)
        data['logo']='/media/'+path.name
    with core.db() as c:
        # Re-check after awaiting a logo download to avoid racing the worker.
        c.execute('BEGIN IMMEDIATE')
        current=c.execute('SELECT busy,status FROM nav_items WHERE id=?',(aid,)).fetchone()
        if current['busy'] or current['status'] in ('published','draft'):raise ValueError('网址状态已变化，请刷新后再编辑')
        key=nav_database.identity(data['url'])
        if c.execute('SELECT id FROM nav_items WHERE identity=? AND id<>?',(key,aid)).fetchone():raise ValueError('该官网已在导航库中，请编辑已有记录')
        changed=key!=row['identity']
        if changed:
            data['logo']='';data['screenshot']=''
            c.execute("UPDATE nav_items SET original='{}' WHERE id=?",(aid,))
        c.execute('UPDATE nav_items SET identity=?,url=? WHERE id=?',(key,data['url'],aid))
        complete=bool(data.get('logo') and data.get('screenshot'))
        c.execute('UPDATE nav_items SET data=?,status=?,stage=?,error=? WHERE id=?',(json.dumps(data,ensure_ascii=False),'collected' if changed else 'ready' if complete else 'needs_logo','官网链接已变更，请重新采集截图与资料' if changed else '编辑已保存，可发布' if complete else '编辑已保存，仍需补齐截图或 Logo','',aid))
    return {'ok':True}


class ActionInput(BaseModel):
    ids:list[int]=Field(min_length=1,max_length=50)
    author:int=Field(default=1,ge=1)
    status:str='draft'


@router.post('/generate')
async def generate(value:ActionInput):
    if not core.settings()['api_key']:raise ValueError('请先在连接设置检测并保存硅基流动 API Key，原始资料会继续保留')
    return {'id':navigation.enqueue('generate',{'ids':list(dict.fromkeys(value.ids))})}


@router.post('/publish')
async def publish(value:ActionInput):
    if value.status not in ('draft','publish'):raise ValueError('发布状态无效')
    nav_upload.config()
    for aid in value.ids:
        row=navigation.item(aid)
        navigation.validate_data(row['data'])
        if not row['data'].get('logo') or not row['data'].get('screenshot'):raise ValueError('请先补齐 Logo 和网站截图')
    return {'id':navigation.enqueue('publish',value.model_dump()|{'ids':list(dict.fromkeys(value.ids))})}
