from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.database import Database
from bot.keyboards import BTN_CUSTOM
from bot.utils.access import ensure_access

WAITING_CUSTOM = "waiting_custom_order"


async def custom_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await ensure_access(update, context):
        return

    context.user_data[WAITING_CUSTOM] = True
    await update.message.reply_text(
        "📦 **Custom Order**\n\n"
        "Describe what you need:\n"
        "• Number of proxies\n"
        "• Type (HTTP/SOCKS5/residential)\n"
        "• Duration or any special requirements\n\n"
        "Our team will reply with a quote.",
        parse_mode="Markdown",
    )


async def receive_custom_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not context.user_data.get(WAITING_CUSTOM):
        return
    if not await ensure_access(update, context):
        return

    context.user_data.pop(WAITING_CUSTOM, None)
    settings = context.bot_data["settings"]
    user = update.effective_user
    if not user:
        return

    text = update.message.text.strip()
    await update.message.reply_text(
        "✅ Custom order submitted! We'll contact you soon.",
    )

    admin_msg = (
        f"📦 **Custom Order Request**\n\n"
        f"From: {user.first_name} (@{user.username or 'n/a'}) `{user.id}`\n\n"
        f"{text}"
    )
    for admin_id in settings.admin_ids:
        try:
            await context.bot.send_message(admin_id, admin_msg, parse_mode="Markdown")
        except Exception:
            pass


def register_custom_handlers(application) -> None:
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_CUSTOM}$"), custom_order_start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_order),
        group=3,
    )
