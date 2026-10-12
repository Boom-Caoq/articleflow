"""Topic-driven discovery. Chromium renders every candidate before selection."""
import asyncio
import calendar
import hashlib
import json
import ipaddress
import re
import socket
import time
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, urljoin
from urllib.robotparser import RobotFileParser

import feedparser
import httpx
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from . import core

# Editable through the source API/UI. Feeds discover links; full text comes from Chromium.
SOURCES = [
    {'name':'IT之家 · 中文资讯（优先）','url':'https://www.ithome.com/rss/','priority':12},
    {'name':'Hugging Face · 工具与模型','url':'https://huggingface.co/blog/feed.xml','priority':20},
    {'name':'TechCrunch · AI','url':'https://techcrunch.com/category/artificial-intelligence/feed/','priority':16},
    {'name':'Google AI · 官方动态','url':'https://blog.google/technology/ai/rss/','priority':20},
    {'name':'The Verge · 科技资讯','url':'https://www.theverge.com/rss/index.xml','priority':14},
]
AI = re.compile(r'\b(ai|llm|gpt|claude|gemini|deepseek|chatgpt|openai|anthropic|hugging\s?face)\b|artificial intelligence|machine learning|人工智能|大模型|生成式|智能体|机器学习|深度学习',re.I)
TOOL = re.compile(r'\b(tool|launch|release|model|agent|app|open.source|api|coding)\b|工具|发布|开源|模型|应用|插件|上线|智能体',re.I)

def is_chinese(text):
    chinese=len(re.findall(r'[\u3400-\u9fff]',text))
    letters=len(re.findall(r'[A-Za-z\u3400-\u9fff]',text))
    return chinese>=2 and chinese/max(1,letters)>=.2

def reading_order(candidates,limit):
    def interleave(items):
        buckets={}
        for item in items:buckets.setdefault(item['source'],[]).append(item)
        out=[]
        while buckets:
            for source in list(buckets):
                out.append(buckets[source].pop(0))
                if not buckets[source]:del buckets[source]
        return out
    zh=interleave([c for c in candidates if is_chinese(c['title'])])
    other=interleave([c for c in candidates if not is_chinese(c['title'])])
    quota=(limit*4+4)//5
    first=zh[:quota]
    return (first+other[:limit-len(first)]+zh[quota:]+other[limit-len(first):])[:limit]

def selection_order(candidates):
    return sorted(candidates,key=lambda c:(c.get('language')=='zh',c['score']),reverse=True)

