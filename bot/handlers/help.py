from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.keyboards import BTN_HELP
from bot.utils.access import ensure_access
from bot.utils.user_state import clear_input_modes


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await ensure_access(update, context):
        return

    clear_input_modes(context)
    settings = context.bot_data["settings"]
    support = settings.support_username
    if not support.startswith("@"):
        support = f"@{support}"

    await update.message.reply_text(
        "❓ **How to buy proxies:**\n\n"
        "1️⃣ Tap **Buy Proxies** or **Custom Order**\n"
        "2️⃣ Choose a pack or enter your desired quantity\n"
        "3️⃣ Select payment method (**bKash** / **Nagad**)\n"
        "4️⃣ Send payment & enter your **TRX ID**\n"
        "5️⃣ Admin verifies & proxies are delivered as a **TXT file**\n\n"
        "⏱️ **Processing:** Usually within 1–2 hours\n"
        "📋 Orders expire after **24 hours** if not approved\n\n"
        f"🆘 **Support:** {support}",
        parse_mode="Markdown",
    )


def register_help_handlers(application) -> None:
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_HELP}$"), help_handler))
