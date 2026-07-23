import asyncio
import html
import logging

from telegram import Bot, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.error import Forbidden, TelegramError

logger = logging.getLogger(__name__)

MAINTENANCE_NOTICE = (
    "<b>⚠️ Bot Under Maintenance</b>\n\n"
    "The bot is currently under maintenance. "
    "We will notify you here as soon as the bot is back online!"
)

BACK_ONLINE_NOTICE = (
    "<b>🎉 The bot is back online!</b>\n\n"
    "Maintenance is complete, and you can now purchase proxies.\n\n"
    "Use the menu below to get started."
)

BROADCAST_HEADER = "📢 Broadcast"
NOTICE_HEADER = "📣 Notice"


def format_announcement(kind: str, body: str) -> str:
    header = NOTICE_HEADER if kind == "notice" else BROADCAST_HEADER
    return f"<b>{header}</b>\n\n{html.escape(body.strip())}"


async def broadcast_message(
    bot: Bot,
    user_ids: list[int],
    text: str,
    *,
    parse_mode: str | None = "HTML",
    reply_markup: ReplyKeyboardMarkup | ReplyKeyboardRemove | None = None,
    exclude_ids: set[int] | None = None,
) -> tuple[int, int]:
    """Send a message to many users. Returns (sent, failed)."""
    exclude = exclude_ids or set()
    sent = 0
    failed = 0
    kwargs: dict = {}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup

    for user_id in user_ids:
        if user_id in exclude:
            continue
        try:
            await bot.send_message(user_id, text, **kwargs)
            sent += 1
        except Forbidden:
            failed += 1
        except TelegramError:
            logger.exception("Broadcast failed for user %s", user_id)
            failed += 1
        await asyncio.sleep(0.05)

    return sent, failed
