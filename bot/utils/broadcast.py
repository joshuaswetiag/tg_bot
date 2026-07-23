import asyncio
import logging

from telegram import Bot
from telegram.error import Forbidden, TelegramError

logger = logging.getLogger(__name__)

MAINTENANCE_NOTICE = (
    "<b>⚠️ Bot Under Maintenance</b>\n\n"
    "The bot is currently under maintenance. "
    "We will notify you here as soon as the bot is back online!"
)

BACK_ONLINE_NOTICE = (
    "<b>🎉 The bot is back online!</b>\n\n"
    "Maintenance is complete, and you can now purchase proxies."
)


async def broadcast_message(
    bot: Bot,
    user_ids: list[int],
    text: str,
    *,
    parse_mode: str | None = "HTML",
    exclude_ids: set[int] | None = None,
) -> tuple[int, int]:
    """Send a message to many users. Returns (sent, failed)."""
    exclude = exclude_ids or set()
    sent = 0
    failed = 0
    kwargs: dict = {}
    if parse_mode:
        kwargs["parse_mode"] = parse_mode

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
