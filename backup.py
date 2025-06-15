"""Резервное копирование базы данных.

Перед запуском требуется переменная окружения ``DATABASE_URL``.
"""

import logging
import os
import subprocess
import urllib.parse
from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from peewee import PostgresqlDatabase
from config import (
    DATABASE_URL,
    POSTGRES_DB,
    POSTGRES_USER,
    BACKUP_DIR,
    SQL_BACKUP_TEMPLATE,
    XLSX_BACKUP_TEMPLATE,
    DRIVE_BACKUP_FOLDER,
)

from database.db import db
from database.models import Client, Deal, Expense, Income, Payment, Policy, Task
from services.folder_utils import (
    create_drive_folder,
    extract_folder_id,
    upload_to_drive,
)
from utils.logging_config import setup_logging

# ───────────── setup ─────────────
logger = logging.getLogger(__name__)
load_dotenv()
setup_logging()

DATE = datetime.now().strftime("%Y-%m-%d_%H-%M")
SQL_PATH = BACKUP_DIR / SQL_BACKUP_TEMPLATE.format(date=DATE)
XLSX_PATH = BACKUP_DIR / XLSX_BACKUP_TEMPLATE.format(date=DATE)
DRIVE_FOLDER_NAME = DRIVE_BACKUP_FOLDER

os.makedirs(BACKUP_DIR, exist_ok=True)

# ───────────── pg_dump via Docker ─────────────
logger.info("📦 SQL-дамп через docker exec…")

pg_container = "crm_db"
pg_user = POSTGRES_USER
pg_db = POSTGRES_DB

# Инициализация Proxy
url = urllib.parse.urlparse(DATABASE_URL)
db.initialize(
    PostgresqlDatabase(
        database=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port or 5432,
    )
)

try:
    with open(SQL_PATH, "w", encoding="utf-8") as f:
        subprocess.run(
            ["docker", "exec", pg_container, "pg_dump", "-U", pg_user, "-d", pg_db],
            stdout=f,
            check=True,
        )
    logger.info(f"✅ SQL-дамп сохранён: {SQL_PATH}")
except Exception:
    logger.exception("⚠️ Не удалось создать SQL-дамп")

# ───────────── Excel ─────────────
logger.info("📊 Excel-файл…")


def peewee_to_df(model):
    return pd.DataFrame([m.__data__ for m in model.select()])


with db.connection_context():
    sheets = {
        "clients": peewee_to_df(Client),
        "deals": peewee_to_df(Deal),
        "policies": peewee_to_df(Policy),
        "payments": peewee_to_df(Payment),
        "incomes": peewee_to_df(Income),
        "expenses": peewee_to_df(Expense),
        "tasks": peewee_to_df(Task),
    }

with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as writer:
    for name, df in sheets.items():
        df.to_excel(writer, index=False, sheet_name=name)

logger.info(f"✅ Excel-файл сохранён: {XLSX_PATH}")

# ───────────── Google Drive ─────────────
logger.info("☁️ Загрузка в Google Drive…")

folder_url = create_drive_folder(DRIVE_FOLDER_NAME)
folder_id = extract_folder_id(folder_url)

if SQL_PATH.exists():
    upload_to_drive(str(SQL_PATH), folder_id)
else:
    logger.warning("⚠️ SQL-файл не найден, пропускаем загрузку.")

upload_to_drive(str(XLSX_PATH), folder_id)

logger.info("✅ Готово: всё, что найдено, загружено в Google Drive.")
