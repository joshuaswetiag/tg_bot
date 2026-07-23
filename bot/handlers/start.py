from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from bot.database import Database
from bot.keyboards import MAIN_KEYBOARD, verify_channel_keyboard
from bot.utils.access import check_channel_member, ensure_access


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    user = update.effective_user
    if not user or not update.message:
        return

    db.upsert_user(user.id, user.username, user.first_name)

    if settings.required_channel:
        in_channel = await check_channel_member(update, context, settings.required_channel)
        if not in_channel:
            await update.message.reply_text(
                f"👋 Welcome to **{settings.bot_name}**!\n\n"
                f"Please join our channel to unlock all features.",
                reply_markup=verify_channel_keyboard(settings.required_channel),
                parse_mode="Markdown",
            )
            return
        db.set_user_verified(user.id, True)

    await update.message.reply_text(
        f"👋 Welcome to **{settings.bot_name}**!\n\n"
        "Use the menu below to browse proxy packs, check orders, or get help.",
        reply_markup=MAIN_KEYBOARD,
        parse_mode="Markdown",
    )


async def verify_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return
    await query.answer()

    settings = context.bot_data["settings"]
    db: Database = context.bot_data["db"]
    user = update.effective_user
    if not user:
        return

    if not settings.required_channel:
        await query.edit_message_text("No channel verification required.")
        return

    in_channel = await check_channel_member(update, context, settings.required_channel)
    if in_channel:
        db.set_user_verified(user.id, True)
        await query.edit_message_text(
            "✅ **Channel Verified!**\n\n"
            "Welcome to Proxy Shop Bot! You can now use all features of the bot.",
            parse_mode="Markdown",
        )
        if query.message:
            await query.message.reply_text(
                "Choose an option from the menu:",
                reply_markup=MAIN_KEYBOARD,
            )
    else:
        await query.answer("You haven't joined the channel yet.", show_alert=True)


def register_start_handlers(application) -> None:
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(verify_channel_callback, pattern="^verify_channel$"))
