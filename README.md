# CRM Desktop

Простое учебное CRM‑приложение на Python с использованием Peewee и PySide6. Позволяет вести базу клиентов, сделок, полисов и задач. Для работы с задачами есть отдельный Telegram‑бот. Файлы клиентов и сделок могут храниться в Google Drive.

## Структура каталогов

- `database/` – модели и инициализация БД.
- `services/` – бизнес‑логика и утилиты.
- `ui/` – Qt‑интерфейс приложения.
- `telegram_bot/` – код Telegram‑бота и Dockerfile.
- `tests/` – автотесты `pytest`.
- `resources/` – стили и статические файлы.
- `utils/` – вспомогательные модули.

## Пример `.env`

```env
DATABASE_URL=sqlite:///crm.db
TG_BOT_TOKEN=000000:telegram-bot-token
GOOGLE_DRIVE_LOCAL_ROOT=/path/to/drive
GOOGLE_CREDENTIALS=credentials.json
```

## Подготовка окружения

1. Создайте и активируйте виртуальное окружение:

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. Установите зависимости:

```bash
pip install -r requirements.txt
```

Файл `requirements.txt` уже содержит пакеты Google API (`google-api-python-client`, `google-auth`, `google-auth-oauthlib`) и Qt-библиотеку `PySide6`.

3. Скопируйте `.env.example` в `.env` и укажите свои значения.

## Запуск приложения

1. Подготовьте окружение (см. раздел выше).
2. Запустите интерфейс командой `python main.py`.

После запуска откроется вкладка **Главная** со сводной статистикой. В нижней части окна отображается строка состояния с количеством записей в текущей таблице. На дашборде показываются ближайшие задачи, заканчивающиеся полисы и напоминания по сделкам. Для каждой записи выводятся основные детали: дата, короткая заметка и связанные клиент, сделка или полис. Записи кликабельны и открывают подробную карточку объекта. Также отображаются счётчики задач, отправленных в Telegram, и задач, выполненных помощником, но ещё не подтверждённых.

## Запуск Telegram‑бота

Для работы бота необходимы переменные `DATABASE_URL` и `TG_BOT_TOKEN`.
Бот можно запустить локально:

```bash
python telegram_bot/bot.py
```


## Docker Compose

В репозитории есть `docker-compose.yml` для запуска PostgreSQL и бота.
Перед стартом создайте в корне файл `.env` с параметрами базы:

```env
POSTGRES_DB=crm
POSTGRES_USER=crm_user
POSTGRES_PASSWORD=crm_pass
```

Также создайте `telegram_bot/.env`:

```env
DATABASE_URL=postgres://crm_user:crm_pass@db:5432/crm
TG_BOT_TOKEN=000000:telegram-bot-token
GOOGLE_DRIVE_LOCAL_ROOT=/path/to/drive  # опционально
GOOGLE_CREDENTIALS=credentials.json     # опционально
```

Запустите сервисы командой:

```bash
docker-compose up -d
```

Сервис `db` использует том `db_data:/var/lib/postgresql/data`.
Контейнер `telegram_bot` монтирует
`G:/Мой диск/Клиенты:/data/clients` и `./logs:/app/logs`.

## Тесты

Запуск тестов выполняется командой:

```bash
pytest
```

## Работа с Google Drive

Функции загрузки и создания папок используют сервисный аккаунт Google.
Укажите путь к JSON‑файлу в переменной `GOOGLE_CREDENTIALS` и локальный
каталог синхронизации в `GOOGLE_DRIVE_LOCAL_ROOT`. Для корректной работы
необходимы библиотеки `google-api-python-client`, `google-auth` и
`google-auth-oauthlib` (уже перечислены в `requirements.txt`).

## Резервное копирование

Скрипт `backup.py` использует переменную окружения `DATABASE_URL` и
сохраняет файлы бэкапа в Google Drive.
