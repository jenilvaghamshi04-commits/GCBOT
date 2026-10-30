# Render deployment

Select branch community-guardian-render in repository jenilvaghamshi04-commits/GCBOT.
Create a Background Worker (not a Web Service or Static Site).
Root directory: community-guardian
Runtime: Python
Build: python -m unittest -q
Start: python -u bot.py
Instances: 1
Environment: BOT_TOKEN (secret; enter privately), DB_PATH=/var/data/guardian.sqlite3
Persistent disk: mount /var/data; size 1 GB.
Use Python 3.11 or newer. This worker and disk incur Render charges; review the displayed price before deploying.

For Blueprint deployment, select community-guardian/render.yaml as the Blueprint path. This does not use the repository's root render.yaml, which belongs to an existing website.

Stop every local or previously hosted copy using this token before starting the worker. Rotate the token previously pasted in chat using BotFather, then use the new token in Render only. Never commit .env, tokens, database files, or PRIVATE ZIPs.

Successful startup logs show Started @SpamLFlabs_bot. Send /help in Telegram; test repeat deletion with a regular member. Admins are exempt. Check Delete Messages permission. The bot runs without a public website URL.
