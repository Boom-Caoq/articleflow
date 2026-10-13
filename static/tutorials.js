/* 右侧悬浮操作教程：每个页面独立，Windows/Linux 双版本 */
const PAGE_GUIDES = {
overview: {
  title: '工作台',
  intro: '工作台是总览页，不需要配置。看四个数字就能知道整个系统状态：已生成、正在进行、已同步、关键词覆盖率。',
  steps: [
    ['看懂状态数字', ['已生成文章：已完成改写、可以发布的文章数', '正在进行：正在采集或改写的任务数', '已同步 WordPress：已经发布成功的文章数', '关键词覆盖率：SEO / GEO 关键词在正文中的命中比例']],
    ['开始第一个任务', '点击「开始你的第一个任务」，会自动跳到采集任务页。首次使用建议先完成「连接设置」再创建任务。'],
    ['查看动态与文章', ['任务动态：最近任务的状态和日志入口', '最近入库：刚采集到的文章，点卡片可以预览']]
  ]
},
jobs: {
  title: '采集任务',
  intro: '创建采集任务会自动搜索 AI 行业的中文资讯、阅读候选网页、评分择优并入库。没有配置 API Key 也可以采集，原文先进文章库。',
  steps: [
    ['新建自动发现任务', ['点击「＋ 新建采集任务」', '采集方式选「自动发现 · 浏览器搜索与择优」', '填主题（中文，如：DeepSeek 大模型、AI 编程工具），选内容方向和时间范围', '设定「择优生成篇数」，点击创建']],
    ['新建手动采集任务', ['采集方式选「手动补充 · 文章链接」', '每行粘贴一个文章网址，或使用「列表页面」模式并填写 CSS 选择器（如 article a[href]）', '创建后逐条采集，重复链接自动去重']],
    ['查看进度与候选', ['任务卡片显示进度条和当前阶段；「查看日志」看每步明细', '「发现与选题」查看候选文章：已入选的会进入文章库']],
    ['Windows 注意', '采集浏览器来自本机 Chromium；首次使用若提示浏览器未安装，运行 .venv\\Scripts\\python -m playwright install chromium'],
    ['Linux 注意', '运行 python3 -m playwright install chromium 安装浏览器后重启服务']
  ]
},
articles: {
  title: '文章库',
  intro: '文章库存放采集原文与成稿。流程：查看原文 → 执行 Skill 改写 → 下载封面配图 → 同步 WordPress。缺少 Key 时原文会一直保留。',
  steps: [
    ['查看采集原文', '点文章卡片打开预览：左侧显示正文，下方可展开「保留的采集原文」核对来源。'],
    ['执行 Skill 改写', ['先到「连接设置」确认硅基流动 API Key 是绿灯', '点「执行 Skill 改写」：DS 初稿 → 本地 de-ai-flavor 质检 → 修订 → 封面图', '改写完成后状态变为「已改写 · 待同步」', '质检不通过会停止自动同步，不会发布半成品']],
    ['同步 WordPress', ['确认连接设置里 WordPress 是绿灯（应用密码已保存）', '点「继续至 WordPress」或「同步到 WordPress」', '按连接设置的发布状态执行：草稿或直接发布', '同步失败会保留错误，重试即可']],
    ['Windows 注意', 'WordPress 应用密码在后台「用户 → 个人资料 → 应用密码」生成，不要填登录密码'],
    ['Linux 注意', '若前台没有新文章，清理 Redis/页面缓存；同步走 API 不受服务器系统影响']
  ]
},
navigation: {
  title: 'AI 工具导航',
  intro: '自动发现 AI 工具、核实官网、生成中文介绍与真实截图，最后把网址、分类、标签直接写入一为导航数据库。图片通过 SFTP 上传，不使用 WordPress API。',
  steps: [
    ['首次：检测站点结构', '点「检测站点结构」：确认连上的是 example.com、读取到已有分类（favorites）、标签（sitetag）和发布作者。'],
    ['配置 SFTP（Windows 服务器）', ['服务器启用 OpenSSH：PowerShell 执行 Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0', 'Start-Service sshd；Set-Service -Name sshd -StartupType Automatic', '放行 22 端口：New-NetFirewallRule -Name sshd -DisplayName sshd -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22', '展开网页里的「SFTP 图片上传设置」：主机填公网 IP，用户=Windows 登录账号，密码=该账号密码，上传目录=C:/wwwroot/example.com/wp-content/uploads，公开 URL=https://example.com/wp-content/uploads', '首次检测显示 SSH 指纹，点「已核对，信任此指纹并检测」']],
    ['配置 SFTP（Linux 服务器）', ['面板开启 SSH，创建 SFTP 子账号或使用 root', '开放 22 端口：firewall-cmd --permanent --add-port=22/tcp && firewall-cmd --reload', '上传目录=/www/wwwroot/example.com/wp-content/uploads，公开 URL=https://example.com/wp-content/uploads', '指纹用 ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub 核对']],
    ['发现与生成', ['点「＋ 发现 AI 工具」输入主题，浏览器搜索并核实官网，采集真实截图与 Logo', '也可以展开「手动补充工具官网」直接粘贴网址', '生成一句话介绍、详细介绍、分类（1-2 个）和标签（2-5 个）']],
    ['预览编辑与发布', ['点「预览 / 编辑」检查内容，可修改分类、标签和详细介绍', '选择「草稿」或「直接发布」，点「发布此网址」或勾选后「一键发布所选」', '发布时先 SFTP 上传截图和 Logo，再事务写入数据库；前台没更新就清理缓存']],
    ['常见问题', ['AuthenticationException：SFTP 账号或密码错误，用 Windows 登录密码再试', '指纹不一致：先核对服务器公钥，不要跳过确认', '分类没显示：新分类需要主题前台启用']]
  ]
},
settings: {
  title: '连接设置',
  intro: '所有外部连接都在这里检测并保存。检测成功才会保存（绿点），失败不保存（红点）。密码类留空表示保留已保存的密码。',
  steps: [
    ['硅基流动 API Key', ['到硅基流动控制台复制 sk- 开头的 API Key', '模型保持 deepseek-ai/DeepSeek-V4-Flash', '点「检测并保存」：绿灯=Key 和模型可用，红灯=Key 错或余额不足']],
    ['WordPress', ['站址填 https://example.com，不带 /wp-admin', '用户名=登录用户名，密码=应用密码（后台个人资料生成）', 'REST 入口选「兼容模式 ?rest_route=（按站点实际配置）」', '检测通过=WordPress 登录及文章、媒体、分类权限通过']],
    ['MySQL 数据库', ['填主机、库名、用户名和密码（面板里的完整密码）', '点「检测并保存」：读到 WordPress 表前缀 = 绿灯', '失败检查：3306 是否放行、账号是否有远程权限、密码是否带特殊字符']],
    ['发布偏好', '选「草稿」先在后台审核，或选「直接发布」；勾选自动同步后，文章生成完成会自动同步。']
  ]
},
skill: {
  title: '写作 Skill',
  intro: '这里配置的是你指定的 de-ai-flavor 写作风格参数，并把本地全局包的真实运行状态展示出来。改写在文章库执行。',
  steps: [
    ['确认本地包已安装', '页面顶部显示「已安装 de-ai-flavor vX」说明自动改写可执行；若未安装，先运行 npm install -g de-ai-flavor。'],
    ['调整写作配置', ['在 JSON 配置里调整角色、风格、口语程度等参数', '不要删除配置结构；修订次数保持 1-3', '点「保存写作配置」，只影响之后生成的文章']],
    ['查看质检结果', '文章预览里可展开「本地质检报告」查看命中规则：规则通过才允许发布。']
  ]
}
};
(function(){
const esc = (v)=>String(v==null?'':v).replace(/[&<>"\']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"\'":'&#39;'}[c]));
let guideOs = localStorage.getItem('articleflow.guide.os') || 'win';
function osName(){ return guideOs === 'linux' ? 'linux' : 'win'; }
function renderGuideBody(view, os){
  const g = PAGE_GUIDES[view]; if(!g) return '';
  const blocks = g.steps.map(step=>{
    const lines = Array.isArray(step[1]) ? step[1].map(x=>`<li>${esc(x)}</li>`).join('') : `<li>${esc(step[1])}</li>`;
    return `<div class="tutorial-block"><h3>${esc(step[0])}</h3><ul>${lines}</ul></div>`;
  }).join('');
  return `<p class="tutorial-note">${esc(g.intro)}</p>${blocks}`;
}
function openTutorial(){
  const view = document.querySelector('nav button.active')?.dataset.view || 'overview';
  const overlay = document.getElementById('tutorial-overlay');
  const body = document.getElementById('tutorial-panel-body');
  const title = document.getElementById('tutorial-panel-title');
  if(!overlay || !body || !title) return;
  title.textContent = PAGE_GUIDES[view]?.title || '操作教程';
  body.innerHTML = renderGuideBody(view, osName());
  document.querySelectorAll('#tutorial-overlay .tutorial-platform button').forEach(b=>b.classList.toggle('active', b.dataset.os === osName()));
  overlay.classList.remove('hidden');
  overlay.setAttribute('aria-hidden','false');
}
function closeTutorial(){
  const overlay = document.getElementById('tutorial-overlay');
  if(!overlay) return;
  overlay.classList.add('hidden');
  overlay.setAttribute('aria-hidden','true');
}
document.getElementById('tutorial-trigger')?.addEventListener('click', ()=>{ openTutorial(); });
document.addEventListener('mouseover', e=>{
  const overlay = document.getElementById('tutorial-overlay');
  if(e.target.closest && e.target.closest('#tutorial-trigger') && overlay && overlay.classList.contains('hidden')) openTutorial();
});
document.getElementById('tutorial-overlay')?.addEventListener('click', e=>{
  if(e.target.closest('[data-close-tutorial]')) closeTutorial();
});
document.querySelector('.tutorial-backdrop')?.addEventListener('click', ()=>closeTutorial());
document.querySelectorAll('#tutorial-overlay .tutorial-platform button').forEach(b=>
  b.addEventListener('click', ()=>{ guideOs = b.dataset.os; localStorage.setItem('articleflow.guide.os', guideOs);
    document.querySelectorAll('#tutorial-overlay .tutorial-platform button').forEach(x=>x.classList.toggle('active', x===b));
    const view = document.querySelector('nav button.active')?.dataset.view || 'overview';
    document.getElementById('tutorial-panel-body').innerHTML = renderGuideBody(view, osName());
  }));
document.addEventListener('keydown', e=>{ if(e.key==='Escape') closeTutorial(); });
})();
