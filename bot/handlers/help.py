from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.keyboards import BTN_HELP
from bot.utils.access import ensure_access


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await ensure_access(update, context):
        return

    settings = context.bot_data["settings"]
    await update.message.reply_text(
        f"ℹ️ **Help — {settings.bot_name}**\n\n"
        "**🛒 Buy Proxies** — Choose a pack and pay via bKash\n"
        "**📦 Custom Order** — Request a custom proxy package\n"
        "**🔍 Proxy Checker** — Test if your proxies are working\n"
        "**📋 My Orders** — View order history and delivered proxies\n"
        "**👤 My Profile** — Your account stats\n\n"
        "Payment: Send bKash to the number shown, then reply with your TRX ID.\n"
        "Use your Telegram ID as the payment reference.",
        parse_mode="Markdown",
    )


def register_help_handlers(application) -> None:
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_HELP}$"), help_handler))
