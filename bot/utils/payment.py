from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import Settings


def payment_method_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("bKash", callback_data=f"pay:bkash:{order_id}"),
                InlineKeyboardButton("Nagad", callback_data=f"pay:nagad:{order_id}"),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data=f"pay:cancel:{order_id}")],
        ]
    )


def payment_instructions(
    method: str, amount: float, settings: Settings, user_id: int, proxy_count: int
) -> str:
    if method == "nagad":
        return (
            f"💳 **Nagad Payment**\n\n"
            f"**Order:** {proxy_count} proxies — **৳{amount:.0f}**\n\n"
            f"Send **৳{amount:.0f}** to:\n"
            f"**Number:** `{settings.nagad_number}`\n"
            f"**Account Type:** {settings.nagad_type}\n\n"
            f"Send money → Personal → Enter amount → "
            f"Use reference: your Telegram ID (`{user_id}`)\n\n"
            f"✅ After sending, reply with your **Transaction ID (TRX ID):**"
        )

    return (
        f"💳 **bKash Payment**\n\n"
        f"**Order:** {proxy_count} proxies — **৳{amount:.0f}**\n\n"
        f"Send **৳{amount:.0f}** to:\n"
        f"**Number:** `{settings.bkash_number}`\n"
        f"**Account Type:** {settings.bkash_type}\n\n"
        f"Send money → Personal → Enter amount → "
        f"Use reference: your Telegram ID (`{user_id}`)\n\n"
        f"✅ After sending, reply with your **Transaction ID (TRX ID):**"
    )


def payment_method_prompt(amount: float, proxy_count: int) -> str:
    return (
        f"💳 **Select payment method**\n\n"
        f"**{proxy_count}** proxies — **৳{amount:.0f}**\n\n"
        "Choose bKash or Nagad:"
    )
