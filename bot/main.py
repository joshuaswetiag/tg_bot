import logging

from telegram.ext import Application

from bot.config import load_settings
from bot.database import get_database
from bot.handlers.admin import register_admin_handlers
from bot.handlers.buy import register_buy_handlers
from bot.handlers.checker import register_checker_handlers
from bot.handlers.custom_order import register_custom_handlers
from bot.handlers.help import register_help_handlers
from bot.handlers.orders import register_orders_handlers
from bot.handlers.profile import register_profile_handlers
from bot.handlers.start import register_start_handlers

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    settings = load_settings()
    db = get_database(settings)
    backend = "Supabase/PostgreSQL" if settings.database_url else f"SQLite ({settings.db_path})"

    application = (
        Application.builder()
        .token(settings.bot_token)
        .build()
    )

    application.bot_data["db"] = db
    application.bot_data["settings"] = settings

    register_start_handlers(application)
    register_buy_handlers(application)
    register_orders_handlers(application)
    register_profile_handlers(application)
    register_checker_handlers(application)
    register_custom_handlers(application)
    register_help_handlers(application)
    register_admin_handlers(application)

    logger.info("Starting %s — database: %s", settings.bot_name, backend)
    application.run_polling(
        allowed_updates=["message", "callback_query"],
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
