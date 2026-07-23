from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.config import CUSTOM_ORDER_MAX, CUSTOM_ORDER_MIN, CUSTOM_PRICE_PER_PROXY
from bot.database import Database
from bot.handlers.buy import _prompt_payment_method
from bot.keyboards import BTN_CUSTOM, MAIN_KEYBOARD
from bot.utils.access import ensure_access
from bot.utils.user_state import WAITING_CUSTOM_QTY, clear_input_modes, is_menu_button

CUSTOM_ORDER_INTRO = (
    "📦 **Custom Order**\n\n"
    "💡 Enter the number of proxies you need:\n"
    f"• Minimum: {CUSTOM_ORDER_MIN:,}\n"
    f"• Maximum: {CUSTOM_ORDER_MAX:,}\n"
    f"• Price: ৳{CUSTOM_PRICE_PER_PROXY:.0f}/proxy\n\n"
    "Type the quantity (numbers only):"
)


async def custom_order_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await ensure_access(update, context):
        return

    clear_input_modes(context)
    context.user_data[WAITING_CUSTOM_QTY] = True
    await update.message.reply_text(
        CUSTOM_ORDER_INTRO, parse_mode="Markdown", reply_markup=MAIN_KEYBOARD
    )


async def receive_custom_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    if not context.user_data.get(WAITING_CUSTOM_QTY):
        return
    if not await ensure_access(update, context):
        return

    if is_menu_button(update.message.text):
        return

    text = update.message.text.strip().replace(",", "")
    if not text.isdigit():
        await update.message.reply_text(
            "Please enter numbers only.\n\n"
            f"Minimum: {CUSTOM_ORDER_MIN:,} · Maximum: {CUSTOM_ORDER_MAX:,}"
        )
        return

    quantity = int(text)
    if quantity < CUSTOM_ORDER_MIN or quantity > CUSTOM_ORDER_MAX:
        await update.message.reply_text(
            f"Quantity must be between **{CUSTOM_ORDER_MIN:,}** and "
            f"**{CUSTOM_ORDER_MAX:,}**.",
            parse_mode="Markdown",
        )
        return

    db: Database = context.bot_data["db"]
    user = update.effective_user
    if not user:
        return

    available = db.count_available_proxies()
    if available < quantity:
        await update.message.reply_text(
            f"⚠️ Not enough stock. Need {quantity:,}, have {available:,}.\n"
            "Try a smaller quantity or contact support."
        )
        return

    context.user_data.pop(WAITING_CUSTOM_QTY, None)
    amount = quantity * CUSTOM_PRICE_PER_PROXY
    pack_name = f"Custom Order ({quantity:,} proxies)"
    order_id = db.create_order(user.id, "custom", pack_name, quantity, amount)
    await _prompt_payment_method(update, context, order_id, amount, quantity)


def register_custom_handlers(application) -> None:
    application.add_handler(MessageHandler(filters.Text([BTN_CUSTOM]), custom_order_start))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, receive_custom_quantity),
        group=3,
    )
