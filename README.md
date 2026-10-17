# Telegram Team Finder — GCBOT on Render

This repository serves the Telegram Team Finder website on the existing GCBOT Render Web Service.

## Run locally

```bash
python server.py
```

Open `http://localhost:10000`. The `/health` endpoint returns `ok` for Render health checks.

The site is a transparent demo: it validates public Telegram group link syntax but does not query Telegram. A real Telegram bot can request a group's admin list only after it has access to that group. It cannot enumerate every member or verify job titles such as CEO or CTO.
