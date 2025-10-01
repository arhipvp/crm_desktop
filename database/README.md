# Каталог `database`

Здесь находятся модели базы данных и функции инициализации.

- `db.py` содержит объект `db` (peewee Proxy).
- `init.py` инициализирует соединение с SQLite или PostgreSQL на основе переменной `DATABASE_URL` и создаёт таблицы.
- `models.py` описывает модели: клиентов, сделки, полисы, платежи и т. д.

## Миграции

Для перевода денежных полей на `Decimal(12,2)` добавлена миграция
`migrations/001_decimal_fields.py`. Запустите её после обновления моделей:

```bash
python database/migrations/001_decimal_fields.py
```

Если в таблице `policy` отсутствует столбец `drive_folder_path`, выполните
миграцию `migrations/002_add_policy_drive_folder_path.py`:

```bash
python database/migrations/002_add_policy_drive_folder_path.py
```

Для работы в тестах база создаётся в памяти с помощью фикстуры `test_db` из `tests/conftest.py`.
