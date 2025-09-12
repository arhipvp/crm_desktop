# Обзор сервисного слоя

Сервисные модули содержат бизнес‑логику и интеграции.

## client_service
- допустимые поля описаны в `CLIENT_ALLOWED_FIELDS`; валидация телефонов предотвращает дублирование【F:services/clients/client_service.py†L15-L97】.
- `add_client` нормализует имя и телефон, создаёт только локальную папку и сохраняет путь без ссылки; синхронизация с Google Drive выполняется вручную【F:services/clients/client_service.py†L156-L163】.

## deal_service
- `add_deal` создаёт сделку, формирует запись в журнале и создаёт локальную папку «Сделка - …»【F:services/deal_service.py†L56-L123】.
- `add_deal_from_policy` строит описание сделки из данных полиса и связывает их между собой【F:services/deal_service.py†L137-L160】.

## executor_service
- `ensure_executors_from_env` создаёт записи исполнителей на основе `APPROVED_EXECUTOR_IDS` из переменных окружения【F:services/executor_service.py†L17-L21】.
- `assign_executor` очищает прежние привязки и создаёт новую запись с датой назначения【F:services/executor_service.py†L60-L66】.

## ai_consultant_service
- `_gather_context` собирает сведения из последних записей клиентов, сделок, полисов и задач【F:services/ai_consultant_service.py†L10-L27】.
- `ask_consultant` отправляет вопрос в OpenAI, добавляя контекст БД и выбранную модель【F:services/ai_consultant_service.py†L30-L63】.

## telegram_service
- `format_exec_task` формирует HTML‑сообщение и inline‑клавиатуру для задачи исполнителю【F:services/telegram_service.py†L15-L48】.
- `send_exec_task` передаёт сообщение через бот и сохраняет идентификаторы для обратной связи【F:services/telegram_service.py†L51-L64】.

## folder_utils
- `sanitize_name` удаляет недопустимые символы из имен файлов и папок【F:services/folder_utils.py†L58-L66】.
- `create_client_drive_folder` создаёт локальную папку клиента в каталоге синхронизации и возвращает путь【F:services/folder_utils.py†L121-L136】.
- `create_deal_folder` строит путь вида `Клиенты/<Клиент>/Сделка - …` и гарантирует наличие папки【F:services/folder_utils.py†L200-L239】.
