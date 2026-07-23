from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters

from bot.database import Database
from bot.keyboards import BTN_ORDERS
from bot.utils.access import ensure_access
from bot.utils.user_state import clear_input_modes

STATUS_LABELS = {
    "awaiting_payment": "⏳ Awaiting payment",
    "pending_review": "🔍 Pending review",
    "completed": "✅ Completed",
    "rejected": "❌ Rejected",
    "cancelled": "🚫 Cancelled",
}


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not await ensure_access(update, context):
        return

    clear_input_modes(context)
    db: Database = context.bot_data["db"]
    user = update.effective_user
    if not user:
        return

    orders = db.get_user_orders(user.id)
    if not orders:
        await update.message.reply_text("📋 You have no orders yet.")
        return

    lines = ["📋 **My Orders**\n"]
    for order in orders:
        status = STATUS_LABELS.get(order["status"], order["status"])
        lines.append(
            f"**#{order['id']}** — {order['pack_name']}\n"
            f"{order['proxy_count']} proxies · ৳{order['amount']:.0f} · {status}"
        )
        if order["status"] == "completed" and order["proxies"]:
            lines.append(f"```\n{order['proxies']}\n```")

    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


def register_orders_handlers(application) -> None:
    application.add_handler(MessageHandler(filters.Text([BTN_ORDERS]), my_orders))
