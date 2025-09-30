from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from appdirs import user_log_dir
from dotenv import load_dotenv


@dataclass
class Settings:
    database_url: str = ""
    log_dir: str = field(default_factory=lambda: user_log_dir("crm_desktop"))
    log_level: str = "INFO"
    detailed_logging: bool = False
    approved_executor_ids: list[int] = field(default_factory=list)
    tg_bot_token: str | None = None
    admin_chat_id: int | None = None
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o"
    ai_policy_prompt: str | None = None
    drive_root_folder_id: str | None = "1-hTRZ7meDTGDQezoY_ydFkmXIng3gXFm"
    drive_service_account_file: str = "credentials.json"
    google_drive_local_root: str = r"G:\\Мой диск\\Клиенты"


@lru_cache()
def get_settings() -> Settings:
    dotenv_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path)

    approved_ids = [
        int(part)
        for part in re.split(r"[ ,]+", os.getenv("APPROVED_EXECUTOR_IDS", "").strip())
        if part
    ]

    admin_chat = os.getenv("ADMIN_CHAT_ID")
    return Settings(
        database_url=os.getenv("DATABASE_URL", ""),
        log_dir=os.getenv("LOG_DIR") or user_log_dir("crm_desktop"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        detailed_logging=os.getenv("DETAILED_LOGGING", "0").lower() in {"1", "true", "yes", "on"},
        approved_executor_ids=approved_ids,
        tg_bot_token=os.getenv("TG_BOT_TOKEN"),
        admin_chat_id=int(admin_chat) if admin_chat else None,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
        ai_policy_prompt=os.getenv("AI_POLICY_PROMPT"),
        drive_root_folder_id=os.getenv("GOOGLE_ROOT_FOLDER_ID")
        or "1-hTRZ7meDTGDQezoY_ydFkmXIng3gXFm",
        drive_service_account_file=os.getenv(
            "GOOGLE_CREDENTIALS", "credentials.json"
        ),
        google_drive_local_root=os.getenv(
            "GOOGLE_DRIVE_LOCAL_ROOT", r"G:\\Мой диск\\Клиенты"
        ),
    )