def canonical(url):
    p=urlsplit(url)
    query=[(k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid')]
    return urlunsplit((p.scheme,p.netloc.lower(),p.path.rstrip('/') or '/',urlencode(query),''))

def normalized(title):
    return re.sub(r'[^\w\u4e00-\u9fff]','',title.lower())

def near_duplicate(title,previous):
    n=normalized(title)
    return any(n and SequenceMatcher(None,n,normalized(p)).ratio()>=.82 for p in previous)

def date_stamp(value):
    if not isinstance(value,str) or not value: return None
    try:
        d=datetime.fromisoformat(value.strip().replace('Z','+00:00'))
        return d.replace(tzinfo=d.tzinfo or timezone.utc).timestamp()
    except (ValueError,TypeError): return None

def publication(raw, fallback=None):
    soup=BeautifulSoup(raw,'html.parser')
    for selector in ('meta[property="article:published_time"]','meta[name="date"]','meta[itemprop="datePublished"]','time[itemprop="datePublished"][datetime]'):
        tag=soup.select_one(selector)
        if tag:
            stamp=date_stamp(tag.get('content') or tag.get('datetime'))
            if stamp: return stamp,'网页发布日期'
    def walk(obj):
        if isinstance(obj,dict):
            if obj.get('datePublished'):
                stamp=date_stamp(obj['datePublished'])
                if stamp: return stamp
            for v in obj.values():
                stamp=walk(v)
                if stamp: return stamp
        elif isinstance(obj,list):
            for v in obj:
                stamp=walk(v)
                if stamp: return stamp
        return None
    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            stamp=walk(json.loads(tag.string or tag.get_text()))
            if stamp:return stamp,'结构化发布日期'
        except (ValueError,TypeError): pass
    return fallback, '订阅源发布日期' if fallback else '日期未知'

def score(candidate,original,config,now=None):
    now=now or time.time()
    stamp=candidate.get('published')
    if not stamp:return 0,'无可核查发布日期，未入选'
    age=(now-stamp)/86400
    if age<-.5:return 0,'发布日期在未来，未入选'
    if age>config['days']:return 0,f'超过最近 {config["days"]} 天的时效窗口'
    text=original['title']+' '+original['text'][:12000]
    if not AI.search(text):return 0,'与 AI 行业相关性不足'
    if len(original['text'])<400:return 0,'正文过短或未完整提取'
    if config['content_type']=='tools' and not TOOL.search(text):return 0,'不符合工具与模型主题'
    topics=[x for x in re.split(r'[,，\n]',config['topics']) if x.strip()]
    hits=[x.strip() for x in topics if x.strip().lower() in text.lower()]
    # A declared, inspectable heuristic, not a claim of factual truth or SEO ranking.
    freshness=round(30*(1-max(0,age)/config['days']))
    priority=candidate.get('priority',8)
    relevance=20+min(10,len(hits)*3)
    completeness=min(20,len(original['text'])//150)
    return freshness+priority+relevance+completeness,f'时效 {freshness}/30 · 来源优先级 {priority}/20 · 主题 {relevance}/30 · 完整度 {completeness}/20'

def persist(jid,candidates):
    with core.db() as c:
        c.execute('INSERT OR REPLACE INTO discoveries(job_id,value) VALUES(?,?)',(jid,json.dumps(candidates,ensure_ascii=False)))

def public_url_sync(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):
        raise ValueError('仅允许公网 HTTP/HTTPS 页面')
    addresses=socket.getaddrinfo(p.hostname,p.port or 443,type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(x[4][0]).is_global for x in addresses):
        raise ValueError('禁止浏览器访问本机、内网和保留地址')
    return url

def fetch_robots(url):
    with httpx.Client(timeout=12,trust_env=False,headers={'User-Agent':'ArticleFlow/1.0'}) as client:
        for _ in range(5):
            public_url_sync(url)
            with client.stream('GET',url) as response:
                if response.is_redirect:
                    url=urljoin(url,response.headers['location']);continue
                response.raise_for_status()
                data=bytearray()
                for chunk in response.iter_bytes():
                    data.extend(chunk)
                    if len(data)>500_000:raise ValueError('robots.txt 过大')
                return bytes(data)
    raise ValueError('robots.txt 重定向过多')

def read_article(url):
    """Reacquire legacy selections whose original body was never persisted."""
    public_url_sync(url)
    cache={}
    if not robots_allowed(url,cache):raise ValueError('网站禁止采集或爬取规则无法确认')
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(service_workers='block',accept_downloads=False)
        page=context.new_page()
        def guard(route):
            try:
                request=route.request
                if request.resource_type in ('image','font','media'):
                    route.abort();return
                public_url_sync(request.url)
                if request.resource_type=='document' and not robots_allowed(request.url,cache):
                    route.abort();return
                if request.resource_type!='document' and urlsplit(request.url).hostname!=urlsplit(page.url).hostname:
                    route.abort();return
                route.continue_()
            except Exception:route.abort()
        context.route('**/*',guard)
        try:
            response=page.goto(url,wait_until='domcontentloaded',timeout=35000)
            if response and response.status>=400:raise ValueError(f'网页 HTTP {response.status}')
            try:page.wait_for_load_state('networkidle',timeout=3000)
            except Exception:pass
            raw=page.content()
            original=core.extract(raw,public_url_sync(page.url))
            stamp,_=publication(raw)
            original['source_date']=datetime.fromtimestamp(stamp,timezone.utc).isoformat() if stamp else None
            original['source_url']=page.url
            return original
        finally:
            context.close();browser.close()

def robots_allowed(url,cache):
    p=urlsplit(url)
    origin=f'{p.scheme}://{p.netloc}'
    if origin not in cache:
        try:
            raw=fetch_robots(origin+'/robots.txt')
            robot=RobotFileParser()
            robot.parse(raw.decode('utf-8',errors='replace').splitlines())
            cache[origin]=robot
        except httpx.HTTPStatusError as e:
            if e.response.status_code==404:cache[origin]=True
            else:cache[origin]=False
        except Exception:cache[origin]=False
    rule=cache[origin]
    return rule if isinstance(rule,bool) else rule.can_fetch('ArticleFlow',url)

def run(jid,config):
    """Called in one dedicated thread (Playwright sync APIs stay in that thread)."""
    candidates=[]
    seen=set()
    now=time.time()
    with core.db() as c:
        previous={canonical(r[0]) for r in c.execute('SELECT source FROM articles')}
    def add(url,title,source,published=None,priority=8):
        if not url.startswith(('http://','https://')):return
        url=canonical(url)
        if url in seen:return
        seen.add(url)
        candidates.append(dict(url=url,title=title[:300],source=source,published=published,priority=priority,status='found',score=0,reason='等待浏览器阅读'))
    selected_sources=config.get('sources',[s['url'] for s in SOURCES])
    for src in SOURCES:
        if src['url'] not in selected_sources:continue
        core.update_job(jid,'发现最新内容 · '+src['name'],3)
        try:
            data,_,_=asyncio.run(core.fetch(src['url'],2_000_000))
            feed=feedparser.parse(data)
            if not feed.entries:raise ValueError('订阅源没有返回可用内容')
            for e in feed.entries[:40]:
                stamp=calendar.timegm(e.published_parsed) if e.get('published_parsed') else None
                if stamp and now-stamp>config['days']*86400:continue
                if not AI.search(e.get('title','')) and src['priority']<16:continue
                add(e.get('link',''),e.get('title','未命名'),src['name'],stamp,src['priority'])
        except Exception as e:
            core.update_job(jid,src['name']+' 暂不可用：'+core.safe_error(e))
    cache={}
    rendered={}
    core.update_job(jid,'启动 Chromium 浏览器 · 搜索与阅读候选',8)
    with sync_playwright() as p:
        try:
            browser=p.chromium.launch(headless=True)
        except Exception:
            raise ValueError('Chromium 无法启动，请运行 .venv/Scripts/python -m playwright install chromium') from None
        context=browser.new_context(locale='zh-CN',service_workers='block',accept_downloads=False,user_agent='Mozilla/5.0 ArticleFlow/1.0')
        def guard(route):
            try:
                req=route.request
                if req.resource_type in ('image','font','media'):
                    route.abort();return
                if req.resource_type!='document':
                    target_host=urlsplit(req.url).hostname or ''
                    current_host=urlsplit(page.url).hostname or ''
                    if target_host!=current_host and not target_host.endswith('.'+current_host):
                        route.abort();return
                public_url_sync(req.url)
                if req.resource_type=='document' and not robots_allowed(req.url,cache):
                    route.abort();return
                route.continue_()
            except Exception:route.abort()
        context.route('**/*',guard)
        page=context.new_page()
        page.set_default_timeout(8000)
        try:
            query=re.sub(r'[,，]+',' ',config['topics'])+' '+('人工智能 工具 发布' if config['content_type']=='tools' else '人工智能 最新资讯')
            search='https://www.bing.com/news/search?'+urlencode({'q':query,'qft':f'interval="{7 if config["days"]<=7 else 30}"','form':'YFNR','mkt':'zh-CN','setlang':'zh-hans'})
            core.update_job(jid,'浏览器搜索 · '+config['topics'][:65],10)
            try:
                page.goto(search,wait_until='domcontentloaded',timeout=30000)
                for link in page.locator('a.title').all()[:30]:
                    url=link.get_attribute('href') or ''
                    if urlsplit(url).hostname and not urlsplit(url).hostname.endswith('bing.com'):
                        add(url,link.inner_text(),'Bing 新闻搜索')
            except Exception:
                core.update_job(jid,'浏览器搜索暂不可用，继续从行业订阅源发现；不会绕过访问限制')
            candidates.sort(key=lambda x:(x['published'] or 0,x['priority']),reverse=True)
            # Balance sources before the expensive browser pass.
            available=[]
            for c in candidates:
                if c['url'] in previous:
                    c.update(status='skipped',reason='此前已生成文章');continue
                available.append(c)
            pending=reading_order(available,config['candidate_limit'])
            pending_ids={id(x) for x in pending}
            for c in candidates:
                if c['status']=='found' and id(c) not in pending_ids:
                    c.update(status='skipped',reason='本轮浏览预算或来源配额已满')
            persist(jid,candidates)
            for i,c in enumerate(pending):
                core.update_job(jid,f'浏览器阅读 {i+1}/{len(pending)} · {c["title"][:50]}',12+int(i/max(1,len(pending))*33))
                c['status']='reading';persist(jid,candidates)
                try:
                    public_url_sync(c['url'])
                    if not robots_allowed(c['url'],cache):raise ValueError('robots.txt 禁止访问或规则无法确认')
                    response=page.goto(c['url'],wait_until='domcontentloaded',timeout=35000)
                    if response and response.status>=400:raise ValueError(f'网页 HTTP {response.status}')
                    try:page.wait_for_load_state('networkidle',timeout=3500)
                    except Exception:pass
                    raw=page.content()
                    final=public_url_sync(page.url)
                    if canonical(final) in previous:raise ValueError('跳转后的文章此前已生成')
                    original=core.extract(raw,final)
                    c['language']='zh' if is_chinese(original['text']) else 'other'
                    c['title']=original['title']
                    c['published'],c['date_source']=publication(raw,c['published'])
                    original['source_date']=datetime.fromtimestamp(c['published'],timezone.utc).isoformat() if c['published'] else None
                    original['source_url']=final
                    c['score'],c['reason']=score(c,original,config,now)
                    c['status']='eligible' if c['score']>=55 else 'rejected'
                    if c['status']=='rejected' and c['score']>0:c['reason']='评分低于 55；'+c['reason']
                    c['final_url']=final
                    c['word_count']=len(original['text'])
                    c['content_hash']=hashlib.sha256(original['text'].encode()).hexdigest()
                    rendered[c['url']]=(original,final)
                except Exception as e:
                    c.update(status='rejected',reason=core.safe_error(e))
                persist(jid,candidates)
            ranked=selection_order(c for c in candidates if c['status']=='eligible')
            chosen=[];titles=[];hashes=set();domains={}
            for c in ranked:
                domain=urlsplit(c.get('final_url',c['url'])).hostname
                if c['content_hash'] in hashes or near_duplicate(c['title'],titles):
                    c.update(status='rejected',reason='同一内容或高度相似标题，保留更高分来源');continue
                if len(chosen)>=config['limit']:
                    c.update(status='reserve',reason='已达到目标篇数；'+c['reason']);continue
                if c.get('language')!='zh' and domains.get(domain,0)>=max(1,(config['limit']+1)//2):
                    c.update(status='reserve',reason='保持来源多样性，本来源已达入选上限');continue
                domains[domain]=domains.get(domain,0)+1
                c['reason']=('中文正文优先；' if c.get('language')=='zh' else '合格中文候选不足，外文补充（成稿使用简体中文）；')+c['reason']
                c['status']='selected';chosen.append(c);titles.append(c['title']);hashes.add(c['content_hash'])
            persist(jid,candidates)
            core.update_job(jid,f'发现 {len(candidates)} 条 · 浏览 {len(pending)} 条 · 择优入选 {len(chosen)} 条',48)
            return [(c,*rendered[c['url']]) for c in chosen]
        finally:
            context.close()
            browser.close()
