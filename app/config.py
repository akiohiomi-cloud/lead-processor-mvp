from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()


class Settings(BaseModel):
    dry_run: bool
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"
    google_sheets_id: str = ""
    google_service_account_path: str = "./service-account.json"
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    phone_default_region: str = "UA"


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@lru_cache
def get_settings() -> Settings:
    return Settings(
        dry_run=_env_bool("DRY_RUN", default=True),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5"),
        google_sheets_id=os.getenv("GOOGLE_SHEETS_ID", ""),
        google_service_account_path=os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_PATH", "./service-account.json"
        ),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
        phone_default_region=os.getenv("PHONE_DEFAULT_REGION", "UA"),
    )
