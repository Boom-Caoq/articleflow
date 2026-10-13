import asyncio
import json
import time
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import core, connections, skill_runtime, pipeline, navigation, nav_api, automation
from .discovery import SOURCES

queue = asyncio.Queue()
pending_articles=set()

async def worker():
    while True:
        jid = await queue.get()
        try:
            if isinstance(jid,tuple):
                _,aid,action=jid
                try:
                    await pipeline.advance(aid,sync_after=action=='continue',capture_only=action=='capture')
                finally:
                    pending_articles.discard(aid)
            else:
                await core.run_job(jid)
        except Exception as exc:
            if isinstance(jid,tuple):
                with core.db() as c:
                    current=c.execute('SELECT status FROM articles WHERE id=?',(jid[1],)).fetchone()
                if current and current['status'] not in ('synced','syncing'):
                    pipeline.mark(jid[1],'rewrite_failed','处理失败，可重试',core.safe_error(exc))
        finally:
            queue.task_done()

@asynccontextmanager
async def lifespan(app):
    global queue
    queue = asyncio.Queue()
    pending_articles.clear()
    core.init()
    navigation.init()
    automation.init()
    task = asyncio.create_task(worker())
    nav_task = asyncio.create_task(navigation.worker())
    scheduler_task = asyncio.create_task(automation.scheduler())
    with core.db() as c:
        legacy=c.execute("SELECT id FROM articles WHERE original='{}' AND status IN ('collected','rewrite_failed')").fetchall()
    for row in legacy:
        pending_articles.add(row['id'])
        await queue.put(('article',row['id'],'capture'))
    yield
    task.cancel()
    nav_task.cancel()
    scheduler_task.cancel()
    await asyncio.gather(nav_task,scheduler_task,return_exceptions=True)
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(title='ArticleFlow', lifespan=lifespan)
app.include_router(nav_api.router)

@app.get('/api/automations')
async def automations():
    return automation.listing()

@app.post('/api/automations/{kind}/run')
async def run_automation(kind:str):
    task_id=await automation.run_now(kind)
    return {'task_id':task_id,'automations':automation.listing()}

class AutomationInput(BaseModel):
    enabled:bool
    interval_minutes:int=Field(ge=5,le=525600)
    config:dict

@app.put('/api/automations/{kind}')
async def update_automation(kind:str,value:AutomationInput):
    config=value.config
    if kind=='articles':
        from .discovery import SOURCES
        config={'name':str(config.get('name','定时文章采集'))[:100],'mode':'discover','topics':str(config.get('topics','AI行业资讯\n人工智能\n大模型与生成式AI\nAI智能体与自动化\nAI产品发布与融资\nAI研究与开源模型'))[:1500],'days':int(config.get('days',7)),'candidate_limit':20,'content_type':config.get('content_type','all'),'discover_only':False,'sources':config.get('sources') or [x['url'] for x in SOURCES],'selector':'','limit':max(1,min(50,int(config.get('limit',5)))),'seo':config.get('seo',[]),'geo':config.get('geo',[])}
        if config['days'] not in (1,3,7,30) or config['content_type'] not in ('all','news','tools'):raise ValueError('文章采集设置无效')
        from .discovery import SOURCES
        if any(s not in [x['url'] for x in SOURCES] for s in config['sources']):raise ValueError('行业来源无效')
    elif kind=='navigation':
        config={'topic':str(config.get('topic','AI设计与绘画\nAI视频生成与剪辑\nAI音乐与音频\nAI自动化工具与智能体\nAI PPT与演示文稿\nAI Excel与数据分析\nAI写作与办公\nAI编程与开发'))[:1500],'limit':max(1,min(20,int(config.get('limit',5)))),'author':max(1,int(config.get('author',1)))}
        # Enabling is a scheduling preference. Missing external connections are
        # reported by the run itself and retried on the next interval.
    automation.configure(kind,value.enabled,value.interval_minutes,config)
    return automation.listing()

async def create_automated_job(config):
    config=dict(config)
    config['automated_publish']=True
    config['discover_only']=False
    value=JobInput.model_validate(config)
    result=await create_job(value)
    jid=result['id']
    with core.db() as c:c.execute('UPDATE jobs SET name=? WHERE id=?',(value.name,jid))
    return jid
app.mount('/static', StaticFiles(directory=core.ROOT/'static'), name='static')
app.mount('/media', StaticFiles(directory=core.DATA/'media'), name='media')

