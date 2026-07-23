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

CUSTOM_ORDER_MIN = 50
CUSTOM_ORDER_MAX = 5000
CUSTOM_PRICE_PER_PROXY = 2.0


@dataclass
class Settings:
    bot_token: str
    admin_ids: list[int]
    required_channel: str
    bkash_number: str
    bkash_type: str
    nagad_number: str
    nagad_type: str
    support_username: str
    bot_name: str
    checker_daily_limit: int
    database_url: str
    db_path: str


def _parse_admin_ids(raw: str) -> list[int]:
    ids: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if part.startswith("@"):
            raise ValueError(
                f"ADMIN_IDS must be a numeric Telegram ID, not a username. "
                f"You used '{part}'. Message @userinfobot on Telegram to get your ID."
            )
        try:
            ids.append(int(part))
        except ValueError as exc:
            raise ValueError(
                f"Invalid ADMIN_IDS value '{part}'. "
                "Use your numeric Telegram ID from @userinfobot (e.g. 123456789)."
            ) from exc
    if not ids:
        raise ValueError(
            "ADMIN_IDS is required in .env — your numeric Telegram ID from @userinfobot"
        )
    return ids


def load_settings() -> Settings:
    admin_ids = _parse_admin_ids(os.getenv("ADMIN_IDS", ""))

    token = os.getenv("BOT_TOKEN", "")
    if not token:
        raise ValueError("BOT_TOKEN is required in .env")

    return Settings(
        bot_token=token,
        admin_ids=admin_ids,
        required_channel=os.getenv("REQUIRED_CHANNEL", ""),
        bkash_number=os.getenv("BKASH_NUMBER", "01845007133"),
        bkash_type=os.getenv("BKASH_TYPE", "Personal"),
        nagad_number=os.getenv("NAGAD_NUMBER", "01845007133"),
        nagad_type=os.getenv("NAGAD_TYPE", "Personal"),
        support_username=os.getenv("SUPPORT_USERNAME", "@Noyon001"),
        bot_name=os.getenv("BOT_NAME", "Proxy Store"),
        checker_daily_limit=int(os.getenv("CHECKER_DAILY_LIMIT", "5")),
        database_url=os.getenv("DATABASE_URL", ""),
        db_path=os.getenv("DB_PATH", "data/bot.db"),
    )
