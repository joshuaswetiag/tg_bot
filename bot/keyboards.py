from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.config import PROXY_PACKS

# Reply keyboard labels
BTN_BUY = "🛒 Buy Proxies"
BTN_CUSTOM = "📦 Custom Order"
BTN_CHECKER = "🔍 Proxy Checker"
BTN_ORDERS = "📋 My Orders"
BTN_PROFILE = "👤 My Profile"
BTN_HELP = "ℹ️ Help"

MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton(BTN_BUY), KeyboardButton(BTN_CUSTOM)],
        [KeyboardButton(BTN_CHECKER)],
        [KeyboardButton(BTN_ORDERS), KeyboardButton(BTN_PROFILE)],
        [KeyboardButton(BTN_HELP)],
    ],
    resize_keyboard=True,
)


def pack_selection_keyboard() -> InlineKeyboardMarkup:
    buttons = []
    for p in PROXY_PACKS:
        prefix = "🧪 " if p.id == "test" else "📦 "
        label = f"{prefix}{p.name} — {p.count} proxy{'ies' if p.count != 1 else ''} @ ৳{int(p.price)}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"pack:{p.id}")])
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="pack:cancel")])
    return InlineKeyboardMarkup(buttons)


def order_admin_keyboard(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Approve", callback_data=f"admin:approve:{order_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"admin:reject:{order_id}"),
            ]
        ]
    )


def verify_channel_keyboard(channel: str) -> InlineKeyboardMarkup:
    username = channel.lstrip("@")
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{username}")],
            [InlineKeyboardButton("✅ I Joined", callback_data="verify_channel")],
        ]
    )


BTN_CHECKER_CANCEL = "❌ Cancel Check"

CHECKER_CANCEL_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton(BTN_CHECKER_CANCEL, callback_data="checker:cancel")]]
)
