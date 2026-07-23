from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from bot.utils.order_messages import payment_instructions, payment_method_prompt

__all__ = [
    "payment_method_keyboard",
    "payment_instructions",
    "payment_method_prompt",
]


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
