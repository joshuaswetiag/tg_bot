from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.keyboards import BTN_CHECKER
from bot.utils.access import ensure_access
from bot.utils.proxy_checker import check_proxies

WAITING_PROXY_CHECK = "waiting_proxy_check"


async def proxy_checker_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await ensure_access(update, context):
        return

    context.user_data[WAITING_PROXY_CHECK] = True
    await update.message.reply_text(
        "🔍 **Proxy Checker**\n\n"
        "Send one or more proxies (one per line):\n"
        "`host:port` or `user:pass@host:port`\n\n"
        "Max 10 proxies per check.",
        parse_mode="Markdown",
    )


async def receive_proxies_to_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not context.user_data.get(WAITING_PROXY_CHECK):
        return
    if not await ensure_access(update, context):
        return

    context.user_data.pop(WAITING_PROXY_CHECK, None)
    lines = [ln.strip() for ln in update.message.text.splitlines() if ln.strip()]
    if not lines:
        await update.message.reply_text("No proxies found. Try again from 🔍 Proxy Checker.")
        return

    await update.message.reply_text(f"Checking {min(len(lines), 10)} proxy(s)...")

    results = await check_proxies(lines)
    parts = ["🔍 **Results:**\n"]
    for r in results:
        icon = "✅" if r.alive else "❌"
        parts.append(f"{icon} `{r.proxy}`\n{r.detail}")

    await update.message.reply_text("\n".join(parts), parse_mode="Markdown")


def register_checker_handlers(application) -> None:
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_CHECKER}$"), proxy_checker_start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_proxies_to_check),
        group=2,
    )
