# ArticleFlow

[简体中文](README.md) · **English**

![ArticleFlow content workspace](docs/images/dashboard.png)

**Discover, refine, and publish content in one continuous workflow.** ArticleFlow is a free, open-source, local-first content automation workspace. It finds AI industry news and AI tools on a schedule, uses a language model to prepare content, and publishes articles to WordPress and tool listings to a OneNav-compatible directory site.

ArticleFlow is created by **加密社** and made freely available so people can run and adapt it themselves. We also invite you to visit our automated AI tools directory: [123gpt.cn](https://123gpt.cn).

> ArticleFlow is software that runs on your computer, not a hosted SaaS. Connection settings, task records, and collected content stay in your local data directory by default. Scheduled tasks run only while the local service is running.

## Why ArticleFlow

- **One flow from discovery to publishing:** reduce repetitive copy-and-paste work across collection, rewriting, and publishing tools.
- **Automation you can control and monitor:** set separate schedules, topics, and on/off switches for articles and tool listings, with live progress and task history.
- **Direct publishing targets:** publish successfully processed articles to WordPress and tool listings to a OneNav-compatible directory without manually syncing each item.
- **Local-first storage:** SQLite keeps local content and task history; connection settings are encrypted in the local data directory.
- **Traceable work:** source material, processing status, and reports help you review results and diagnose failed tasks.
- **Free and open source:** inspect, use, and adapt the code under the MIT License in [LICENSE](LICENSE). Third-party model APIs may charge according to their providers' terms.

## Features

### AI news collection and article publishing

- Discover article candidates from feeds and browser search, then review their sources and original text.
- Follow AI industry news, generative AI, language models, agents, AI coding, products, and applications; edit the topics to suit your needs.
- Use a SiliconFlow-compatible model API to organize and rewrite content, then run the included `de-ai-flavor` checks.
- Review source text, generated content, images, keywords, task status, and publishing results in the article library.
- With WordPress configured, automatically publish successfully processed articles with the published status.

### AI tool discovery and directory publishing

- Discover AI products in areas such as design and image generation, video, music, automation, agents, presentations, spreadsheets, writing, and coding.
- Capture official-site information, prepare descriptions, categories, and tags, and track processing results.
- With a compatible OneNav MySQL database and SFTP image upload configured, write and publish listings to the directory site automatically.
- Search and filter listings, inspect the target site structure, and review batch publishing status.

### Scheduled automation

- Configure article and AI tool discovery independently.
- Set the run interval, items per round, and topic list.
- Turn each task on or off with a clear switch. Enabling starts a run immediately; later runs follow the configured interval.
- See in-progress, completed, and partially failed states, progress, last run, and next scheduled run.
- Inspect task logs and failure details in the collection task page and retry when needed.

## How it works

### Article workflow

```text
Scheduled search → discover candidate articles and sources → AI refinement/rewrite → content checks → save locally → publish to WordPress
```

Once the connections and topics are configured, automation runs on the selected interval. Successfully processed articles can be sent to WordPress directly as published posts. Failures appear in task status and logs for review and retry.

### AI tool directory workflow

```text
Scheduled AI tool search → visit and capture official sites → prepare name, description, and category → validate listing → publish to directory database
```

ArticleFlow discovers tools by topic, processes official-site information, and prepares directory entries. Once MySQL and SFTP are configured, successful listings are published automatically to a OneNav-compatible site.

## Requirements

- Windows 10/11 (a PowerShell launcher is included); other systems can start the Python service manually.
- Python 3.11 or newer.
- Node.js and npm for the `de-ai-flavor` writing-check CLI.
- Chromium installed through Playwright.
- **A SiliconFlow API key is required for article rewriting.** Register and create an API key at [SiliconFlow](https://cloud.siliconflow.cn/i/ROspRzwK). Enter the key in ArticleFlow's **连接设置** (Connection Settings); do not put it in source code or commit it to GitHub. Model/API availability and charges are subject to SiliconFlow's current terms.
- WordPress with an application password and permissions to create posts and media for article publishing.
- A OneNav-compatible MySQL database and working SFTP image upload settings for AI directory publishing.

## Quick start

Clone the repository, then run in Windows PowerShell:

```powershell
git clone https://github.com/Boom-Caoq/articleflow.git
cd articleflow
.\start.ps1
```

On first launch, the script creates a Python virtual environment, installs dependencies, and starts the local service. Open the address printed in the terminal (default: `http://127.0.0.1:8000`).

To install and start manually:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Install the `de-ai-flavor` CLI if it is not already available:

```sh
npm install -g de-ai-flavor
```

Use a single Uvicorn worker. The task queue and scheduler are process-local, and SQLite is configured for a single local service instance.

## First-time setup

1. Start ArticleFlow and open **连接设置** (Connection Settings).
2. Enter your SiliconFlow API key and check the model connection. This is required for article rewriting.
3. To publish articles, configure your WordPress HTTPS URL, username, and application password, then check the connection.
4. To publish AI tool listings, configure the target MySQL database and SFTP image upload, then inspect the directory schema.
5. In **自动化任务** (Automations), set article and tool topics, intervals, and items per run.
6. Turn on the tasks you want and monitor live progress. Keep the local service running for scheduled runs.

Enter credentials only through the app's local connection settings. Never put real API keys, WordPress passwords, database connection details, SFTP host/user/password values, or private keys in source code, screenshots, issues, or public documentation.

## Local data and security

- `data/` stores the local SQLite database, encryption key, connection settings, logs, images, and processing records. It is excluded by `.gitignore`.
- The encryption key and encrypted settings are on the same computer. Restrict local account access and back up `data/` securely; anyone who obtains both files may recover the credentials.
- The app has no user login. The service binds to `127.0.0.1` and checks local origins. **Do not expose it directly to the public internet.**
- Collection follows `robots.txt` and does not bypass logins, CAPTCHAs, or other access controls. Follow source-site terms, copyright, and applicable laws, and make sure you have rights to republish material.
- Search results are discovery leads, not fact checks. Review sources, claims, rewrite quality, and image rights before publishing.
- Directory records are written directly to the database. This does not run WordPress hooks or automatically clear site/CDN caches; test on a staging site before production use.
- Scheduled tasks pause when the local service stops. Check interrupted task status after restarting.
- If a credential was committed to Git history, rotate it and clean the history. Removing it only from the latest files does not invalidate the old credential.

## Screenshots

| Content workspace | Collection task progress |
| --- | --- |
| ![Content workspace](docs/images/dashboard.png) | ![Collection tasks](docs/images/collection-tasks.png) |

| Automations | Article library |
| --- | --- |
| ![Automation settings](docs/images/automations.png) | ![Article library](docs/images/articles.png) |

| AI tools directory and publishing |
| --- |
| ![AI tools directory](docs/images/navigation.png) |

## Development

```sh
python -m pip install -r requirements.txt
python -m pytest -q
```

Before committing, make sure `.venv/`, `data/`, local environment files, logs, database backups, and real credentials are excluded. Review the full Git history before making a repository public.

## License and acknowledgements

ArticleFlow is open source under the MIT License, with **加密社** as the copyright holder. Read [LICENSE](LICENSE) for the terms. Third-party libraries, models, and services retain their own licenses and terms.

If ArticleFlow is useful to your workflow, visit [123gpt.cn, our automated AI tools directory](https://123gpt.cn) to discover more tools.
