"""Persistent interval scheduler for article and AI directory publishing."""
import asyncio
import json
import time
from . import core, navigation

DEFAULTS = {
    'articles': {'enabled': False, 'interval_minutes': 1440, 'config': {'name':'定时文章采集','mode':'discover','topics':'AI行业资讯\n人工智能\n大模型与生成式AI\nAI智能体与自动化\nAI产品发布与融资\nAI研究与开源模型\nAI设计与绘画\nAI视频与音频','days':7,'candidate_limit':20,'content_type':'all','discover_only':False,'sources':[],'selector':'','limit':5,'seo':[],'geo':[]}},
    'navigation': {'enabled': False, 'interval_minutes': 1440, 'config': {'topic':'AI设计与绘画\nAI视频生成与剪辑\nAI音乐与音频\nAI自动化工具与智能体\nAI PPT与演示文稿\nAI Excel与数据分析\nAI写作与办公\nAI编程与开发\nAI图像与3D\nAI搜索与知识管理','limit':5}},
}

def init():
    with core.db() as c:
        c.execute("CREATE TABLE IF NOT EXISTS automations (kind TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 0, interval_minutes INTEGER NOT NULL DEFAULT 1440, config TEXT NOT NULL, next_run REAL, last_run REAL, last_task_id INTEGER, status TEXT NOT NULL DEFAULT 'idle', stage TEXT NOT NULL DEFAULT '等待执行', progress INTEGER NOT NULL DEFAULT 0, error TEXT NOT NULL DEFAULT '', updated REAL NOT NULL)")
        for kind, default in DEFAULTS.items():
            c.execute('INSERT OR IGNORE INTO automations(kind,enabled,interval_minutes,config,next_run,updated) VALUES(?,0,?,?,NULL,?)',(kind,default['interval_minutes'],json.dumps(default['config'],ensure_ascii=False),time.time()))
            row=c.execute('SELECT config FROM automations WHERE kind=?',(kind,)).fetchone()
            config=json.loads(row['config'])
            old_topics={'articles':'人工智能,大模型,AI工具','navigation':'中文 AI 写作 编程 办公 工具'}[kind]
            key='topics' if kind=='articles' else 'topic'
            if config.get(key)==old_topics:
                config[key]=default['config'][key]
                c.execute('UPDATE automations SET config=?,updated=? WHERE kind=?',(json.dumps(config,ensure_ascii=False),time.time(),kind))
        c.execute("UPDATE automations SET next_run=?,status='queued',stage='首次启用，立即开始',updated=? WHERE enabled=1 AND last_run IS NULL",(time.time(),time.time()))

def listing():
    with core.db() as c: rows=[dict(r) for r in c.execute('SELECT * FROM automations ORDER BY kind')]
    for r in rows:r['config']=json.loads(r['config']);r['enabled']=bool(r['enabled'])
    return rows

def configure(kind, enabled, interval_minutes, config):
    if kind not in DEFAULTS: raise ValueError('自动化类型无效')
    if not 5 <= interval_minutes <= 525600: raise ValueError('间隔需为 5 分钟至 365 天')
    now=time.time()
    with core.db() as c:
        old=c.execute('SELECT status,last_run FROM automations WHERE kind=?',(kind,)).fetchone()
        next_run=(now if old['last_run'] is None else now+interval_minutes*60) if enabled and old['status']!='running' else None
        status=old['status'] if old['status']=='running' else 'queued' if enabled and old['last_run'] is None else 'idle' if enabled else 'paused'
        stage='首次启用，立即开始' if enabled and old['last_run'] is None else '等待下次计划运行' if enabled else '已关闭'
        c.execute('UPDATE automations SET enabled=?,interval_minutes=?,config=?,next_run=?,status=?,stage=?,progress=CASE WHEN ? THEN progress ELSE 0 END,updated=? WHERE kind=?',(int(enabled),interval_minutes,json.dumps(config,ensure_ascii=False),next_run,status,stage,int(enabled),now,kind))

def _sync_status(kind, task_id):
    with core.db() as c:
        if kind=='articles':
            row=c.execute('SELECT status,stage,progress FROM jobs WHERE id=?',(task_id,)).fetchone()
            table='jobs'
        else:
            row=c.execute('SELECT status,stage FROM nav_tasks WHERE id=?',(task_id,)).fetchone();table='nav_tasks'
        if not row:return
        progress=row['progress'] if kind=='articles' else (100 if row['status'] in ('completed','partial','failed') else 50 if row['status']=='running' else 0)
        status=row['status'];stage=row['stage']
        if status not in ('queued','running'):
            enabled=c.execute('SELECT enabled FROM automations WHERE kind=?',(kind,)).fetchone()[0]
            next_run=time.time()+c.execute('SELECT interval_minutes FROM automations WHERE kind=?',(kind,)).fetchone()[0]*60 if enabled else None
            c.execute('UPDATE automations SET status=?,stage=?,progress=?,error=?,next_run=?,updated=? WHERE kind=?',(status,stage,progress,stage if status in ('failed','partial') else '',next_run,time.time(),kind))
        else:
            display_status='running' if status=='queued' else status
            display_stage=('采集任务排队中' if kind=='articles' else '导航任务排队中') if status=='queued' else stage
            c.execute('UPDATE automations SET status=?,stage=?,progress=?,updated=? WHERE kind=?',(display_status,display_stage,max(progress,1 if status=='queued' else 0),time.time(),kind))

async def scheduler():
    while True:
        now=time.time()
        with core.db() as c: due=[dict(r) for r in c.execute("SELECT * FROM automations WHERE enabled=1 AND status NOT IN ('running','queued') AND (next_run IS NULL OR next_run<=?)",(now,))]
        for row in due:
            kind=row['kind'];cfg=json.loads(row['config'])
            try:
                if kind=='articles':
                    from .main import create_automated_job
                    task_id=await create_automated_job(cfg)
                else:
                    from . import nav_database
                    await asyncio.to_thread(nav_database.inspect)
                    task_id=navigation.enqueue('automated_discover',cfg|{'auto_publish':True,'author':cfg.get('author',1),'status':'publish'})
                with core.db() as c:c.execute("UPDATE automations SET last_run=?,last_task_id=?,status='running',stage='任务已启动',progress=1,error='',next_run=NULL,updated=? WHERE kind=? AND enabled=1",(now,task_id,now,kind))
            except Exception as e:
                with core.db() as c:c.execute("UPDATE automations SET last_run=?,status='failed',stage='启动失败',error=?,next_run=CASE WHEN enabled=1 THEN ? ELSE NULL END,updated=? WHERE kind=?",(now,core.safe_error(e),now+row['interval_minutes']*60,now,kind))
        with core.db() as c: running=[(r['kind'],r['last_task_id']) for r in c.execute("SELECT kind,last_task_id FROM automations WHERE status='running' AND last_task_id IS NOT NULL")]
        for kind,task_id in running:_sync_status(kind,task_id)
        await asyncio.sleep(2)
