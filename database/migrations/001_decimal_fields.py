"""Миграция: перевод денежных полей на Decimal.

Запуск:
    python database/migrations/001_decimal_fields.py
"""

from decimal import Decimal
from peewee import DecimalField
from playhouse.migrate import SqliteMigrator, PostgresqlMigrator, migrate

from database.db import db


def run() -> None:
    database = db.obj
    if database.__class__.__name__ == "SqliteDatabase":
        migrator = SqliteMigrator(database)
    else:
        migrator = PostgresqlMigrator(database)

    decimal = DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))

    migrate(
        migrator.alter_column_type("payment", "amount", decimal),
        migrator.alter_column_type("income", "amount", decimal),
        migrator.alter_column_type("expense", "amount", decimal),
        migrator.alter_column_type("dealcalculation", "insured_amount", decimal),
        migrator.alter_column_type("dealcalculation", "premium", decimal),
        migrator.alter_column_type("dealcalculation", "deductible", decimal),
    )


if __name__ == "__main__":
    from database.init import init_from_env

    init_from_env()
    run()