@app.middleware('http')
async def local_access(request: Request, call_next):
    if request.url.hostname not in ('127.0.0.1','localhost','testserver'):
        return JSONResponse({'detail':'本服务仅允许本机访问'},status_code=403)
    origin = request.headers.get('origin')
    if origin and urlsplit(origin).netloc != request.headers.get('host'):
        return JSONResponse({'detail':'拒绝跨站请求'},status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; frame-ancestors 'none'; object-src 'none'"
    return response

@app.exception_handler(ValueError)
async def invalid(request, exc):
    return JSONResponse({'detail':core.safe_error(exc)},status_code=400)

@app.get('/')
async def index():
    return FileResponse(core.ROOT/'static/index.html')

@app.get('/api/settings')
async def read_settings():
    s=core.settings()
    s.pop('navigation_upload',None)
    for key in ('api_key','wp_password','db_password'):
        s[key+'_configured']=bool(s[key])
        s[key]=''
    s['skill']='Boom-Caoq/de-ai-flavor'
    return s

@app.put('/api/settings')
async def write_settings(request:Request):
    value=await request.json()
    if not isinstance(value,dict):
        raise ValueError('配置必须为对象')
    for fields in connections.GROUPS.values():
        for key in fields:
            if key in value and value[key] and value[key]!=core.settings()[key]:
                raise ValueError('连接配置需要点击「检测并保存」，检测成功后才能保存')
    for key in ('api_key','model','wp_url','wp_user','wp_password','db_host','db_user','db_name','db_password'):
        if key in value and (not isinstance(value[key],str) or len(value[key])>2000):
            raise ValueError('配置字段格式错误')
    if 'auto_sync' in value and not isinstance(value['auto_sync'],bool):
        raise ValueError('自动同步配置无效')
    if value.get('wp_url'):
        await core.public_url(value['wp_url'])
    core.save_settings({k:v for k,v in value.items() if k in ('auto_sync','wp_status')})
    return {'ok':True}

@app.post('/api/connections/{group}/test')
async def test_connection(group:str,request:Request):
    return await connections.verify(group,await request.json())

@app.get('/api/skill/runtime')
async def runtime():
    return await asyncio.to_thread(skill_runtime.info)

@app.post('/api/database/inspect')
async def inspect_database():
    return await asyncio.to_thread(core.inspect_database)

@app.get('/api/skill')
async def read_skill():
    return json.loads((core.ROOT/'skills/de-ai-flavor/config.json').read_text(encoding='utf-8'))

@app.put('/api/skill')
async def write_skill(request:Request):
    cfg=await request.json()
    if not isinstance(cfg,dict) or not isinstance(cfg.get('max_revision_iterations'),dict):
        raise ValueError('请保留原有 skill 配置结构')
    rounds=cfg['max_revision_iterations'].get('value')
    if not isinstance(rounds,int) or not 1<=rounds<=3:
        raise ValueError('修订次数必须为 1 至 3')
    (core.ROOT/'skills/de-ai-flavor/config.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
    return {'ok':True}

class JobInput(BaseModel):
    name:str=Field(default='新的采集任务',min_length=1,max_length=100)
    urls:list[str]=Field(default_factory=list,max_length=50)
    mode:str='discover'
    topics:str=Field(default='人工智能,大模型,AI工具',min_length=1,max_length=1500)
    days:int=Field(default=7,ge=1,le=30)
    candidate_limit:int=Field(default=15,ge=3,le=40)
    content_type:str='all'
    discover_only:bool=False
    sources:list[str]=Field(default_factory=lambda:[s['url'] for s in SOURCES],max_length=10)
    selector:str=Field(default='',max_length=300)
    limit:int=Field(default=5,ge=1,le=50)
    seo:list[str]=Field(default_factory=list,max_length=30)
    geo:list[str]=Field(default_factory=list,max_length=30)
    automated_publish:bool=False

@app.post('/api/jobs')
async def create_job(value:JobInput):
    if value.mode not in ('articles','list','discover'):
        raise ValueError('采集模式无效')
    if value.mode!='discover' and not value.urls:
        raise ValueError('手动采集模式需要填写来源网址')
    if value.content_type not in ('all','news','tools'):
        raise ValueError('内容类型无效')
    if value.mode=='discover':
        from .discovery import SOURCES
        if any(s not in [x['url'] for x in SOURCES] for s in value.sources):
            raise ValueError('请选择已配置的行业来源')
    for url in value.urls:
        await core.public_url(url)
    with core.db() as c:
        config=value.model_dump()
        automated=bool(config.get('automated_publish',False))
        if automated:config['automated_publish']=True
        jid=c.execute('INSERT INTO jobs(name,config,created) VALUES(?,?,?)',(value.name,json.dumps(config,ensure_ascii=False),time.time())).lastrowid
    await queue.put(jid)
    return {'id':jid}

@app.get('/api/discovery/sources')
async def discovery_sources():
    from .discovery import SOURCES
    return SOURCES

@app.get('/api/jobs/{jid}/candidates')
async def candidates(jid:int):
    with core.db() as c:
        row=c.execute('SELECT value FROM discoveries WHERE job_id=?',(jid,)).fetchone()
    return json.loads(row[0]) if row else []

@app.post('/api/jobs/{jid}/retry')
async def retry(jid:int):
    with core.db() as c:
        row=c.execute('SELECT status FROM jobs WHERE id=?',(jid,)).fetchone()
        if not row:
            raise HTTPException(404,'任务不存在')
        if row[0] in ('running','queued'):
            raise ValueError('任务已经在队列中')
        c.execute("UPDATE jobs SET status='queued',stage='等待重试',progress=0 WHERE id=?",(jid,))
    await queue.put(jid)
    return {'ok':True}

@app.get('/api/dashboard')
async def dashboard():
    with core.db() as c:
        jobs=[dict(x) for x in c.execute('SELECT * FROM jobs ORDER BY id DESC LIMIT 100')]
        articles=[dict(x) for x in c.execute('SELECT id,job_id,title,source,excerpt,tags,categories,images,keywords,status,wp_url,error,stage FROM articles ORDER BY id DESC LIMIT 200')]
        count=c.execute('SELECT COUNT(*) FROM articles').fetchone()[0]
        generated=c.execute("SELECT COUNT(*) FROM articles WHERE status IN ('ready','synced','syncing','sync_failed','sync_uncertain')").fetchone()[0]
        synced=c.execute("SELECT COUNT(*) FROM articles WHERE status='synced'").fetchone()[0]
    for job in jobs:
        job['logs']=json.loads(job['logs'])
        job['config']=json.loads(job['config'])
    for a in articles:
        for k in ('tags','categories','images','keywords'):
            a[k]=json.loads(a[k])
    return dict(jobs=jobs,articles=articles,total=generated,library_total=count,synced=synced)

@app.get('/api/library/connections')
async def library_connections():
    s=core.settings()
    return {
        'siliconflow':dict(configured=bool(s['api_key']),check=s.get('connection_checks',{}).get('siliconflow')),
        'wordpress':dict(configured=all(s[k] for k in ('wp_url','wp_user','wp_password')),check=s.get('connection_checks',{}).get('wordpress')),
        'auto_sync':s['auto_sync'],'wp_status':s['wp_status']
    }

@app.post('/api/articles/{aid}/process')
async def process_article(aid:int,request:Request):
    value=await request.json()
    if not isinstance(value,dict):raise ValueError('处理参数必须是对象')
    action=value.get('action','continue')
    if action not in ('rewrite','continue','capture'):raise ValueError('处理动作无效')
    with core.db() as c:
        row=c.execute('SELECT status,draft FROM articles WHERE id=?',(aid,)).fetchone()
        if not row:raise HTTPException(404,'文章不存在')
        if row['status']=='synced':return {'status':'synced'}
        if aid in pending_articles or row['status'] in ('processing','syncing'):
            raise ValueError('文章正在处理或排队中')
        needs_model=row['status'] in ('collected','rewrite_failed') and not json.loads(row['draft'] or '{}')
        if action!='capture' and needs_model and not core.settings()['api_key']:
            raise ValueError('尚未开始改写：请到连接设置填写硅基流动 API Key，点击「检测并保存」成功后再试。采集原文已保留。')
        c.execute("UPDATE articles SET stage='已加入处理队列',error='' WHERE id=?",(aid,))
    pending_articles.add(aid)
    await queue.put(('article',aid,action))
    return {'status':'queued'}

@app.get('/api/articles/{aid}')
async def article(aid:int):
    with core.db() as c:
        a=c.execute('SELECT * FROM articles WHERE id=?',(aid,)).fetchone()
    if not a:
        raise HTTPException(404,'文章不存在')
    result=dict(a)
    for k in ('tags','categories','images','keywords','report'):
        result[k]=json.loads(result[k])
    result['original']=json.loads(result['original'] or '{}')
    result['pipeline_config']=json.loads(result['pipeline_config'] or '{}')
    return result

@app.post('/api/articles/{aid}/sync')
async def sync(aid:int):
    if aid in pending_articles:raise HTTPException(409,'文章正在排队处理中')
    try:
        return await core.sync_article(aid)
    except Exception as e:
        raise HTTPException(400,core.safe_error(e)) from None
