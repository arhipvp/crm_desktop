"""Миграция: добавление поля локального пути папки для полисов.

Запуск:
    python database/migrations/002_add_policy_drive_folder_path.py
"""

from peewee import CharField
from playhouse.migrate import SqliteMigrator, PostgresqlMigrator, migrate

from database.db import db


def _get_migrator(database):
    if database.__class__.__name__ == "SqliteDatabase":
        return SqliteMigrator(database)
    return PostgresqlMigrator(database)


def run() -> None:
    database = db.obj
    migrator = _get_migrator(database)

    existing_columns = {column.name for column in database.get_columns("policy")}

    if "drive_folder_path" in existing_columns:
        print("drive_folder_path уже существует в таблице policy — изменений не требуется.")
        return

    migrate(
        migrator.add_column(
            "policy",
            "drive_folder_path",
            CharField(null=True),
        )
    )


def rollback() -> None:
    database = db.obj
    migrator = _get_migrator(database)

    existing_columns = {column.name for column in database.get_columns("policy")}

    if "drive_folder_path" not in existing_columns:
        print("drive_folder_path отсутствует в таблице policy — откатывать нечего.")
        return

    migrate(
        migrator.drop_column("policy", "drive_folder_path"),
    )


if __name__ == "__main__":
    from database.init import init_from_env

    init_from_env()
    run()
