# Архитектура CRM Desktop

CRM Desktop — настольное приложение на Python, объединяющее базу данных Peewee, слой сервисов и интерфейс на PySide6.

## Поток запуска

Точка входа `main.py` загружает переменные окружения, инициализирует базу данных и логирование, гарантирует наличие исполнителей и запускает GUI-цикл Qt【F:main.py†L8-L44】.

## Хранилище данных

Модели данных описаны в `database/models.py` и охватывают ключевые сущности CRM:
- `Client` хранит информацию о клиентах и пути к их папкам【F:database/models.py†L38-L48】.
- `Deal` связывает клиента с сделкой и содержит статус, описания и ссылки на папки【F:database/models.py†L64-L78】.
- `Policy` описывает страховые полисы, связанные с клиентами и сделками【F:database/models.py†L81-L101】.
- `Task` хранит задачи с телеграм-атрибутами для уведомлений исполнителей【F:database/models.py†L111-L126】.

Инициализация соединения происходит через `init_from_env`, поддерживающий SQLite и PostgreSQL【F:database/init.py†L52-L73】.

## Сервисный слой

Сервисы инкапсулируют бизнес-логику и обращаются к базовым моделям и внешним API:
- `client_service` нормализует данные, проверяет уникальность телефонов и создаёт локальные папки клиентов【F:services/clients/client_service.py†L192-L249】.
- `deal_service` добавляет сделки, формирует имя папки «Сделка - …» и сохраняет путь к ней【F:services/deal_service.py†L100-L166】.
- `calculation_service` ведёт расчёты по сделкам: добавление, фильтрацию и массовое удаление или обновление записей【F:services/calculation_service.py†L14-L72】【F:services/calculation_service.py†L89-L132】.
- `policy_service` проверяет дубликаты, создаёт локальную папку полиса (синхронизация с Google Drive выполняется вручную) и связывает платежи и уведомления【F:services/policies/policy_service.py†L117-L155】【F:services/policies/policy_service.py†L426-L593】【F:services/policies/policy_service.py†L260-L287】.

Финансовые сервисы управляют платежами и финансовыми записями:
- `payment_service` ведёт платежи, обеспечивает пагинацию и фильтры, выполняет каскадное удаление и массовую отметку оплаты【F:services/payment_service.py†L20-L223】.
- `income_service` фиксирует поступления, поддерживает фильтры и массовое удаление, уведомляет исполнителей【F:services/income_service.py†L65-L82】【F:services/income_service.py†L185-L260】.
- `expense_service` учитывает расходы, связывая их с платежами и полисами и предоставляя фильтры и массовые пометки【F:services/expense_service.py†L106-L166】.

- `executor_service` управляет исполнителями и назначениями на сделки, используя список ID из окружения【F:services/executor_service.py†L14-L66】.
- `task_service` управляет CRUD‑операциями задач, ставит их в очередь и отправляет уведомления исполнителям【F:services/task_crud.py†L83-L102】【F:services/task_queue.py†L18-L29】【F:services/task_notifications.py†L13-L34】.

## Интеграции и утилиты

- Работа с файлами и Google Drive реализована в `folder_utils.py`: модуль очищает имена и формирует локальные папки клиентов, сделок и полисов; синхронизация с Google Drive выполняется вручную【F:services/folder_utils.py†L58-L66】【F:services/folder_utils.py†L121-L136】【F:services/folder_utils.py†L200-L239】【F:services/folder_utils.py†L243-L260】.
- `dashboard_service` формирует сводную панель: базовую статистику, счётчики задач, напоминания по сделкам и истекающие полисы【F:services/dashboard_service.py†L9-L46】【F:services/dashboard_service.py†L62-L88】.
- Telegram‑уведомления формируются и отправляются через `telegram_service.py`【F:services/telegram_service.py†L15-L64】.
- Модуль `ai_consultant_service.py` собирает контекст из базы и задаёт вопросы модели OpenAI【F:services/ai_consultant_service.py†L10-L63】.
- Сервис `ai_policy_service` распознаёт полисы из PDF или текста через OpenAI и возвращает данные в формате JSON【F:services/policies/ai_policy_service.py†L333-L390】.
- `reso_table_service` импортирует таблицы выплат RESO и по выбранным строкам создаёт клиентов, полисы и доходы【F:services/reso_table_service.py†L53-L66】【F:services/reso_table_service.py†L96-L116】【F:services/reso_table_service.py†L143-L157】.
- Сервис `sheets_service.py` читает строки из листов, определённых идентификаторами `GOOGLE_SHEETS_TASKS_ID` и `GOOGLE_SHEETS_CALCULATIONS_ID`, и синхронизирует их с локальной БД через пары методов `fetch_tasks` / `sync_tasks` и `fetch_calculations` / `sync_calculations`【F:services/sheets_service.py†L52-L121】.
- `export_service.py` экспортирует ORM‑объекты в CSV-файлы с русскими заголовками столбцов【F:services/export_service.py†L1-L38】.
- Скрипт `backup.py` выгружает данные в SQL и Excel и загружает их на Google Drive【F:backup.py†L1-L108】.
- Конфигурация логирования сохраняет сообщения в файл и по умолчанию скрывает `SELECT`‑запросы фильтром `PeeweeFilter`; при `DETAILED_LOGGING=1` уровень принудительно повышается до `DEBUG`, а фильтр отключается【F:utils/logging_config.py†L17-L48】【F:README.md†L33-L66】.

## Пользовательский интерфейс

Главное окно собирает вкладки «Главная», «Клиенты», «Сделки», «Полисы», «Финансы» и «Задачи», используя виджеты PySide6【F:ui/main_window.py†L21-L55】.
