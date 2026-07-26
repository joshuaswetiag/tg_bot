import html
import logging

from telegram import Bot
from telegram.ext import ContextTypes

from bot.keyboards import order_admin_keyboard
from bot.utils.account_stock import account_count_label

logger = logging.getLogger(__name__)


def format_new_order_admin_message(
    *,
    order_id: int,
    user_id: int,
    first_name: str,
    username: str | None,
    pack_name: str,
    proxy_count: int,
    amount: float,
    payment_method: str,
    trx_id: str,
) -> str:
    uname = f"@{html.escape(username)}" if username else "—"
    return (
        "<b>🆕 New Payment — Approval Needed</b>\n\n"
        f"🆔 Order: <code>#{order_id}</code>\n"
        f"👤 User: {html.escape(first_name)} ({uname})\n"
        f"🆔 Telegram ID: <code>{user_id}</code>\n"
        f"📦 Pack: {html.escape(pack_name)}\n"
        f"🌐 {account_count_label(proxy_count)}\n"
        f"💵 Amount: ৳{amount:.1f}\n"
        f"💳 Method: {html.escape(payment_method.upper())}\n"
        f"🏷 TRX ID: <code>{html.escape(trx_id)}</code>"
    )


def format_pending_order_message(order: dict) -> str:
    first_name = html.escape(str(order.get("first_name") or "User"))
    username = order.get("username")
    uname = f"@{html.escape(username)}" if username else "n/a"
    trx = html.escape(str(order.get("trx_id") or "—"))
    return (
        f"<b>Order #{order['id']}</b>\n"
        f"User: {first_name} ({uname})\n"
        f"Telegram ID: <code>{order['user_id']}</code>\n"
        f"Pack: {html.escape(str(order['pack_name']))} "
        f"({account_count_label(int(order['proxy_count']))})\n"
        f"Amount: ৳{float(order['amount']):.1f}\n"
        f"TRX: <code>{trx}</code>"
    )


async def notify_admins_new_order(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    order_id: int,
    user_id: int,
    first_name: str,
    username: str | None,
    pack_name: str,
    proxy_count: int,
    amount: float,
    payment_method: str,
    trx_id: str,
) -> None:
    settings = context.bot_data["settings"]
    bot: Bot = context.bot
    text = format_new_order_admin_message(
        order_id=order_id,
        user_id=user_id,
        first_name=first_name or "User",
        username=username,
        pack_name=pack_name,
        proxy_count=proxy_count,
        amount=amount,
        payment_method=payment_method,
        trx_id=trx_id,
    )
    markup = order_admin_keyboard(order_id)

    for admin_id in settings.admin_ids:
        try:
            await bot.send_message(
                admin_id,
                text,
                parse_mode="HTML",
                reply_markup=markup,
            )
        except Exception:
            logger.exception("Failed to notify admin %s about order #%s", admin_id, order_id)
