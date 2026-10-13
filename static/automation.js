const automationNames={articles:'文章采集并发布',navigation:'AI 工具网址采集并发布'};
const automationDefaults={articles:{name:'定时文章采集',topics:'AI行业资讯\n人工智能\n大模型与生成式AI\nAI智能体与自动化\nAI产品发布与融资\nAI研究与开源模型\nAI设计与绘画\nAI视频与音频\nAI编程与开发\nAI办公与效率工具',days:7,content_type:'all',sources:[],limit:5,seo:[],geo:[]},navigation:{topic:'AI设计与绘画\nAI视频生成与剪辑\nAI音乐与音频\nAI自动化工具与智能体\nAI PPT与演示文稿\nAI Excel与数据分析\nAI写作与办公\nAI编程与开发\nAI图像与3D\nAI搜索与知识管理',limit:5,author:1}};
let automationRows=[];
function toggleMarkup(a){return `<div class="automation-toggle-row"><label class="switch"><input name="enabled" type="checkbox" ${a.enabled?'checked':''} aria-label="${a.enabled?'关闭':'开启'}自动化"><span class="switch-track"></span></label><span class="automation-toggle-state ${a.enabled?'on':'off'}">${a.enabled?'已开启':'已关闭'}</span><small class="automation-toggle-hint">${a.enabled?'将按设定间隔自动执行':'当前不会自动执行'}</small></div>`}
function automationCard(a){const c={...automationDefaults[a.kind],...a.config},running=a.status==='running';return `<form class="automation-card" data-automation="${a.kind}" data-saved-enabled="${a.enabled}"><div class="section-head"><h3>${automationNames[a.kind]}</h3><span class="badge ${a.enabled?'completed':'interrupted'}">${a.enabled?'运行中':'已关闭'}</span></div>${toggleMarkup(a)}<div class="form-row"><label>执行间隔（分钟）<input name="interval_minutes" type="number" min="5" max="525600" value="${a.interval_minutes}" required></label><label>每轮数量<input name="limit" type="number" min="1" max="${a.kind==='articles'?50:20}" value="${c.limit}"></label></div>${a.kind==='articles'?`<label>任务名称<input name="name" maxlength="100" value="${esc(c.name)}"></label><label>文章关注主题 <span class="subtle">每行一个，可添加多个</span><textarea name="topics" rows="7" maxlength="1500">${esc(c.topics)}</textarea></label><div class="form-row"><label>内容时效<select name="days">${[1,3,7,30].map(n=>`<option value="${n}" ${Number(c.days)===n?'selected':''}>最近 ${n} 天</option>`).join('')}</select></label><label>内容方向<select name="content_type">${[['all','综合'],['news','行业新闻'],['tools','AI 工具']].map(([v,n])=>`<option value="${v}" ${c.content_type===v?'selected':''}>${n}</option>`).join('')}</select></label></div>`:`<label>AI 工具搜索主题 <span class="subtle">覆盖所有相关工具类别，每行一个</span><textarea name="topic" rows="8" maxlength="1500">${esc(c.topic)}</textarea></label><label>发布作者 ID<input name="author" type="number" min="1" value="${c.author||1}"></label>`}<div class="automation-status" data-automation-live></div><div class="form-actions"><button type="submit" class="primary">保存自动化设置</button><button type="button" class="primary" data-automation-run="${a.kind}" ${running?'disabled':''}>立即运行一次</button></div><p class="subtle">立即运行使用已保存的设置；关闭定时开关时也可以单独运行。每轮结束后按设置间隔执行下一轮。</p></form>`}
const automationStatusNames={queued:'排队中',running:'正在运行',completed:'已完成',partial:'部分失败',failed:'失败',interrupted:'已中断',idle:'等待计划',paused:'已关闭'};
function automationTime(t){return t?new Date(t*1000).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai'}):'尚无记录'}
function automationLive(a){
 if(!a.server_time)return '<p role="alert">当前后端仍是旧版本，请在运行服务的终端按 Ctrl+C，再运行 .\\start.ps1，刷新本页后使用立即运行和日志。</p>';
 const running=a.status==='running',remaining=Math.max(0,Math.ceil((a.next_run-a.server_time)/60));
 const state=running?(a.task_status==='queued'?'排队中':'正在运行'):a.enabled?(a.next_run<=a.server_time?'已到期，等待调度':'等待计划'):'定时已关闭';
 const progress=running&&a.kind==='articles'?`<div class="progress"><span style="width:${Number(a.progress)||0}%"></span></div><small>本轮进度 ${Number(a.progress)||0}%</small>`:'';
 return `<b>${state}</b><p>${running?esc(a.stage):a.enabled?`距下次运行约 ${remaining} 分钟`:'可点击“立即运行一次”执行单次任务'}</p>${progress}<small>上次启动：${automationTime(a.last_run)}（北京时间）</small><small>下次计划：${a.next_run?automationTime(a.next_run):running?'本轮结束后计算':a.enabled?'等待调度':'未启用'}</small>${!running&&a.last_run?`<p>最近一轮：${esc(automationStatusNames[a.task_status||a.status]||a.status)} · ${esc(a.stage)}</p>`:''}${a.error?`<p role="alert">${esc(a.error)}</p>`:''}<details data-automation-logs><summary>运行日志（最近一轮${a.last_task_id?' #'+a.last_task_id:''}）</summary>${(a.logs||[]).map(l=>`<div class="log"><time>${esc(l.time)}</time>${esc(l.message)}</div>`).join('')||'<p>暂无日志；启动后自动刷新。</p>'}</details><small>状态更新：${automationTime(a.server_time)} · 每 2 秒刷新</small>`;
}
async function automationRefresh(force=false){
 try{
  automationRows=await api('/automations');
  if(force||!$('#automation-cards').children.length)$('#automation-cards').innerHTML=automationRows.map(automationCard).join('');
  for(const a of automationRows){
   const form=document.querySelector(`[data-automation="${a.kind}"]`);if(!form)continue;
   const live=form.querySelector('[data-automation-live]'),opened=live.querySelector('details')?.open;
   live.innerHTML=automationLive(a);live.querySelector('details').open=!!opened;
   const badge=form.querySelector('.section-head .badge');badge.textContent=a.status==='running'?(a.task_status==='queued'?'排队中':'正在运行'):a.enabled?'等待计划':'已关闭';
   form.querySelector('[data-automation-run]').disabled=!a.server_time||a.status==='running'||form.dataset.saving==='true';
  }
 }catch(e){toast('自动化状态读取失败：'+e.message)}
}
function automationPayload(form,enabled){const kind=form.dataset.automation,f=form.elements,config={};for(const [k,v] of new FormData(form))config[k]=v;config.limit=Number(f.limit.value);if(kind==='articles'){config.days=Number(f.days.value);config.candidate_limit=20;config.content_type=f.content_type.value}else config.author=Number(f.author.value);return {enabled,interval_minutes:Number(f.interval_minutes.value),config}}
async function automationSave(form,enabled){const input=form.elements.enabled,button=form.querySelector('button.primary');form.dataset.saving='true';input.disabled=true;if(button)button.disabled=true;try{await api('/automations/'+form.dataset.automation,{method:'PUT',body:JSON.stringify(automationPayload(form,enabled))});toast(enabled?'设置已保存，新的运行计划已生效':'自动化已关闭，当前执行中的任务会完成');form.dataset.savedEnabled=String(enabled);input.blur();await automationRefresh(true)}catch(err){input.checked=form.dataset.savedEnabled==='true';const row=form.querySelector('.automation-toggle-row'),state=row.querySelector('.automation-toggle-state'),hint=row.querySelector('.automation-toggle-hint');state.textContent=input.checked?'已开启':'已关闭';state.className='automation-toggle-state '+(input.checked?'on':'off');hint.textContent=input.checked?'将按设定间隔自动执行':'当前不会自动执行';toast(err.message)}finally{form.dataset.saving='false';input.disabled=false;if(button)button.disabled=false}}
document.addEventListener('change',e=>{const input=e.target.closest('[data-automation] input[name="enabled"]');if(!input)return;const row=input.closest('.automation-toggle-row'),state=row.querySelector('.automation-toggle-state'),hint=row.querySelector('.automation-toggle-hint');state.textContent=input.checked?'已开启':'已关闭';state.className='automation-toggle-state '+(input.checked?'on':'off');hint.textContent=input.checked?'正在保存并启动自动执行':'正在保存关闭设置';automationSave(input.closest('form'),input.checked)});
document.addEventListener('submit',async e=>{const form=e.target.closest('[data-automation]');if(!form)return;e.preventDefault();await automationSave(form,form.elements.enabled.checked)});
document.querySelectorAll('nav button').forEach(b=>b.addEventListener('click',()=>{if(b.dataset.view==='automations')automationRefresh()}));
setInterval(()=>{if(current==='automations')automationRefresh()},2000);

document.addEventListener('click',async e=>{
 const button=e.target.closest('[data-automation-run]');if(!button)return;
 button.disabled=true;
 try{await api('/automations/'+button.dataset.automationRun+'/run',{method:'POST',body:'{}'});toast('任务已加入执行队列，可展开运行日志查看进度');await automationRefresh();}
 catch(err){toast(err.message)}finally{await automationRefresh()}
});
