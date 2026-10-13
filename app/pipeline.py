"""Durable article stages: source acquisition never depends on model credentials."""
import asyncio
import html
import json
from bs4 import BeautifulSoup
from . import core

def save_source(jid,url,original,config,selection=None):
    text=original['text']
    body=''.join('<p>'+html.escape(p)+'</p>' for p in text.splitlines() if p.strip())
    with core.db() as c:
        c.execute("INSERT OR IGNORE INTO articles(job_id,source,title,content,excerpt,tags,categories,images,keywords,report,status,original,pipeline_config,stage) VALUES(?,?,?,?,?,'[]','[]','[]','[]',?,'collected',?,?,'已采集，待 Skill 改写')",(jid,url,original['title'],body,text[:180],json.dumps({'discovery':selection} if selection else {},ensure_ascii=False),json.dumps(original,ensure_ascii=False),json.dumps(config,ensure_ascii=False)))
        row=c.execute('SELECT id,original,status FROM articles WHERE source=?',(url,)).fetchone()
        if not json.loads(row['original'] or '{}').get('text') and row['status'] in ('collected','rewrite_failed'):
            c.execute('UPDATE articles SET original=?,content=?,excerpt=?,stage=?,error=? WHERE id=?',(json.dumps(original,ensure_ascii=False),body,text[:180],'已采集，待 Skill 改写','',row['id']))
        return row['id']

def mark(aid,status,stage,error=''):
    with core.db() as c:
        c.execute('UPDATE articles SET status=?,stage=?,error=? WHERE id=?',(status,stage,error,aid))

async def advance(aid,sync_after=False,capture_only=False):
    with core.db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT * FROM articles WHERE id=?',(aid,)).fetchone()
        if not row:raise ValueError('文章不存在')
        a=dict(row)
        automated=bool(json.loads(a['pipeline_config'] or '{}').get('automated_publish'))
        if automated:sync_after=True;capture_only=False
        if a['status']=='synced' and not automated:return {'status':'synced'}
        if a['status'] in ('processing','syncing'):raise ValueError('文章正在处理中，请勿重复提交')
        generated=a['status'] in ('ready','sync_failed','sync_uncertain','synced')
        if not generated:
            c.execute("UPDATE articles SET status='processing',stage='准备原文',error='' WHERE id=?",(aid,))
    if not generated:
        try:
            original=json.loads(a['original'] or '{}')
            config={'seo':[],'geo':[],**json.loads(a['pipeline_config'] or '{}')}
            if not original.get('text'):
                from .discovery import read_article
                mark(aid,'processing','浏览器补采历史入选原文')
                original=await asyncio.to_thread(read_article,a['source'])
                # Write the source immediately, before any paid step or media download.
                with core.db() as c:
                    c.execute('UPDATE articles SET original=?,content=?,excerpt=? WHERE id=?',(json.dumps(original,ensure_ascii=False),''.join('<p>'+html.escape(x)+'</p>' for x in original['text'].splitlines()),original['text'][:180],aid))
            draft=json.loads(a.get('draft') or '{}')
            if capture_only or (not draft and not core.settings()['api_key']):
                mark(aid,'collected','已采集，待 Skill 改写','' if capture_only else '请先配置硅基流动 API Key，原文已保留，可随时继续')
                return {'status':'collected'}
            if draft:
                article,report=draft['article'],draft['report']
            else:
                mark(aid,'processing','DS V4 Flash + 本地 Skill 改写与质检')
                article,report=await core.generate(a['job_id'],original,config,lambda stage:mark(aid,'processing',stage))
                with core.db() as c:
                    c.execute('UPDATE articles SET draft=? WHERE id=?',(json.dumps({'article':article,'report':report},ensure_ascii=False),aid))
            if report.get('verdict')!='pass' or report.get('content_preserved') is not True:
                raise ValueError('文章质检未通过，已停止自动发布')
            previous=json.loads(a['report'] or '{}')
            if previous.get('discovery'):report['discovery']=previous['discovery']
            mark(aid,'processing','下载封面与正文配图')
            images=await core.media_files(original,a['source'])
            content=article['content_html']
            for img in images[1:]:
                content+=f'<figure><img src="{img["path"]}" alt="{html.escape(img["alt"],quote=True)}" loading="lazy"></figure>'
            source=original.get('source_url') or a['source']
            content+=f'<p>资料来源：<a href="{html.escape(source,quote=True)}">原文链接</a></p>'
            plain=BeautifulSoup(content,'html.parser').get_text()
            keywords=[dict(word=x,count=plain.lower().count(x.lower())) for x in dict.fromkeys(config['seo']+config['geo'])]
            with core.db() as c:
                c.execute("UPDATE articles SET title=?,content=?,excerpt=?,tags=?,categories=?,images=?,keywords=?,report=?,status='ready',stage='改写完成，待 WordPress 同步',error='' WHERE id=?",(article['title'],content,article['excerpt'],json.dumps(article['tags'],ensure_ascii=False),json.dumps(article['categories'],ensure_ascii=False),json.dumps(images,ensure_ascii=False),json.dumps(keywords,ensure_ascii=False),json.dumps(report,ensure_ascii=False),aid))
        except Exception as e:
            mark(aid,'rewrite_failed','改写或补采失败，可重试',core.safe_error(e))
            return {'status':'rewrite_failed'}
    if sync_after and not capture_only:
        s=core.settings()
        if not all(s[k] for k in ('wp_url','wp_user','wp_password')):
            mark(aid,'ready','待配置 WordPress 后继续','改写稿已保存，请配置 WordPress 用户名和应用密码')
            return {'status':'ready'}
        try:
            await core.sync_article(aid)
        except Exception as e:
            mark(aid,'sync_failed','同步失败，可重试',core.safe_error(e))
            return {'status':'sync_failed'}
        return {'status':'synced'}
    return {'status':'ready'}
