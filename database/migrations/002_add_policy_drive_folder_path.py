"""Миграция: добавление поля локального пути папки для полисов.

Запуск:
    python database/migrations/002_add_policy_drive_folder_path.py
"""

from peewee import CharField
from playhouse.migrate import SqliteMigrator, PostgresqlMigrator, migrate

from database.db import db


def run() -> None:
    database = db.obj
    if database.__class__.__name__ == "SqliteDatabase":
        migrator = SqliteMigrator(database)
    else:
        migrator = PostgresqlMigrator(database)

    existing_columns = {column.name for column in database.get_columns("policy")}

    operations = []
    if "drive_folder_path" not in existing_columns:
        operations.append(
            migrator.add_column(
                "policy",
                "drive_folder_path",
                CharField(null=True),
            )
        )

    if not operations:
        print("drive_folder_path уже существует в таблице policy — изменений не требуется.")
        return

    migrate(*operations)


if __name__ == "__main__":
    from database.init import init_from_env

    init_from_env()
    run()
