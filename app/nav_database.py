"""OneNav direct SQL adapter. No REST publishing and no WordPress plugin."""
import hashlib
import re
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, quote
from zoneinfo import ZoneInfo

import pymysql
from . import core


def identity(url):
    p=urlsplit(url.strip())
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:
        raise ValueError('请输入有效的 HTTP/HTTPS 官网链接')
    host=p.hostname.lower().removeprefix('www.')
    if p.port not in (None,80,443):host+=':'+str(p.port)
    query=sorted((k,v) for k,v in parse_qsl(p.query) if not k.lower().startswith('utm_') and k.lower() not in ('ref','from','fbclid','gclid'))
    return urlunsplit(('',host,p.path.rstrip('/') or '/',urlencode(query),''))


@contextmanager
def connection():
    s=core.settings()
    c=pymysql.connect(host=s['db_host'],user=s['db_user'],password=s['db_password'],database=s['db_name'],charset='utf8mb4',connect_timeout=10,read_timeout=25,write_timeout=25,autocommit=False,cursorclass=pymysql.cursors.DictCursor)
    try:yield c
    finally:c.close()


def schema(q):
    q.execute('SHOW TABLES')
    tables={next(iter(x.values())) for x in q.fetchall()}
    matches=[]
    for table in tables:
        if not table.endswith('_options') or not re.fullmatch(r'[A-Za-z0-9_]+',table):continue
        prefix=table[:-7]
        if not all(prefix+x in tables for x in ('posts','postmeta','terms','term_taxonomy','term_relationships','users')):continue
        q.execute(f"SELECT option_name,option_value FROM `{table}` WHERE option_name IN ('home','siteurl','timezone_string','gmt_offset')")
        opts={x['option_name']:x['option_value'] for x in q.fetchall()}
        desired=core.settings().get('wp_url','').rstrip('/')
        if not desired or desired in (opts.get('home','').rstrip('/'),opts.get('siteurl','').rstrip('/')):matches.append((prefix,opts))
    if len(matches)!=1:raise ValueError('无法唯一确定 WordPress 表前缀，请检查数据库与站点网址是否对应')
    prefix,opts=matches[0]
    q.execute(f"SELECT COUNT(*) AS n FROM `{prefix}term_taxonomy` WHERE taxonomy='favorites'")
    if not q.fetchone()['n']:raise ValueError('未找到一为导航 favorites 分类，请确认目标站点')
    return prefix,opts


def taxonomy(q,prefix):
    q.execute(f"SELECT t.term_id,t.name,tt.parent,tt.taxonomy FROM `{prefix}terms` t JOIN `{prefix}term_taxonomy` tt ON t.term_id=tt.term_id WHERE tt.taxonomy IN ('favorites','sitetag') ORDER BY tt.parent,t.term_id")
    return q.fetchall()


def existing(q,prefix):
    q.execute(f"SELECT p.ID,p.post_title,p.post_status,m.meta_value AS url FROM `{prefix}posts` p JOIN `{prefix}postmeta` m ON p.ID=m.post_id WHERE p.post_type='sites' AND p.post_status NOT IN ('trash','auto-draft') AND m.meta_key='_sites_link'")
    return q.fetchall()


def inspect():
    with connection() as c,c.cursor() as q:
        p,opts=schema(q)
        q.execute(f"SELECT ID,user_login,display_name FROM `{p}users` ORDER BY ID LIMIT 100")
        authors=q.fetchall()
        terms=taxonomy(q,p)
        sites=existing(q,p)
    return dict(prefix=p,site=opts.get('home'),categories=[x for x in terms if x['taxonomy']=='favorites'],tags=[x for x in terms if x['taxonomy']=='sitetag'],authors=authors,existing=sites)


def wp_dates(opts):
    now=datetime.now(timezone.utc)
    try:tz=ZoneInfo(opts['timezone_string']) if opts.get('timezone_string') else timezone(timedelta(hours=float(opts.get('gmt_offset') or 0)))
    except (ValueError,KeyError):raise ValueError('WordPress 时区配置无效')
    return now.astimezone(tz).strftime('%Y-%m-%d %H:%M:%S'),now.strftime('%Y-%m-%d %H:%M:%S')


def term(q,p,name,tax):
    q.execute(f"SELECT tt.term_taxonomy_id,tt.term_id FROM `{p}term_taxonomy` tt JOIN `{p}terms` t ON t.term_id=tt.term_id WHERE tt.taxonomy=%s AND t.name=%s ORDER BY t.term_id LIMIT 1",(tax,name))
    row=q.fetchone()
    if row:return row['term_taxonomy_id']
    slug='af-'+hashlib.sha256((tax+':'+name).encode()).hexdigest()[:24]
    q.execute(f"INSERT INTO `{p}terms` (name,slug,term_group) VALUES (%s,%s,0)",(name,slug))
    tid=q.lastrowid
    q.execute(f"INSERT INTO `{p}term_taxonomy` (term_id,taxonomy,description,parent,count) VALUES (%s,%s,'',0,0)",(tid,tax))
    return q.lastrowid


