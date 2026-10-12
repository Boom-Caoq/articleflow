# ArticleFlow

[简体中文](README.md) · **English**

ArticleFlow is a local-first content workflow for discovering AI industry articles, rewriting and reviewing them with an LLM, and publishing approved results to WordPress. It also discovers AI products, prepares directory listings, and can publish them to a compatible OneNav database.

The interface and documentation are primarily in Simplified Chinese. The service is intended for a trusted local computer, not direct public hosting.

## Features

- Discover recent AI news and articles from feeds and browser search, then review candidates and source material.
- Rewrite content with a configured SiliconFlow-compatible chat completion API and run the included `de-ai-flavor` checks.
- Keep source text, drafts, reports, images, and task history in a local SQLite database.
- Publish articles and media through the WordPress REST API.
- Find AI tools across design, video, music, automation, agents, presentations, spreadsheets, coding, and other categories.
- Publish compatible directory listings through MySQL and SFTP.
- Configure independent interval-based automations for article and tool discovery, with enable/disable controls and live task progress.

## Requirements

- Python 3.11 or newer
- Node.js and npm, for the `de-ai-flavor` CLI
- Chromium installed through Playwright
- Optional external services: a SiliconFlow-compatible API, WordPress, and MySQL/SFTP for directory publishing

## Quick start

On Windows, run `start.ps1` from PowerShell. The script creates `.venv`, installs Python dependencies, and starts the local web app at `http://127.0.0.1:8000`.

For a manual setup:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m playwright install chromium
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Install the writing CLI if it is not already available:

```sh
npm install -g de-ai-flavor
```

Use a single Uvicorn worker. The queues and scheduler are process-local and SQLite is configured for a single local service instance.

## Configure connections

Open **连接设置** in the app and enter credentials there. The app encrypts saved connection settings on the local machine. Credentials are not read from this README or required in source files.

- **Article generation:** configure the model API key.
- **Article publishing:** configure an HTTPS WordPress URL, username, and application password.
- **AI directory publishing:** configure the MySQL connection and SFTP image-upload settings, then inspect the target site's schema before publishing.

Run each connection check before enabling the corresponding workflow. Use a WordPress account with the required post and media permissions. The directory publisher writes to a OneNav-compatible schema directly; test with a non-production database before using it on a live site.

## Automations

The **自动化任务** page has separate schedules for articles and AI tool listings. Set an interval in minutes, edit the topic list (one topic per line), and switch each automation on or off. The first run starts immediately after enabling; later runs follow the configured interval. The local service must remain running for schedules to execute.

Automated articles are rewritten and checked before being published to WordPress. Directory listings are published only after the official site has been captured and the listing passes validation. Review model-generated content and verify that you have permission to republish source material.

## Data and secrets

Runtime data is stored in `data/`, including the SQLite database, local encryption key, logs, generated images, and processing artifacts. Keep this directory private and out of source control. The `.gitignore` excludes it and other local runtime files.

The encryption key and encrypted settings are stored on the same machine. This protects against accidental disclosure in the UI; it does not protect credentials if someone obtains both files. Back up `data/` securely if you need to preserve local settings and history.

Before publishing a fork, check the full commit history and repository settings for credentials. If a credential was ever committed, remove it from history and rotate it with the provider; deleting it from the latest version alone does not make the old value safe.

## Safety and limitations

- The server binds to `127.0.0.1` and includes a local-origin check. It has no user login and should not be exposed directly to the public internet.
- Collection follows `robots.txt` and does not bypass login pages, CAPTCHAs, or other access controls.
- Search results are discovery leads, not fact verification. Generated content should be reviewed before publication.
- Direct database publishing does not run WordPress hooks or automatically clear site/CDN caches.
- Automation pauses when the local service is stopped; interrupted work may need a retry after restart.

## Development

Install the development dependencies and run the test suite:

```sh
python -m pip install -r requirements.txt
python -m pytest -q
```

Do not commit `.venv/`, `data/`, local environment files, logs, credentials, or database dumps.

## License

Add the license you intend to use before publishing this repository. Review the license and attribution requirements for bundled dependencies and the `skills/de-ai-flavor` directory.
