"""Настройки контейнера Telegram‑бота."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем параметры из docker/bot.env, если он существует
DOTENV_PATH = Path(__file__).resolve().parents[1] / 'docker' / 'bot.env'
if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH)
# Fallback на обычный .env для локального запуска
load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)

DATABASE_URL: str | None = os.getenv('DATABASE_URL')
TG_BOT_TOKEN: str | None = os.getenv('TG_BOT_TOKEN')
ADMIN_CHAT_ID: str | None = os.getenv('ADMIN_CHAT_ID')
GOOGLE_DRIVE_LOCAL_ROOT: str = os.getenv('GOOGLE_DRIVE_LOCAL_ROOT', '/drive')
GOOGLE_CREDENTIALS: str = os.getenv('GOOGLE_CREDENTIALS', 'credentials.json')
