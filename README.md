# Telegram Team Finder (starter)

A small Telegram bot that reports Telegram-confirmed group administrators and collects possible role clues from messages it receives while running.

## Important Telegram limits

- Revoke the token shared in chat with @BotFather (`/revoke`) and use the replacement privately.
- Add the bot to each group to be checked. Promote it to admin so `getChatAdministrators` can return the admin list. No delete/restrict permissions are needed.
- In @BotFather, use `/setprivacy` and disable privacy for this bot if you want it to receive ordinary group messages. Alternatively, make it an admin (Telegram delivers group messages to admins). Restart the bot after changing this.
- The Bot API does not provide a bot with the group's old message history or a universal member directory. Role clues are collected only from messages delivered while it is running.
- CEO, CTO, founder, team, and moderator mentions are only unverified clues. The verified Telegram admin status is shown separately.
- This demo keeps clue evidence in memory and clears it on restart. It does not silently scan groups from a link; the bot must have access to the group.

## Run locally

Python 3.10+ is recommended.

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN='YOUR_NEW_TOKEN'  # PowerShell: $env:TELEGRAM_BOT_TOKEN='YOUR_NEW_TOKEN'
python bot.py
```

Add the bot to your test group, promote it to admin, and run `/scan` in the group. Test `/help` in a private chat.

Keep the token in your hosting provider's secret/environment-variable settings. Never put it in source code, commit it to Git, or share it in screenshots.

## Deploy from GitHub to Render

1. Create a new **private** GitHub repository, then upload/push the files in this folder to the repository root. Do not commit a `.env` file or any bot token.
2. In Render, choose **New → Blueprint** and connect that GitHub repository. Render will read `render.yaml` and create a background worker.
3. When prompted for `TELEGRAM_BOT_TOKEN`, enter the replacement token you generated with @BotFather. Keep it as a Render secret/environment variable.
4. Deploy. In Render logs, confirm `Bot is running`, then test `/start` and `/scan` in Telegram.

The service is a background worker, so it does not provide a website URL. For a live Telegram bot, this is the appropriate service type. Keep the worker running continuously; if it stops, the bot will not answer until it starts again.
