import asyncio
import time
import httpx
from . import core

GROUPS={'siliconflow':('api_key','model'),'wordpress':('wp_url','wp_user','wp_password','wp_route'),'database':('db_host','db_name','db_user','db_password')}
SECRETS={'api_key','wp_password','db_password'}

async def probe(group,s):
    if group=='database':
        result=await asyncio.to_thread(core.inspect_database,s)
        if not result['sites']:
            raise ValueError('数据库已连接，但未找到 WordPress 文章表')
        return '数据库连接成功 · '+result['sites'][0]['prefix']
    async with httpx.AsyncClient(timeout=60,trust_env=False) as client:
        if group=='siliconflow':
            if not s['api_key'] or not s['model']:
                raise ValueError('请填写 API Key 和模型 ID')
            r=await client.post('https://api.siliconflow.cn/v1/chat/completions',headers={'Authorization':'Bearer '+s['api_key']},json={'model':s['model'],'messages':[{'role':'user','content':'只回复 OK'}],'max_tokens':16,'stream':False})
            if r.is_error:
                raise ValueError(f'模型调用失败 HTTP {r.status_code}，请检查密钥、模型或余额')
            data=r.json()
            if not data.get('choices'):
                raise ValueError('模型未返回有效结果')
            return 'API Key 与模型调用成功'
        if not all(s[k] for k in ('wp_url','wp_user','wp_password')):
            raise ValueError('请填写 WordPress 网址、用户名和应用密码')
        base=(await core.public_url(s['wp_url'])).rstrip('/')
        if not base.startswith('https://'):
            raise ValueError('WordPress 凭证检测要求 HTTPS')
        params={'context':'edit'}
        endpoint=base+'/wp-json/wp/v2/users/me'
        if s['wp_route']=='query':
            endpoint=base+'/'
            params['rest_route']='/wp/v2/users/me'
        r=await client.get(endpoint,params=params,auth=(s['wp_user'],s['wp_password']))
        if r.is_error:
            raise ValueError(f'WordPress 登录检测失败 HTTP {r.status_code}')
        data=r.json()
        caps=data.get('capabilities',{})
        if not data.get('id') or not all(caps.get(k) for k in ('edit_posts','upload_files','manage_categories')):
            raise ValueError('已连接，但该用户缺少文章、媒体上传或分类管理权限')
        return 'WordPress 登录及文章、媒体、分类权限通过'

async def verify(group,values):
    if group not in GROUPS:
        raise ValueError('未知连接类型')
    if not isinstance(values,dict):
        raise ValueError('配置必须为对象')
    candidate=core.settings().copy()
    for key in GROUPS[group]:
        if key in values:
            if not isinstance(values[key],str) or len(values[key])>2000:
                raise ValueError('配置字段无效')
            if values[key] or key not in SECRETS:
                candidate[key]=values[key].strip()
    if candidate['wp_route'] not in ('query','pretty'):
        raise ValueError('WordPress 接口模式无效')
    try:
        message=await probe(group,candidate)
    except Exception as e:
        return dict(ok=False,message=core.safe_error(e),checked_at=time.time())
    # Merge only this verified group, preserving concurrent changes to other groups.
    states=core.settings().get('connection_checks',{}).copy()
    state=dict(ok=True,message=message,checked_at=time.time())
    states[group]=state
    core.save_settings({k:candidate[k] for k in GROUPS[group]} | {'connection_checks':states})
    return state
