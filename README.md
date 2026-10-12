# ArticleFlow

**简体中文** · [English](README.en.md)

![ArticleFlow 内容工作台](docs/images/dashboard.png)

**让内容发现、整理、改写和发布自动流转。** ArticleFlow 是一个免费开源、本地优先的内容自动化工作台：定时发现 AI 行业资讯与 AI 工具，借助大语言模型整理内容，并将文章发布到 WordPress、将工具网址发布到兼容 OneNav 的导航站点。

项目由「加密社」发起，免费开放代码，方便用户自行部署和改造。我们希望你在体验 ArticleFlow 后，也来访问我们的自动化 AI 工具导航站：[123gpt.cn](https://123gpt.cn)。

> ArticleFlow 是本地运行的软件，不是托管 SaaS。连接配置、任务记录和采集内容默认留在你自己的机器上；自动任务只会在本地服务运行时执行。

## 为什么使用 ArticleFlow

- **从发现到发布自动衔接：** 不用在多个采集、改写和发布工具之间反复搬运内容。
- **自动化可控、进度可见：** 文章和工具导航任务可分别设置执行间隔、主题和开关，并查看实时进度与任务记录。
- **发布目标明确：** 文章可自动发布到 WordPress；工具条目可写入兼容 OneNav 的导航数据库。无需每次手动点击同步。
- **本地优先：** SQLite 保存本机内容与任务历史，连接设置加密保存在本机数据目录。
- **流程可检查：** 保留来源、处理状态和报告，方便追踪失败任务和复核生成结果。
- **免费开源：** 代码可查看、使用和自行修改，MIT 许可证见 [LICENSE](LICENSE)。运行过程中使用的第三方模型 API 可能按服务商规则计费。

## 功能一览

### AI 资讯文章采集与发布

- 从资讯源和浏览器搜索发现文章候选，查看来源与原文。
- 关注 AI 行业新闻、生成式 AI、大模型、智能体、AI 编程、AI 产品与应用等主题；也可以按需调整主题。
- 使用 SiliconFlow 提供的兼容模型 API 进行内容整理与改写，并运行内置 `de-ai-flavor` 检查。
- 在文章库查看采集原文、生成内容、图片、关键词、任务状态和发布结果。
- 配置 WordPress 后，可将成功处理的文章自动发布为已发布状态。

### AI 工具网址采集与导航发布

- 自动发现 AI 工具并生成导航介绍，支持 AI 设计与绘画、AI 视频、AI 音乐、AI 自动化、AI 智能体、AI PPT、AI Excel、AI 写作、AI 编程等主题。
- 采集工具官网信息，生成介绍、分类和标签，并查看处理状态。
- 配置兼容 OneNav 的 MySQL 数据库及 SFTP 图片上传后，可自动写入导航站点并发布。
- 可在 AI 工具导航页面检索和筛选条目、检查站点结构，并查看批量发布状态。

### 定时自动化

- 文章采集与 AI 工具网址采集分别设置，不互相影响。
- 设置执行间隔、每轮处理数量和主题列表。
- 使用清晰的开关开启或关闭任务；开启后立即执行一轮，之后按间隔继续。
- 查看进行中、已完成或部分失败状态、处理进度、最近一次运行和下次计划时间。
- 在采集任务页查看任务日志、失败原因和处理结果；可按需重试。

## 工作流程

### 文章流程

```text
定时搜索与发现 → 获取候选文章和来源 → AI 整理/改写 → 内容检查 → 保存本地记录 → 发布到 WordPress
```

连接和主题配置完成后，自动化任务按设定间隔执行。处理成功的文章可以直接以已发布状态写入 WordPress；生成或发布失败时，任务状态和日志会显示在界面中，便于检查和重试。

### AI 工具网址流程

```text
定时搜索 AI 工具 → 访问并采集官网 → 生成名称、简介和分类 → 校验条目 → 写入导航数据库并发布
```

系统按主题发现 AI 工具，处理官网信息并生成导航条目。配置 MySQL 和 SFTP 后，成功条目自动发布到兼容 OneNav 的导航站点。

## 运行要求

- Windows 10/11（项目当前提供 PowerShell 启动脚本）；其他系统可手动运行 Python 服务。
- Python 3.11 或更高版本。
- Node.js 和 npm，用于运行 `de-ai-flavor` 写作检查工具。
- Playwright Chromium 浏览器。
- **文章改写需要 SiliconFlow API Key。** 可在硅基流动注册并创建 API Key：[硅基流动注册链接](https://cloud.siliconflow.cn/i/ROspRzwK)。请在 ArticleFlow 的「连接设置」中填写 Key，不要把 Key 写进源码或提交到 GitHub。模型/API 服务的可用性与费用以硅基流动当前规则为准。
- 文章发布需要 WordPress 站点及具有文章、媒体权限的账户应用密码。
- AI 导航发布需要兼容 OneNav 的 MySQL 数据库及可用的 SFTP 图片上传配置。

## 快速开始

克隆仓库后，在 Windows PowerShell 运行：

```powershell
git clone https://github.com/Boom-Caoq/articleflow.git
cd articleflow
.\start.ps1
```

首次启动会创建 Python 虚拟环境、安装项目依赖并启动本地服务。打开终端提示的地址（默认 `http://127.0.0.1:8000`）访问应用。

也可以手动安装和启动：

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

安装 `de-ai-flavor` 命令行工具（若环境中尚未提供）：

```sh
npm install -g de-ai-flavor
```

请使用单个 Uvicorn worker。任务队列和调度器在进程内运行，SQLite 按单个本地服务实例配置。

## 首次配置

1. 启动 ArticleFlow 并打开「连接设置」。
2. 填入 SiliconFlow API Key，检测模型连接；文章改写需要此项。
3. 如需发布文章，配置 WordPress HTTPS 地址、用户名和应用密码，并检测连接。
4. 如需发布 AI 工具网址，配置目标 MySQL 数据库和 SFTP 图片上传信息，并检查导航表结构。
5. 在「自动化任务」中设置文章与工具采集主题、执行间隔和每轮数量。
6. 使用开关启用所需任务，查看即时进度；保持本地服务运行以便按计划持续执行。

所有凭证都应通过应用的连接设置在本机配置。不要把真实 API Key、WordPress 密码、数据库连接信息、SFTP 主机/用户名/密码或私钥写入源码、截图、Issue 或公开文档。

## 本地数据与安全

- `data/` 保存本地 SQLite 数据库、加密密钥、连接配置、日志、图片和处理记录，已由 `.gitignore` 排除。
- 加密密钥和加密后的设置位于同一台机器。请限制本机账户访问并妥善备份 `data/`；同时取得这两个文件的人仍可能恢复凭证。
- 应用没有用户登录，服务仅绑定 `127.0.0.1` 并检查本机来源。**不要直接将服务暴露到公网。**
- 采集遵循 `robots.txt`，不会绕过登录、验证码或其他访问限制。请遵守来源网站条款、版权和适用法律，确认你有权转载材料。
- 搜索结果是发现线索，不等于事实核验。发布前请检查来源、事实、改写质量及图片使用权。
- 导航数据通过数据库直接写入，不会运行 WordPress 钩子，也不会自动清理网站或 CDN 缓存；正式发布前建议先在测试站点验证。
- 本地服务停止时定时任务会暂停；服务重启后请检查中断任务状态。
- 如曾将凭证提交到 Git 历史，应轮换对应密钥/密码，并清理历史；只从最新文件删除并不能使旧凭证失效。

## 截图

| 内容工作台 | 采集任务进度 |
| --- | --- |
| ![内容工作台](docs/images/dashboard.png) | ![采集任务列表](docs/images/collection-tasks.png) |

| 自动化任务 | 文章库 |
| --- | --- |
| ![自动化任务设置](docs/images/automations.png) | ![文章库](docs/images/articles.png) |

| AI 工具导航与发布 |
| --- |
| ![AI 工具导航](docs/images/navigation.png) |

## 开发

```sh
python -m pip install -r requirements.txt
python -m pytest -q
```

提交前请确认没有加入 `.venv/`、`data/`、本机环境文件、日志、数据库备份或任何真实凭证。公开仓库前也要检查完整 Git 历史。

## 许可证与鸣谢

ArticleFlow 按 MIT License 开源，版权方为「加密社」。请阅读 [LICENSE](LICENSE) 了解授权条款。项目使用的第三方库、模型和服务均遵循各自的许可证与服务条款。

如果 ArticleFlow 对你的工作有帮助，欢迎访问 [123gpt.cn 自动化 AI 工具导航站](https://123gpt.cn)，发现更多 AI 工具。
