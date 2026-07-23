from telegram import Update
from telegram.ext import CallbackQueryHandler, ContextTypes, MessageHandler, filters

from bot.config import PACK_BY_ID
from bot.database import Database
from bot.keyboards import BTN_BUY, MAIN_KEYBOARD, pack_selection_keyboard
from bot.utils.access import ensure_access
from bot.utils.order_messages import order_submitted
from bot.utils.payment import (
    payment_instructions,
    payment_method_keyboard,
    payment_method_prompt,
)
from bot.utils.account_stock import account_count_label
from bot.utils.user_state import WAITING_TRX, clear_input_modes, is_menu_button


async def _prompt_payment_method(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    order_id: int,
    amount: float,
    proxy_count: int,
    *,
    edit: bool = False,
) -> None:
    context.user_data["active_order_id"] = order_id
    context.user_data.pop(WAITING_TRX, None)
    context.user_data.pop("payment_method", None)

    text = payment_method_prompt(amount, proxy_count)
    markup = payment_method_keyboard(order_id)

    if edit and update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=markup, parse_mode="HTML"
        )
        return

    msg = update.effective_message
    if msg:
        await msg.reply_text(text, reply_markup=markup, parse_mode="HTML")


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
    user = update.effective_user
    if not user:
        return

    available = db.count_available_proxies()
    if available < pack.count:
        msg = update.effective_message
        if msg:
            await msg.reply_text(
                f"⚠️ Not enough stock. Need {pack.count}, have {available}.\n"
                "Ask admin to add accounts from Excel or /add_accounts"
            )
        return

    order_id = db.create_order(user.id, pack.id, pack.name, pack.count, pack.price)
    await _prompt_payment_method(
        update, context, order_id, pack.price, pack.count
    )


async def buy_proxies(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await ensure_access(update, context):
        return

    clear_input_modes(context)
    await update.message.reply_text(
        "📦 <b>Choose a Proxy Account Pack:</b>\n\n"
        "All prices in BDT (Bangladeshi Taka).",
        reply_markup=MAIN_KEYBOARD,
        parse_mode="HTML",
    )
    await update.message.reply_text(
        "Select a pack:",
        reply_markup=pack_selection_keyboard(),
    )


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
        if query.message:
            await query.message.reply_text(
                "Choose an option from the menu:",
                reply_markup=MAIN_KEYBOARD,
            )
        context.user_data.pop("active_order_id", None)
        context.user_data.pop(WAITING_TRX, None)
        return

    pack = PACK_BY_ID.get(pack_key)
    if not pack:
        await query.edit_message_text("Unknown pack. Please try again.")
        return

    db: Database = context.bot_data["db"]
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
    await _prompt_payment_method(
        update, context, order_id, pack.price, pack.count, edit=True
    )


async def payment_method_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    if not await ensure_access(update, context):
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        return

    method, order_id_str = parts[1], parts[2]
    order_id = int(order_id_str)
    db: Database = context.bot_data["db"]
    settings = context.bot_data["settings"]
    user = update.effective_user
    if not user:
        return

    order = db.get_order(order_id)
    if not order or order["user_id"] != user.id:
        await query.edit_message_text("Order not found.")
        return

    if method == "cancel":
        db.cancel_order(order_id, user.id)
        context.user_data.pop("active_order_id", None)
        context.user_data.pop(WAITING_TRX, None)
        await query.edit_message_text("❌ Order cancelled.")
        return

    if method not in ("bkash", "nagad"):
        return

    context.user_data["active_order_id"] = order_id
    context.user_data[WAITING_TRX] = True
    context.user_data["payment_method"] = method

    await query.edit_message_text(
        payment_instructions(
            method,
            float(order["amount"]),
            settings,
            user.id,
            int(order["proxy_count"]),
        ),
        parse_mode="HTML",
    )


async def receive_trx_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not context.user_data.get(WAITING_TRX):
        return
    if not await ensure_access(update, context):
        return

    if is_menu_button(update.message.text):
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
        await update.message.reply_text(
            "No active order. Tap 🛒 Buy Proxy Accounts to start."
        )
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
    payment_method = context.user_data.pop("payment_method", "bkash")
    context.user_data.pop(WAITING_TRX, None)
    context.user_data.pop("active_order_id", None)

    await update.message.reply_text(
        order_submitted(
            order_id=order_id,
            pack_name=order["pack_name"],
            proxy_count=int(order["proxy_count"]),
            amount=float(order["amount"]),
            payment_method=payment_method,
            trx_id=trx_id,
        ),
        parse_mode="HTML",
    )

    from bot.keyboards import order_admin_keyboard

    admin_text = (
        f"🆕 **New Payment**\n\n"
        f"Order: #{order_id}\n"
        f"User: {user.first_name} (@{user.username or 'n/a'}) `{user.id}`\n"
        f"Pack: {order['pack_name']} ({account_count_label(int(order['proxy_count']))})\n"
        f"Amount: ৳{order['amount']:.1f}\n"
        f"Method: {payment_method.upper()}\n"
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
    application.add_handler(MessageHandler(filters.Text([BTN_BUY]), buy_proxies))
    application.add_handler(CallbackQueryHandler(pack_selected, pattern=r"^pack:"))
    application.add_handler(CallbackQueryHandler(payment_method_selected, pattern=r"^pay:"))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_trx_id),
        group=1,
    )
