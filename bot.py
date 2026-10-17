import os
import re
import logging
from collections import defaultdict
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

# In-memory evidence from messages received while the bot is running.
# Restarting the process clears this lightweight demo's evidence cache.
EVIDENCE = defaultdict(lambda: defaultdict(set))
ROLE_TERMS = {
    "CEO / Founder": re.compile(r"\b(ceo|founder|co-founder|chief executive officer)\b", re.I),
    "CTO": re.compile(r"\b(cto|chief technology officer)\b", re.I),
    "Team": re.compile(r"\b(team|official team|core team|staff)\b", re.I),
    "Moderator": re.compile(r"\b(mod|moderator|admin)\b", re.I),
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Team Finder is ready. Add me to a group, make me an admin so I can verify the admin list, "
        "then use /scan. I only see new messages delivered to me; I cannot retrieve old chat history."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/scan — show Telegram-confirmed admins and possible public role clues\n"
        "/help — show this help\n\n"
        "CEO/CTO/team labels are inferred from messages and are not independently verified."
    )

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat or chat.type not in ("group", "supergroup"):
        await update.message.reply_text("Use /scan inside the group you want to check.")
        return
    try:
        admins = await context.bot.get_chat_administrators(chat.id)
    except Exception as exc:
        log.info("Admin lookup failed: %s", exc)
        await update.message.reply_text(
            "I couldn't read the admin list. Add me to this group and promote me to admin, then try /scan again."
        )
        return
    lines = [f"Verified Telegram admins in {chat.title or 'this group'}:"]
    for member in admins:
        user = member.user
        name = " ".join(x for x in [user.first_name, user.last_name] if x) or "(unnamed)"
        username = f"@{user.username}" if user.username else "no username"
        title = getattr(member, "custom_title", None)
        label = "Owner/creator" if member.status == "creator" else "Admin"
        if title:
            label += f" — {title}"
        lines.append(f"• {name} ({username}) — {label}")
    clues = EVIDENCE[chat.id]
    if clues:
        lines.append("\nPossible role clues from messages received since bot startup:")
        for user_key, roles in list(clues.items())[:30]:
            lines.append(f"• {user_key}: {', '.join(sorted(roles))} (unverified)")
    else:
        lines.append("\nNo role clues collected yet. I can only check messages delivered to me after startup.")
    await update.message.reply_text("\n".join(lines))

async def observe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    if not msg or not chat or not msg.from_user or msg.from_user.is_bot:
        return
    body = msg.text or msg.caption or ""
    matched = [role for role, pattern in ROLE_TERMS.items() if pattern.search(body)]
    if not matched:
        return
    u = msg.from_user
    who = f"@{u.username}" if u.username else (" ".join(filter(None, [u.first_name, u.last_name])) or f"user_id:{u.id}")
    for role in matched:
        EVIDENCE[chat.id][who].add(role)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Bot error", exc_info=context.error)


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in your environment before running the bot.")
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(MessageHandler(filters.TEXT | filters.CAPTION, observe))
    app.add_error_handler(error_handler)
    log.info("Bot is running")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
