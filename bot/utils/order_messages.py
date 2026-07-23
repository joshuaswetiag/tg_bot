from bot.config import Settings


def format_payment_method(method: str) -> str:
    return "Nagad" if method == "nagad" else "bKash"


def payment_instructions(
    method: str, amount: float, settings: Settings, user_id: int, proxy_count: int
) -> str:
    if method == "nagad":
        title = "💳 Nagad Payment"
        number = settings.nagad_number
        acc_type = settings.nagad_type
    else:
        title = "💳 bKash Payment"
        number = settings.bkash_number
        acc_type = settings.bkash_type

    return (
        f"<b>{title}</b>\n\n"
        f"📧 Send <b>৳{amount:.1f}</b> to:\n"
        f"📱 Number: <code>{number}</code>\n"
        f"🏷 Type: {acc_type}\n\n"
        f"📝 Send money → Personal → Enter amount → "
        f"Use reference: your Telegram ID\n\n"
        f"✅ After sending, reply with your Transaction ID (TRX ID):"
    )


def payment_method_prompt(amount: float, proxy_count: int) -> str:
    return (
        "<b>💳 Select Payment Method</b>\n\n"
        f"📦 <b>{proxy_count}</b> proxies — <b>৳{amount:.1f}</b>\n\n"
        "Choose bKash or Nagad:"
    )


def order_submitted(
    *,
    order_id: int,
    pack_name: str,
    proxy_count: int,
    amount: float,
    payment_method: str,
    trx_id: str,
) -> str:
    return (
        "<b>✅ Order Submitted!</b>\n\n"
        f"🆔 Order ID: <code>#{order_id}</code>\n"
        f"📦 Pack: {pack_name}\n"
        f"🌐 Quantity: {proxy_count} proxies\n"
        f"💵 Amount: ৳{amount:.1f}\n"
        f"💳 Method: {format_payment_method(payment_method)}\n"
        f"🏷 TRX ID: <code>{trx_id}</code>\n\n"
        "⏳ Your order is pending admin approval. "
        "You'll be notified once it's processed."
    )


def order_delivered(*, order_id: int, proxy_count: int) -> str:
    return (
        f"<b>🎉 Order #{order_id} Delivered!</b>\n\n"
        "✅ Your payment was approved.\n"
        f"📦 {proxy_count} proxies are attached below.\n\n"
        "Thank you for your purchase! 🙏"
    )


def order_proxy_filename(order_id: int) -> str:
    return f"proxies_order_{order_id}.txt"


def order_proxy_caption(*, order_id: int, proxy_count: int) -> str:
    return f"📦 {proxy_count} proxies — Order #{order_id}"
