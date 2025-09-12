# Архитектура CRM Desktop

CRM Desktop — настольное приложение на Python, объединяющее базу данных Peewee, слой сервисов и интерфейс на PySide6.

## Поток запуска

Точка входа `main.py` загружает переменные окружения, инициализирует базу данных и логирование, гарантирует наличие исполнителей и запускает GUI-цикл Qt【F:main.py†L8-L44】.

## Хранилище данных

Модели данных описаны в `database/models.py` и охватывают ключевые сущности CRM:
- `Client` хранит информацию о клиентах и пути к их папкам【F:database/models.py†L12-L24】.
- `Deal` связывает клиента с сделкой и содержит статус, описания и ссылки на папки【F:database/models.py†L27-L49】.
- `Policy` описывает страховые полисы, связанные с клиентами и сделками【F:database/models.py†L53-L74】.
- `Task` хранит задачи с телеграм-атрибутами для уведомлений исполнителей【F:database/models.py†L86-L103】.

Инициализация соединения происходит через `init_from_env`, поддерживающий SQLite и PostgreSQL【F:database/init.py†L52-L73】.

## Сервисный слой

Сервисы инкапсулируют бизнес-логику и обращаются к базовым моделям и внешним API:
- `client_service` нормализует данные, проверяет уникальность телефонов и создаёт локальные папки клиентов【F:services/clients/client_service.py†L103-L141】.
- `deal_service` добавляет сделки, формирует имя папки «Сделка - …» и сохраняет путь к ней【F:services/deal_service.py†L56-L123】.
- `executor_service` управляет исполнителями и назначениями на сделки, используя список ID из окружения【F:services/executor_service.py†L14-L66】.
- `task_service` управляет CRUD‑операциями задач, ставит их в очередь и отправляет уведомления исполнителям【F:services/task_crud.py†L83-L102】【F:services/task_queue.py†L18-L29】【F:services/task_notifications.py†L13-L34】.

## Интеграции и утилиты

- Работа с файлами и Google Drive реализована в `folder_utils.py`: очистка имён и создание локальных папок клиентов и сделок【F:services/folder_utils.py†L58-L66】【F:services/folder_utils.py†L121-L136】【F:services/folder_utils.py†L200-L239】.
- Telegram‑уведомления формируются и отправляются через `telegram_service.py`【F:services/telegram_service.py†L15-L64】.
- Модуль `ai_consultant_service.py` собирает контекст из базы и задаёт вопросы модели OpenAI【F:services/ai_consultant_service.py†L10-L63】.
- Скрипт `backup.py` выгружает данные в SQL и Excel и загружает их на Google Drive【F:backup.py†L1-L108】.
- Конфигурация логирования сохраняет сообщения в файл и подавляет «SELECT» от Peewee【F:utils/logging_config.py†L17-L48】.

## Пользовательский интерфейс

Главное окно собирает вкладки «Главная», «Клиенты», «Сделки», «Полисы», «Финансы» и «Задачи», используя виджеты PySide6【F:ui/main_window.py†L21-L55】.
