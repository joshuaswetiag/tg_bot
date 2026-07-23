from telegram import Update
from telegram.ext import ContextTypes

from bot.database import Database
from bot.keyboards import MAIN_KEYBOARD, verify_channel_keyboard


async def check_channel_member(update: Update, context: ContextTypes.DEFAULT_TYPE, channel: str) -> bool:
    if not channel:
        return True
    user = update.effective_user
    if not user:
        return False
    try:
        member = await context.bot.get_chat_member(channel, user.id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False


async def ensure_access(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Return True if user may continue; otherwise send a block message."""
    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    user = update.effective_user
    if not user:
        return False

    db.upsert_user(user.id, user.username, user.first_name)

    if db.is_maintenance() and user.id not in settings.admin_ids:
        msg = update.effective_message
        if msg:
            await msg.reply_text(
                "<b>⚠️ Bot Under Maintenance</b>\n\n"
                "The bot is currently under maintenance. "
                "We will notify you here as soon as the bot is back online!",
                parse_mode="HTML",
            )
        return False

    if settings.required_channel:
        in_channel = await check_channel_member(update, context, settings.required_channel)
        if not in_channel and not db.is_user_verified(user.id):
            msg = update.effective_message
            if msg:
                await msg.reply_text(
                    f"📢 **Channel Verification Required**\n\n"
                    f"Please join {settings.required_channel} to use this bot.",
                    reply_markup=verify_channel_keyboard(settings.required_channel),
                    parse_mode="Markdown",
                )
            return False
        if in_channel:
            db.set_user_verified(user.id, True)

    return True
