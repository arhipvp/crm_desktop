import os
from pathlib import Path

from dotenv import load_dotenv
from peewee import PostgresqlDatabase, Proxy

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")


# Парсим переменные
DATABASE_URL = os.getenv("DATABASE_URL")
print(DATABASE_URL)
dotenv_path = Path(__file__).resolve().parent.parent / ".env"
print("Загружаемый .env:", dotenv_path)


if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL не задан в .env")

# Простейший парсер URL для Peewee
import urllib.parse

url = urllib.parse.urlparse(DATABASE_URL)
db = Proxy()
