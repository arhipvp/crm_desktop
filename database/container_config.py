"""Параметры контейнера PostgreSQL."""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

DOTENV_PATH = Path(__file__).resolve().parents[1] / 'docker' / 'db.env'
if DOTENV_PATH.exists():
    load_dotenv(DOTENV_PATH)
load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)

POSTGRES_DB: str = os.getenv('POSTGRES_DB', 'crm')
POSTGRES_USER: str = os.getenv('POSTGRES_USER', 'crm_user')
POSTGRES_PASSWORD: str = os.getenv('POSTGRES_PASSWORD', 'crm_pass')
POSTGRES_PORT: int = int(os.getenv('POSTGRES_PORT', 5432))
