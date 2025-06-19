#!/usr/bin/env python3
"""Миграция базы данных: добавление таблиц исполнителей."""

from database.init import init_from_env
from database.models import Executor, DealExecutor
from database.db import db


def main() -> None:
    init_from_env()
    db.connect(reuse_if_open=True)
    db.create_tables([Executor, DealExecutor], safe=True)
    db.close()


if __name__ == "__main__":
    main()