def publish(item,media,author,status):
    """Single transaction under an advisory lock. Retries recover a committed record."""
    if status not in ('draft','publish'):raise ValueError('发布状态无效')
    data=item['data'];key=hashlib.sha256(identity(data['url']).encode()).hexdigest()
    with connection() as c,c.cursor() as q:
        p,opts=schema(q)
        q.execute('SELECT GET_LOCK(%s,15) AS acquired',('articleflow-nav-'+hashlib.sha256((core.settings()['db_name']+p).encode()).hexdigest()[:32],))
        if q.fetchone()['acquired']!=1:raise ValueError('其他导航正在发布，请稍后重试')
        # End any read snapshot established by schema discovery before taking the lock.
        c.commit()
        try:
            q.execute('SELECT TABLE_NAME,ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE()')
            engines={x['TABLE_NAME']:x['ENGINE'] for x in q.fetchall()}
            if any(engines.get(p+t)!='InnoDB' for t in ('posts','postmeta','terms','term_taxonomy','term_relationships')):
                raise ValueError('导航关联表必须使用 InnoDB 才能保证事务回滚')
            q.execute(f"SELECT ID FROM `{p}users` WHERE ID=%s",(author,))
            if not q.fetchone():raise ValueError('所选作者不存在')
            q.execute(f"SELECT p.ID,p.post_status FROM `{p}posts` p JOIN `{p}postmeta` m ON p.ID=m.post_id WHERE m.meta_key='_articleflow_nav_key' AND m.meta_value=%s AND p.post_type='sites'",(key,))
            prior=q.fetchone()
            if prior:
                if prior['post_status']=='trash':raise ValueError('此前发布的网址已在回收站，请先在 WordPress 中处理')
                return dict(id=prior['ID'],url=opts['home'].rstrip('/')+'/?post_type=sites&p='+str(prior['ID']),recovered=True,status=prior['post_status'])
            for old in existing(q,p):
                try:duplicate=identity(old['url'])==identity(data['url'])
                except ValueError:continue
                if duplicate:raise ValueError(f'站点已收录该网址（ID {old["ID"]}），已停止重复发布')
            local,gmt=wp_dates(opts)
            cols=['post_author','post_date','post_date_gmt','post_content','post_title','post_excerpt','post_status','comment_status','ping_status','post_name','to_ping','pinged','post_modified','post_modified_gmt','post_content_filtered','post_type','guid']
            values=[author,local,gmt,core.clean(data['content_html']),data['title'],data['summary'],status,'open','closed','articleflow-tool-'+key[:20],'','',local,gmt,'','sites','']
            q.execute(f"INSERT INTO `{p}posts` ({','.join(cols)}) VALUES ({','.join(['%s']*len(cols))})",values)
            pid=q.lastrowid;url=opts['home'].rstrip('/')+'/?post_type=sites&p='+str(pid)
            q.execute(f'UPDATE `{p}posts` SET guid=%s WHERE ID=%s',(url,pid))
            metadata={'_articleflow_nav_key':key,'_sites_type':'sites','_sites_link':data['url'],'_sites_sescribe':data['summary'],'_thumbnail':media['logo'],'_sites_preview':media['screenshot'],'_sites_order':'0','_user_purview_level':'all','sidebar_layout':'default','_seo_title':data['title'],'_seo_desc':data['summary'],'_seo_metakey':','.join(data['tags'])}
            q.executemany(f'INSERT INTO `{p}postmeta` (post_id,meta_key,meta_value) VALUES (%s,%s,%s)',[(pid,k,v) for k,v in metadata.items()])
            tids=set()
            for tax,names in [('favorites',data['categories']),('sitetag',data['tags'])]:
                for name in names:tids.add(term(q,p,name,tax))
            q.execute(f"SELECT tt.term_taxonomy_id FROM `{p}term_taxonomy` tt JOIN `{p}terms` t ON t.term_id=tt.term_id WHERE tt.taxonomy='content_visibility' AND t.name='所有人可见' LIMIT 1")
            visibility=q.fetchone()
            if visibility:tids.add(visibility['term_taxonomy_id'])
            for tid in tids:
                q.execute(f'INSERT INTO `{p}term_relationships` (object_id,term_taxonomy_id,term_order) VALUES (%s,%s,0)',(pid,tid))
                q.execute(f"UPDATE `{p}term_taxonomy` SET count=(SELECT COUNT(DISTINCT r.object_id) FROM `{p}term_relationships` r JOIN `{p}posts` s ON s.ID=r.object_id WHERE r.term_taxonomy_id=%s AND s.post_status='publish') WHERE term_taxonomy_id=%s",(tid,tid))
            c.commit()
            return dict(id=pid,url=url,status=status,recovered=False)
        except Exception:
            c.rollback();raise
        finally:
            q.execute('SELECT RELEASE_LOCK(%s)',('articleflow-nav-'+hashlib.sha256((core.settings()['db_name']+p).encode()).hexdigest()[:32],))
