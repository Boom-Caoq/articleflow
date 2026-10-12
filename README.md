# ArticleFlow

**简体中文** · [English](README.en.md)

ArticleFlow 是一个本地优先的内容工作台：发现 AI 行业资讯，使用大语言模型改写并检查内容，然后发布到 WordPress。它也可以发现 AI 工具、生成导航介绍，并写入兼容一为导航（OneNav）的数据库。

界面和主要操作说明为简体中文。服务面向可信的本机环境，不应直接部署到公网。

## 功能

- 从资讯源和浏览器搜索发现 AI 新闻与文章，并查看候选项及原文。
- 使用 SiliconFlow 兼容的对话模型改写内容，并运行内置 `de-ai-flavor` 检查。
- 将原文、草稿、报告、图片和任务记录保存在本地 SQLite 数据库。
- 通过 WordPress REST API 发布文章与媒体。
- 发现 AI 设计、视频、音乐、自动化、智能体、PPT、Excel、编程等类别的工具。
- 通过 MySQL 和 SFTP 发布兼容导航站点的工具条目。
- 为文章和工具发现分别设置定时自动化，控制开启或关闭，并实时查看任务进度。

## 运行要求

- Python 3.11 或更高版本
- Node.js 和 npm（用于 `de-ai-flavor` 命令行工具）
- Playwright Chromium 浏览器
- 可选外部服务：SiliconFlow 兼容 API、WordPress，以及导航发布所需的 MySQL/SFTP

## 快速启动

Windows PowerShell 中运行 `start.ps1`。脚本会创建 `.venv`、安装 Python 依赖并启动本地网站：`http://127.0.0.1:8000`。

也可以手动安装和启动：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

若尚未安装写作检查工具：

```sh
npm install -g de-ai-flavor
```

请使用单个 Uvicorn worker。后台队列和调度器在进程内运行，SQLite 也按单个本地服务实例配置。

## 配置连接

打开应用中的「连接设置」填写凭证。应用会在本机加密保存连接配置；README 和源码不需要填写任何凭证。

- **文章生成：**配置模型 API Key。
- **文章发布：**配置 HTTPS WordPress 地址、用户名和应用密码。
- **AI 导航发布：**配置 MySQL 与 SFTP 图片上传，并在发布前检查目标站点的数据表结构。

启用对应工作流前，请先检测连接。WordPress 用户需要文章和媒体所需的权限。导航发布会直接写入兼容 OneNav 的数据库；用于正式站点前，建议先在非生产环境验证。

## 自动化任务

「自动化任务」页面分别管理文章和 AI 工具网址的定时任务。间隔以分钟设置，主题列表每行一项，可切换开关。首次开启后立即运行一轮，之后按设置的间隔继续执行。需要保持本地服务运行，调度才会生效。

自动采集的文章会经过改写和检查后发布到 WordPress；导航条目会在采集官网并通过内容校验后发布。发布前请检查模型生成的内容，并确认你有权转载相关来源材料。

## 本地数据与密钥

运行数据存放在 `data/`，包括 SQLite 数据库、本机加密密钥、日志、生成图片和处理记录。请勿公开或提交此目录；`.gitignore` 已将其及其他本机运行文件排除。

加密密钥和加密后的配置都存放在同一台机器上。这能降低界面意外泄露的风险，但无法防止拿到这两个文件的人读取凭证。如需保留本机设置和记录，请妥善备份 `data/`。

公开仓库前，请检查完整提交历史和仓库设置中的凭证。如果凭证曾提交过，应先从历史中清除并联系服务提供方轮换；仅从最新文件删除并不能使旧凭证失效。

## 安全与限制

- 服务仅绑定 `127.0.0.1` 并执行本机来源检查。应用没有用户登录，不应直接暴露到公网。
- 采集遵循 `robots.txt`，不会绕过登录、验证码或其他访问限制。
- 搜索结果仅用于发现候选信息，不代表事实核验。发布前应审核生成内容。
- 直接写入导航数据库不会运行 WordPress 钩子，也不会自动清理站点或 CDN 缓存。
- 本地服务停止时自动化也会暂停；重启后中断的任务可能需要重试。

## 开发

安装依赖并运行测试：

```sh
python -m pip install -r requirements.txt
python -m pytest -q
```

不要提交 `.venv/`、`data/`、本机环境文件、日志、凭证或数据库备份。

## 许可证

发布仓库前，请添加你选择的许可证，并检查依赖项和 `skills/de-ai-flavor` 目录中的授权与署名要求。
