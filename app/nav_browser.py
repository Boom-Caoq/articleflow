"""Browser-backed tool discovery and real screenshots (no generated mockups)."""
import base64
import hashlib
import io
import re
from contextlib import contextmanager
from urllib.parse import urljoin,urlsplit,parse_qs,urlencode

from bs4 import BeautifulSoup
from PIL import Image
import httpx
from playwright.sync_api import sync_playwright, Error as BrowserError, TimeoutError as BrowserTimeout
from . import core,discovery
from . import nav_database
from .nav_database import identity


@contextmanager
def browser_page(block_images=False):
    cache={}
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True)
        context=browser.new_context(viewport={'width':1440,'height':960},locale='zh-CN',service_workers='block',accept_downloads=False)
        page=context.new_page()
        def guard(route):
            try:
                req=route.request
                if block_images and req.resource_type in ('image','font','media'):route.abort();return
                discovery.public_url_sync(req.url)
                if req.resource_type in ('media','websocket'):route.abort();return
                if req.resource_type=='document' and not discovery.robots_allowed(req.url,cache):route.abort();return
                route.continue_()
            except Exception:route.abort()
        context.route('**/*',guard)
        try:yield page,cache
        finally:context.close();browser.close()


def visit(page,cache,url):
    discovery.public_url_sync(url)
    if not discovery.robots_allowed(url,cache):raise ValueError('网站禁止采集或 robots.txt 暂时不可读取')
    for attempt in range(2):
        try:
            r=page.goto(url,wait_until='domcontentloaded',timeout=35000)
            break
        except BrowserError as e:
            code=re.search(r'net::(ERR_[A-Z_]+)',str(e))
            reason=('访问官网超时' if isinstance(e,BrowserTimeout) else '浏览器无法访问官网')
            if code:reason+='（'+code.group(1)+'）'
            if attempt:raise ValueError(reason+'，已重试 1 次') from e
    if r and r.status>=400:raise ValueError(f'目标网站 HTTP {r.status}')
    try:page.wait_for_load_state('networkidle',timeout=2500)
    except Exception:pass
    return discovery.public_url_sync(page.url)


def search_link(url):
    p=urlsplit(url)
    if p.hostname and p.hostname.endswith('bing.com'):
        value=parse_qs(p.query).get('u',[''])[0]
        if value.startswith('a1'):
            try:return base64.urlsafe_b64decode(value[2:]+'='*((-len(value[2:]))%4)).decode()
            except Exception:return ''
        return ''
    return url


def download_logo(icons,site_url):
    """Use sync HTTP inside Playwright's sync loop; never nest asyncio.run."""
    stem='nav-'+hashlib.sha256(site_url.encode()).hexdigest()[:20]
    target=core.DATA/'media'/(stem+'-logo.png')
    target.parent.mkdir(exist_ok=True)
    for url in list(dict.fromkeys(icons))[:8]:
        try:
            with httpx.Client(timeout=15,trust_env=False) as client:
                for _ in range(5):
                    discovery.public_url_sync(url)
                    with client.stream('GET',url) as response:
                        if response.is_redirect:
                            url=urljoin(url,response.headers['location']);continue
                        response.raise_for_status();blob=bytearray()
                        for chunk in response.iter_bytes():
                            blob.extend(chunk)
                            if len(blob)>2_000_000:raise ValueError('Logo 图片超过 2 MB')
                        with Image.open(io.BytesIO(blob)) as im:
                            im.load();im.thumbnail((512,512));im.convert('RGBA').save(target)
                        return '/media/'+target.name
        except Exception:continue
    return ''


