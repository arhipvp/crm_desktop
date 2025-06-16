"""Модуль конфигурации приложения."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env в корне проекта
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# Путь к базе данных или строка подключения
DATABASE_URL: str | None = os.getenv("DATABASE_URL")

# Токен Telegram‑бота
TG_BOT_TOKEN: str | None = os.getenv("TG_BOT_TOKEN")

# ID чата администратора
ADMIN_CHAT_ID: str | None = os.getenv("ADMIN_CHAT_ID")

# Путь к учётным данным сервисного аккаунта Google
GOOGLE_CREDENTIALS: str = os.getenv("GOOGLE_CREDENTIALS", "credentials.json")

# Локальная папка синхронизации Google Drive
GOOGLE_DRIVE_LOCAL_ROOT: str = os.getenv(
    "GOOGLE_DRIVE_LOCAL_ROOT", r"G:\\Мой диск\\Клиенты"
)

# ID корневой папки на Google Drive для новых каталогов
ROOT_FOLDER_ID: str = "1-hTRZ7meDTGDQezoY_ydFkmXIng3gXFm"

# Параметры PostgreSQL по умолчанию для backup.py
POSTGRES_USER: str = os.getenv("POSTGRES_USER", "crm_user")
POSTGRES_DB: str = os.getenv("POSTGRES_DB", "crm")

# Пути для логов и бэкапов
LOGS_DIR: Path = Path("logs")
LOG_FILE: Path = LOGS_DIR / "crm.log"
BACKUP_DIR: Path = Path("backups")
SQL_BACKUP_TEMPLATE = "backup_{date}.sql"
XLSX_BACKUP_TEMPLATE = "backup_{date}.xlsx"
DRIVE_BACKUP_FOLDER = "Backups"

# Google Drive scopes
GOOGLE_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
