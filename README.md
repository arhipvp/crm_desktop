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
ADMIN_CHAT_ID=123456789  # Telegram ID администратора для уведомлений
APPROVED_EXECUTOR_IDS=111,222  # Telegram ID разрешённых исполнителей
GOOGLE_DRIVE_LOCAL_ROOT=/path/to/drive
GOOGLE_CREDENTIALS=credentials.json
GOOGLE_ROOT_FOLDER_ID=1-hTRZ7meDTGDQezoY_ydFkmXIng3gXFm
OPENAI_API_KEY=sk-example
OPENAI_BASE_URL=https://api.openai.com/v1  # например, https://api.together.xyz/v1
OPENAI_MODEL=gpt-4o  # например, gpt-3.5-turbo
AI_POLICY_PROMPT=
```

Переменная `ADMIN_CHAT_ID` задаёт Telegram‑ID администратора, которому бот отправляет уведомления.

## Подготовка окружения

1. Создайте и активируйте виртуальное окружение:

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

2. **Только для Linux:** перед установкой зависимостей выполните:

```bash
sudo apt-get update
sudo apt-get install -y libegl1 libgl1
```

Эти библиотеки необходимы для корректной работы `PySide6` и автотестов.

3. Установите зависимости:

```bash
pip install -r requirements.txt
```

Файл `requirements.txt` уже содержит пакеты Google API (`google-api-python-client`, `google-auth`, `google-auth-oauthlib`) и Qt-библиотеку `PySide6`.

4. Скопируйте `.env.example` в `.env` и укажите свои значения.

## Запуск приложения

1. Подготовьте окружение (см. раздел выше).
2. Запустите интерфейс командой `python main.py`.

После запуска откроется вкладка **Главная** со сводной статистикой. В нижней части окна отображается строка состояния с количеством записей в текущей таблице. На дашборде показываются ближайшие задачи, заканчивающиеся полисы и напоминания по сделкам. Для каждой записи выводятся основные детали: дата, короткая заметка и связанные клиент, сделка или полис. Записи кликабельны и открывают подробную карточку объекта. Дополнительно выводятся счётчики задач: сколько отправлено в Telegram, сколько сейчас в работе и сколько ожидают подтверждения.

## Запуск Telegram‑бота

Бот работает только внутри Docker‑контейнера. Перед запуском
скопируйте `telegram_bot/.env.example` в `telegram_bot/.env` и
укажите значения хотя бы для переменных `DATABASE_URL` и `TG_BOT_TOKEN`.
В деталях сделки есть кнопка «Отправить задачу исполнителю». Она
создаёт новую задачу, сразу отправляет её в Telegram выбранному
исполнителю и помечает выполненной. Сообщение содержит кнопки
«Добавить расчёт», «Выполнить» и «Написать вопрос». Список
незавершённых задач можно получить командой `/tasks`.
В таблице задач появилась кнопка «Напомнить»,
которая возвращает выбранные задачи в очередь и
повторно отправляет уведомление исполнителю.

## Docker Compose

В репозитории есть `docker-compose.yml` для запуска PostgreSQL и бота.
Перед стартом создайте в корне файл `.env` с параметрами базы:

```env
POSTGRES_DB=crm
POSTGRES_USER=crm_user
POSTGRES_PASSWORD=crm_pass
```

`telegram_bot/.env` пример (такой же файл `.env.example` уже есть в каталоге):

```env
DATABASE_URL=postgres://crm_user:crm_pass@db:5432/crm
TG_BOT_TOKEN=000000:telegram-bot-token
APPROVED_EXECUTOR_IDS=111,222
GOOGLE_DRIVE_LOCAL_ROOT=/path/to/drive  # опционально
GOOGLE_CREDENTIALS=credentials.json     # опционально
```

Запустите сервисы командой:

```bash
docker-compose up -d
```

Сервис `db` использует том `db_data:/var/lib/postgresql/data`.

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

При создании клиентов и сделок папки создаются сразу в облаке, а локальный
путь просто сохраняется и появится после синхронизации Google Drive. Если при
открытии папки её нет на диске, приложение предложит выбрать каталог вручную
или отменить операцию.

## Резервное копирование

Скрипт `backup.py` использует переменную окружения `DATABASE_URL` и
сохраняет файлы бэкапа в Google Drive.
