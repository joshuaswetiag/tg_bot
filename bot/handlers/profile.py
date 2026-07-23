from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.database import Database
from bot.keyboards import BTN_PROFILE, MAIN_KEYBOARD
from bot.utils.access import ensure_access
from bot.utils.user_state import clear_input_modes


async def my_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await ensure_access(update, context):
        return

    clear_input_modes(context)
    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    user = update.effective_user
    if not user:
        return

    stats = db.get_user_stats(user.id)
    stock = db.count_available_proxies()

    await update.message.reply_text(
        f"👤 **My Profile**\n\n"
        f"**Name:** {user.first_name}\n"
        f"**Username:** @{user.username or '—'}\n"
        f"**Telegram ID:** `{user.id}`\n"
        f"**Total orders:** {stats['total_orders']}\n"
        f"**Accounts purchased:** {stats['total_proxies']}\n"
        f"**Store:** {settings.bot_name}\n"
        f"**Accounts in stock:** {stock}",
        parse_mode="Markdown",
        reply_markup=MAIN_KEYBOARD,
    )


def register_profile_handlers(application) -> None:
    application.add_handler(MessageHandler(filters.Text([BTN_PROFILE]), my_profile))
