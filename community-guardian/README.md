# Community Guardian — v1.1

An independent Telegram group moderation bot inspired by common Rose features.
Not affiliated with Rose. Source code included. Python 3.11+; no packages needed.

## Start on Mac, Windows, or Linux

1. In Telegram open the verified @BotFather, send `/newbot`, and choose your bot name and username.
2. Install Python 3.11 or newer from https://www.python.org/downloads/.
3. Extract this ZIP. Open Terminal in the extracted `community-guardian` folder.
4. Copy `.env.example` to `.env`. Mac/Linux: `cp .env.example .env`; Windows PowerShell: `Copy-Item .env.example .env`.
5. Open `.env` in a text editor and replace the token placeholder with the NEW token from BotFather. Do not put the token into code, GitHub, screenshots, or a group chat. Revoke previously exposed tokens using BotFather.
6. Run `python3 bot.py` (Windows: `py bot.py`). Keep this terminal and computer running. Control+C stops it.
7. Add your new bot to your Telegram supergroup and promote it to admin. Grant Delete Messages and Ban/Restrict Members. Human admins who change settings need Change Group Info; moderation commands need Ban/Restrict Members. Anonymous-admin commands are intentionally ignored; send from your own account.
8. Send `/help` inside your group. Test with a separate regular-member account before enabling restrictions for everyone.

Moderation requires a supergroup. Telegram bots added as administrators can receive ordinary group messages. If messages do not reach the bot, check BotFather privacy settings and re-add the bot after changing them. The bot handles new messages and edits. It does not scan historical messages.

## Recommended initial setup

Send each line separately as an admin:

```
/setrules Be respectful. No spam, scams, or unsolicited promotions. Admins never request your seed phrase.
/setwelcome Welcome {name} to {group}! Read /rules and use website for our official links.
/filter website | https://YOUR-WEBSITE.com
/filter support | Contact only the official admins listed in the group information.
/warnlimit 3
/flood on
/links off
/captcha on
```

`/links on` deletes ALL detected links from ordinary members, including legitimate ones. Start with it off if community members need to share links. Admins are exempt from spam filters.

## Commands

Everyone: `/help`, `/rules`, `/id`.

Admin settings:
- `/setrules text`, `/setwelcome text` (placeholders `{name}` and `{group}`).
- `/filter keyword | reply`: exact, case-insensitive message match. `/unfilter keyword` removes it.
- `/blockword phrase`, `/unblockword phrase`: case-insensitive phrase boundaries; inspect `/settings` for the list.
- `/links on|off`, `/flood on|off`, `/captcha on|off`.
- `/warnlimit 3` (1–20); `/settings` displays settings.

Reply to a member's message to use:
- `/warn`, `/warnings`, `/resetwarns`.
- `/mute 30` (minutes; default 60; accepted 1–43200).
- `/unmute`, `/ban`, `/kick`, `/unban`.

At the warning limit, the member is muted for 60 minutes and their warnings reset.
Flood protection deletes the sixth message within ten seconds and mutes the sender for five minutes. Blocked phrases and prohibited links cause message deletion without an automatic warning. Administrators and bots are protected from manual moderation.

## Verification behavior

Disabled until `/captcha on`. New human members are muted and given 120 seconds to click their own verification button. Buttons are bound to a member, group, message, and random nonce. A different user cannot verify for them. This is a simple join check, NOT strong proof of humanity.

Expired verification temporarily bans/removes the member for 60 seconds; they can try joining again afterward. The deadline is checked approximately every 10–15 seconds while the process runs. Pending checks persist across restarts. If the bot is offline, no deadline action occurs until restart; the initial mute expires after three minutes as a fallback. Successful verification restores the current default group permissions. Admin `/unmute` cancels pending verification.

## Keep it online

Local: computer, terminal, and internet must stay on. No claim of hosted or free 24/7 operation is included.
Docker: with Docker installed, run `docker compose up -d --build`; view logs with `docker compose logs -f`. The named volume retains settings/warnings/pending checks. `docker compose down` stops it without deleting the volume.

VPS/worker hosting: use `python -u bot.py` as a background worker, set BOT_TOKEN privately, and put DB_PATH on a persistent disk. This is a long-polling worker, not an HTTP website. Run only ONE process per token and SQLite database. A pre-existing webhook must be removed deliberately before polling; the bot will refuse to overwrite it.

## Data and limitations

SQLite stores group IDs, settings, warning counts, pending verification IDs/deadlines, and update offsets. It does not archive chat history. Flood timestamps are temporary memory. Back up the data folder privately; stop the bot before copying SQLite. Delete the data folder while stopped to erase all bot settings/data.

Bot API/network failures are logged without the token. Failed actions do not receive a false success confirmation. Telegram rate limits can delay/drop an action; no exactly-once processing guarantee is made. A crash between an action and saving its update offset may repeat that action. Test in a small group first. Automatic scam detection, AI chat, advanced raid detection, dashboards, analytics, and Rose federation bans are not included in this initial version. Basic filters do not catch every obfuscated link or scam.

Run offline tests: `python3 -m unittest -v` (Windows: `py -m unittest -v`). Tests use a mock Telegram API. Live operation still requires your token and a test supergroup.

Official API reference: https://core.telegram.org/bots/api

## New in v1.1: duplicate messages within two minutes

Enabled by default, including existing groups when you upgrade. A regular member repeating the same text or caption in the same group within 120 seconds has the repeat deleted. The original stays. Case, repeated whitespace, and equivalent Unicode formatting are normalized. Different members can send the same text. Admins and bots are exempt. Media without a caption is not compared. This does not inspect historical messages.

Use `/duplicates off` to disable or `/duplicates on` to enable. Human admins need Change Group Info to change this setting. The bot needs Delete Messages. Check with a regular-member account; testing from an admin account will not trigger deletion.

The 120-second window starts from the first observed copy; deleted repeats do not extend it. At 120 seconds a fresh copy is allowed, subject to other spam rules. Recent message hashes and timestamps are saved in SQLite to preserve the window across restarts. No raw message text is stored for duplicate checking. Expired entries are cleaned on the next nonempty message comparison.

### Upgrade on Mac

1. In your running bot Terminal press Control+C once to stop the old version.
2. Extract the updated ZIP. Copy the new bot.py into your existing bot folder, replacing the old bot.py. Keep your existing .env and data folder so your token and settings stay intact.
3. In the same Terminal run `python3 bot.py` again. The database updates automatically.
4. Check `/settings` and test two matching messages from a regular-member account within two minutes.

Alternatively, run from the newly extracted configured folder; this starts fresh settings unless you copy your old data folder into it. Only run one bot instance for your token.
