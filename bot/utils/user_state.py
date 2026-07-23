from bot.keyboards import (
    BTN_BUY,
    BTN_CHECKER,
    BTN_CUSTOM,
    BTN_HELP,
    BTN_ORDERS,
    BTN_PROFILE,
)

MENU_BUTTONS = frozenset(
    {BTN_BUY, BTN_CUSTOM, BTN_CHECKER, BTN_ORDERS, BTN_PROFILE, BTN_HELP}
)

WAITING_PROXY_CHECK = "waiting_proxy_check"
WAITING_CUSTOM_QTY = "waiting_custom_qty"
WAITING_TRX = "waiting_trx"
WAITING_ADMIN_BROADCAST = "waiting_admin_broadcast"
WAITING_ADMIN_PROXIES = "waiting_admin_proxies"


def is_menu_button(text: str | None) -> bool:
    return bool(text and text.strip() in MENU_BUTTONS)


def clear_admin_modes(context) -> None:
    context.user_data.pop(WAITING_ADMIN_BROADCAST, None)
    context.user_data.pop(WAITING_ADMIN_PROXIES, None)


def clear_input_modes(context) -> None:
    """Exit checker / custom-order input modes."""
    context.user_data.pop(WAITING_PROXY_CHECK, None)
    context.user_data.pop(WAITING_CUSTOM_QTY, None)
