from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bot.config import PROXY_PACKS

# Reply keyboard labels
BTN_BUY = "🛒 Buy Proxy Accounts"
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
        label = (
            f"📦 {p.name} — {p.count} account{'s' if p.count != 1 else ''} "
            f"@ ৳{int(p.price)}"
        )
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

# Admin panel inline buttons
ADMIN_MAINT_ON = "adminpanel:maint_on"
ADMIN_MAINT_OFF = "adminpanel:maint_off"
ADMIN_BROADCAST = "adminpanel:broadcast"
ADMIN_NOTICE = "adminpanel:notice"
ADMIN_PENDING = "adminpanel:pending"
ADMIN_STOCK = "adminpanel:stock"
ADMIN_ADD_PROXIES = "adminpanel:add_proxies"
ADMIN_REFRESH = "adminpanel:refresh"
ADMIN_CANCEL = "adminpanel:cancel"


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    maint_row = [
        InlineKeyboardButton("⚠️ Maintenance ON", callback_data=ADMIN_MAINT_ON),
        InlineKeyboardButton("🎉 Maintenance OFF", callback_data=ADMIN_MAINT_OFF),
    ]
    return InlineKeyboardMarkup(
        [
            maint_row,
            [
                InlineKeyboardButton("📢 Broadcast", callback_data=ADMIN_BROADCAST),
                InlineKeyboardButton("📣 Send Notice", callback_data=ADMIN_NOTICE),
            ],
            [
                InlineKeyboardButton("📋 Pending Orders", callback_data=ADMIN_PENDING),
                InlineKeyboardButton("📦 Stock", callback_data=ADMIN_STOCK),
            ],
            [
                InlineKeyboardButton("➕ Add Accounts", callback_data=ADMIN_ADD_PROXIES),
                InlineKeyboardButton("🔄 Refresh", callback_data=ADMIN_REFRESH),
            ],
            [InlineKeyboardButton("❌ Close", callback_data=ADMIN_CANCEL)],
        ]
    )


ADMIN_CANCEL_KEYBOARD = InlineKeyboardMarkup(
    [[InlineKeyboardButton("❌ Cancel", callback_data=ADMIN_CANCEL)]]
)