def discover(topic,limit,log,exclude=None,exclude_titles=None):
    found=[];seen=set(exclude or []);seen_titles=set(exclude_titles or [])
    def add(url,title,source):
        if not url.startswith(('http://','https://')):return
        try:key=identity(url)
        except ValueError:return
        title=title[:300]
        name=nav_database.name_identity(title)
        if key in seen or (name and name in seen_titles):return
        seen.add(key)
        if name:seen_titles.add(name)
        found.append({'url':url,'title':title,'discovered_from':source})
    topics=[x.strip() for x in re.split(r'[,，\n;；]+',topic) if x.strip()]
    if not topics:topics=['AI工具']
    queries=[x+' AI工具 官网' for x in topics[:8]]
    queries.append('人工智能 AI 工具 官方网站 最新产品')
    with browser_page(block_images=True) as (page,cache):
        for query in queries:
            log('浏览器搜索：'+query)
            try:
                visit(page,cache,'https://www.bing.com/search?'+urlencode({'q':query,'mkt':'zh-CN','setlang':'zh-hans'}))
                anchors=page.locator('li.b_algo h2 a').all()
                for a in anchors[:20]:
                    url=search_link(a.get_attribute('href') or '')
                    add(url,a.inner_text(),page.url)
            except Exception as e:log('本次搜索未返回候选：'+core.safe_error(e))
        if len(found)<limit:
            for catalog in ('https://ai-bot.cn/','https://www.aitool6.com/'):
                log('浏览中文 AI 工具目录：'+catalog)
                try:
                    visit(page,cache,catalog)
                    soup=BeautifulSoup(page.content(),'html.parser')
                    for a in soup.select('.url-card a[data-url]'):
                        add(a.get('data-url',''),a.get_text(' ',strip=True),catalog)
                    if len(found)>=limit:break
                except Exception as e:log('工具目录暂不可用：'+core.safe_error(e))
    if not found:raise ValueError('搜索未返回可采集的工具网址，可稍后重试或手动补充官网链接')
    groups=['设计|图像|图片|绘画|绘图|图生|文生图|3D','写作|文章|文案|论文','编程|代码|开发|vibe','办公|文档|表格|Excel|PPT|演示|幻灯片','音乐|音频|声音|语音','视频|短片|剪辑','智能体|agent|自动化|工作流','模型|大模型|搜索|知识管理']
    wanted=[re.compile(g,re.I) for g in groups if re.search(g,topic,re.I)]
    words=[w for w in re.split(r'[\s,，]+',topic) if w.lower() not in ('ai','工具','中文','官网')]
    def relevance(x):return sum(bool(g.search(x['title'])) for g in wanted)*3+sum(w.lower() in x['title'].lower() for w in words)
    found.sort(key=lambda x:(relevance(x),discovery.is_chinese(x['title'])),reverse=True)
    return found[:limit]


def capture(url,log):
    with browser_page() as (page,cache):
        final=visit(page,cache,url)
        log('读取官网介绍与产品信息')
        raw=page.content();soup=BeautifulSoup(raw,'html.parser')
        title=soup.title.get_text(' ',strip=True) if soup.title else urlsplit(final).hostname
        for el in soup.select('script,style,noscript,svg'):el.decompose()
        text=soup.get_text(' ',strip=True)[:22000]
        if len(text)<100:raise ValueError('网页可读取正文不足，可能需要登录或触发访问限制')
        if any(x in title.lower() for x in ('just a moment','access denied','security verification')):raise ValueError('网页被访问验证拦截，请稍后重试')
        links=[]
        for a in soup.select('a[href]'):
            target=urljoin(final,a['href'])
            if target.startswith(('http://','https://')) and urlsplit(target).hostname!=urlsplit(final).hostname:
                links.append({'url':target,'text':a.get_text(' ',strip=True)[:100]})
        links=links[:100]
        icons=[]
        for tag in soup.select('link[rel]'):
            if any('icon' in x.lower() for x in tag.get('rel',[])) and tag.get('href'):
                icons.append(urljoin(final,tag['href']))
        icons.append(urljoin(final,'/favicon.ico'))
        log('截取真实网站预览图')
        directory=core.DATA/'media';directory.mkdir(exist_ok=True)
        stem='nav-'+hashlib.sha256(final.encode()).hexdigest()[:20]
        shot=directory/(stem+'-preview.png')
        page.screenshot(path=str(shot),full_page=False,animations='disabled',timeout=15000)
        logo=download_logo(icons,final)
        if not logo:
            for el in page.locator('header img[alt*="logo" i], header img[src*="logo" i], img[alt*="logo" i]').all()[:5]:
                try:
                    box=el.bounding_box()
                    if not box or box['width']<16 or box['height']<16:continue
                    el.screenshot(path=str(directory/(stem+'-logo.png')),timeout=3000)
                    logo='/media/'+stem+'-logo.png';break
                except Exception:continue
        return dict(url=final,title=title,text=text,links=links,screenshot='/media/'+shot.name,logo=logo,logo_candidates=icons,language='zh' if discovery.is_chinese(text) else 'other')
