from telegram import Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from bot.config import PACK_BY_ID
from bot.database import Database
from bot.keyboards import BTN_BUY, pack_selection_keyboard
from bot.utils.access import ensure_access

WAITING_TRX = "waiting_trx"


async def _start_pack_order(
    update: Update, context: ContextTypes.DEFAULT_TYPE, pack_id: str
) -> None:
    pack = PACK_BY_ID.get(pack_id)
    if not pack:
        msg = update.effective_message
        if msg:
            await msg.reply_text("Unknown pack.")
        return

    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    user = update.effective_user
    if not user:
        return

    available = db.count_available_proxies()
    if available < pack.count:
        msg = update.effective_message
        if msg:
            await msg.reply_text(
                f"⚠️ Not enough stock. Need {pack.count}, have {available}.\n"
                "Ask admin to add proxies with /add_proxies"
            )
        return

    order_id = db.create_order(user.id, pack.id, pack.name, pack.count, pack.price)
    context.user_data["active_order_id"] = order_id
    context.user_data[WAITING_TRX] = True

    msg = update.effective_message
    if msg:
        await msg.reply_text(
            f"💳 **bKash Payment**\n\n"
            f"Send **৳{pack.price:.1f}** to:\n"
            f"**Number:** `{settings.bkash_number}`\n"
            f"**Account Type:** {settings.bkash_type}\n\n"
            f"Send money → Personal → Enter amount → "
            f"Use reference: your Telegram ID (`{user.id}`)\n\n"
            f"✅ After sending, reply with your **Transaction ID (TRX ID):**",
            parse_mode="Markdown",
        )


async def buy_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await ensure_access(update, context):
        return

    await update.message.reply_text(
        "📦 **Choose a Proxy Pack:**\n\n"
        "🧪 **Test Pack** — 1 proxy @ ৳10 (for testing)\n\n"
        "All prices in BDT (Bangladeshi Taka).",
        reply_markup=pack_selection_keyboard(),
        parse_mode="Markdown",
    )


async def test_buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Quick test: buy 1 proxy without opening the full pack menu."""
    if not update.message or not await ensure_access(update, context):
        return
    await _start_pack_order(update, context, "test")


async def pack_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    if not await ensure_access(update, context):
        return

    pack_key = query.data.split(":", 1)[1]
    if pack_key == "cancel":
        await query.edit_message_text("❌ Purchase cancelled.")
        context.user_data.pop("active_order_id", None)
        context.user_data.pop(WAITING_TRX, None)
        return

    pack = PACK_BY_ID.get(pack_key)
    if not pack:
        await query.edit_message_text("Unknown pack. Please try again.")
        return

    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    user = update.effective_user
    if not user:
        return

    available = db.count_available_proxies()
    if available < pack.count:
        await query.edit_message_text(
            f"⚠️ Not enough stock. Need {pack.count}, have {available}.\n"
            "Please try a smaller pack or contact support."
        )
        return

    order_id = db.create_order(user.id, pack.id, pack.name, pack.count, pack.price)
    context.user_data["active_order_id"] = order_id
    context.user_data[WAITING_TRX] = True

    await query.edit_message_text(
        f"💳 **bKash Payment**\n\n"
        f"Send **৳{pack.price:.1f}** to:\n"
        f"**Number:** `{settings.bkash_number}`\n"
        f"**Account Type:** {settings.bkash_type}\n\n"
        f"Send money → Personal → Enter amount → "
        f"Use reference: your Telegram ID (`{user.id}`)\n\n"
        f"✅ After sending, reply with your **Transaction ID (TRX ID):**",
        parse_mode="Markdown",
    )


async def receive_trx_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not context.user_data.get(WAITING_TRX):
        return
    if not await ensure_access(update, context):
        return

    trx_id = update.message.text.strip()
    if len(trx_id) < 6:
        await update.message.reply_text("Please send a valid Transaction ID.")
        return

    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    user = update.effective_user
    if not user:
        return

    order_id = context.user_data.get("active_order_id")
    if not order_id:
        await update.message.reply_text("No active order. Tap 🛒 Buy Proxies to start.")
        context.user_data.pop(WAITING_TRX, None)
        return

    order = db.get_order(order_id)
    if not order or order["user_id"] != user.id:
        await update.message.reply_text("Order not found.")
        context.user_data.pop(WAITING_TRX, None)
        return

    if db.trx_exists(trx_id):
        await update.message.reply_text("This TRX ID was already submitted.")
        return

    db.set_order_trx(order_id, trx_id)
    context.user_data.pop(WAITING_TRX, None)
    context.user_data.pop("active_order_id", None)

    await update.message.reply_text(
        "✅ **Payment submitted!**\n\n"
        f"Order #{order_id} is pending admin review.\n"
        "You'll receive your proxies once approved.",
        parse_mode="Markdown",
    )

    from bot.keyboards import order_admin_keyboard

    admin_text = (
        f"🆕 **New Payment**\n\n"
        f"Order: #{order_id}\n"
        f"User: {user.first_name} (@{user.username or 'n/a'}) `{user.id}`\n"
        f"Pack: {order['pack_name']} ({order['proxy_count']} proxies)\n"
        f"Amount: ৳{order['amount']:.1f}\n"
        f"TRX ID: `{trx_id}`"
    )
    for admin_id in settings.admin_ids:
        try:
            await context.bot.send_message(
                admin_id,
                admin_text,
                parse_mode="Markdown",
                reply_markup=order_admin_keyboard(order_id),
            )
        except Exception:
            pass


def register_buy_handlers(application) -> None:
    application.add_handler(CommandHandler("testbuy", test_buy_command))
    application.add_handler(MessageHandler(filters.Regex(f"^{BTN_BUY}$"), buy_proxies))
    application.add_handler(CallbackQueryHandler(pack_selected, pattern=r"^pack:"))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_trx_id),
        group=1,
    )
