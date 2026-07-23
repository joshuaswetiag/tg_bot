import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class ProxyPack:
    id: str
    name: str
    count: int
    price: float


PROXY_PACKS: list[ProxyPack] = [
    ProxyPack("starter", "Starter Pack", 50, 100),
    ProxyPack("basic", "Basic Pack", 100, 200),
    ProxyPack("standard", "Standard Pack", 250, 500),
    ProxyPack("pro", "Pro Pack", 500, 1000),
    ProxyPack("business", "Business Pack", 1000, 2000),
]

PACK_BY_ID = {p.id: p for p in PROXY_PACKS}


@dataclass
class Settings:
    bot_token: str
    admin_ids: list[int]
    required_channel: str
    bkash_number: str
    bkash_type: str
    bot_name: str
    database_url: str
    db_path: str


def load_settings() -> Settings:
    admin_raw = os.getenv("ADMIN_IDS", "")
    admin_ids = [int(x.strip()) for x in admin_raw.split(",") if x.strip()]

    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise ValueError("BOT_TOKEN is required in .env")

    return Settings(
        bot_token=token,
        admin_ids=admin_ids,
        required_channel=os.getenv("REQUIRED_CHANNEL", ""),
        bkash_number=os.getenv("BKASH_NUMBER", "01845007133"),
        bkash_type=os.getenv("BKASH_TYPE", "Personal"),
        bot_name=os.getenv("BOT_NAME", "Proxy Store"),
        database_url=os.getenv("DATABASE_URL", ""),
        db_path=os.getenv("DB_PATH", "data/bot.db"),
    )
