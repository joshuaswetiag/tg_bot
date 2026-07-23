from bot.config import Settings
from bot.db.postgres import PostgresDatabase
from bot.db.protocol import Database
from bot.db.sqlite import SqliteDatabase


def get_database(settings: Settings) -> Database:
    if settings.database_url:
        return PostgresDatabase(settings.database_url)
    return SqliteDatabase(settings.db_path)
