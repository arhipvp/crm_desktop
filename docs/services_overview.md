# Обзор сервисного слоя

Сервисные модули содержат бизнес‑логику и интеграции.

## client_service
- допустимые поля описаны в `CLIENT_ALLOWED_FIELDS`; валидация телефонов предотвращает дублирование【F:services/clients/client_service.py†L15-L97】.
- `add_client` нормализует имя и телефон, создаёт только локальную папку и сохраняет путь без ссылки; синхронизация с Google Drive выполняется вручную【F:services/clients/client_service.py†L156-L163】.

## deal_service
- `add_deal` создаёт сделку, формирует запись в журнале и создаёт локальную папку «Сделка - …»【F:services/deal_service.py†L56-L123】.
- `add_deal_from_policy` строит описание сделки из данных полиса и связывает их между собой【F:services/deal_service.py†L137-L160】.

## policy_service
- `_check_duplicate_policy` предотвращает создание полиса с существующим номером【F:services/policies/policy_service.py†L108-L146】.
- `add_policy` создаёт папку, привязывает платежи и уведомляет исполнителя【F:services/policies/policy_service.py†L286-L403】【F:services/policies/policy_service.py†L268-L280】.

## payment_service
- Полный набор CRUD‑операций: `add_payment`, `update_payment`, `mark_payment_deleted` и `restore_payment`【F:services/payment_service.py†L81-L137】【F:services/payment_service.py†L163-L177】【F:services/payment_service.py†L277-L305】.
- `get_payments_page` предоставляет постраничный вывод с фильтрами и сортировкой через `apply_payment_filters` и `build_payment_query`【F:services/payment_service.py†L47-L78】【F:services/payment_service.py†L307-L360】.
- `mark_payments_paid` массово отмечает платежи как оплаченные и каскадно обновляет связанные записи【F:services/payment_service.py†L140-L157】.

## income_service
- CRUD и массовые пометки: `add_income`, `update_income`, `mark_income_deleted` и `mark_incomes_deleted`【F:services/income_service.py†L64-L80】【F:services/income_service.py†L166-L195】【F:services/income_service.py†L200-L235】.
- `get_incomes_page` и `apply_income_filters` обеспечивают фильтрацию, сортировку и пагинацию доходов【F:services/income_service.py†L83-L143】【F:services/income_service.py†L238-L256】.
- `_notify_income_received` уведомляет исполнителя о поступлении средств при создании или обновлении записи【F:services/income_service.py†L145-L162】【F:services/income_service.py†L233-L235】.

## expense_service
- CRUD и массовые пометки: `add_expense`, `update_expense`, `mark_expense_deleted` и `mark_expenses_deleted`【F:services/expense_service.py†L48-L64】【F:services/expense_service.py†L70-L108】【F:services/expense_service.py†L114-L153】.
- `get_expenses_page` и `apply_expense_filters` предоставляют фильтрацию по дате, сделке и статусу с пагинацией【F:services/expense_service.py†L159-L200】【F:services/expense_service.py†L203-L244】.
- Каждая запись связывается с платежом и полисом для консистентности финансовых данных【F:services/expense_service.py†L80-L105】.

## executor_service
- `ensure_executors_from_env` создаёт записи исполнителей на основе `APPROVED_EXECUTOR_IDS` из переменных окружения【F:services/executor_service.py†L17-L21】.
- `assign_executor` очищает прежние привязки и создаёт новую запись с датой назначения【F:services/executor_service.py†L60-L66】.

## ai_consultant_service
- `_gather_context` собирает сведения из последних записей клиентов, сделок, полисов и задач【F:services/ai_consultant_service.py†L10-L27】.
- `ask_consultant` отправляет вопрос в OpenAI, добавляя контекст БД и выбранную модель【F:services/ai_consultant_service.py†L30-L63】.

## ai_policy_service
- `process_policy_text_with_ai` импортирует полис, отправляя текст или PDF в OpenAI и получая JSON‑структуру и протокол диалога【F:services/policies/ai_policy_service.py†L196-L209】【F:services/policies/ai_policy_service.py†L350-L359】.
- Системный промпт задаётся переменной окружения `AI_POLICY_PROMPT`【F:config.py†L24】【F:config.py†L49】【F:services/policies/ai_policy_service.py†L117-L119】.

## dashboard_service
- `get_basic_stats` возвращает количество клиентов, сделок, полисов и задач【F:services/dashboard_service.py†L9-L18】.
- `count_assistant_tasks`, `count_sent_tasks`, `count_working_tasks` и `count_unconfirmed_tasks` дают сводные счётчики задач【F:services/dashboard_service.py†L20-L46】.
- `get_upcoming_deal_reminders` возвращает ближайшие напоминания по открытым сделкам【F:services/dashboard_service.py†L70-L88】.
- `get_expiring_policies` показывает полисы с истекающим сроком действия【F:services/dashboard_service.py†L62-L69】.

## telegram_service
- `format_exec_task` формирует HTML‑сообщение и inline‑клавиатуру для задачи исполнителю【F:services/telegram_service.py†L15-L48】.
- `send_exec_task` передаёт сообщение через бот и сохраняет идентификаторы для обратной связи【F:services/telegram_service.py†L51-L64】.

## task_service
- `add_task` создаёт задачу и уведомляет администратора【F:services/task_crud.py†L83-L102】.
- `queue_task` ставит задачу в очередь на отправку исполнителю【F:services/task_queue.py†L18-L29】.
- `notify_task` переотправляет задачу исполнителю или возвращает её в очередь【F:services/task_notifications.py†L13-L34】.

## folder_utils
- `sanitize_name` удаляет недопустимые символы из имен файлов и папок【F:services/folder_utils.py†L58-L66】.
- `create_client_drive_folder` создаёт локальную папку клиента в каталоге синхронизации и возвращает путь【F:services/folder_utils.py†L121-L136】.
- `create_deal_folder` строит путь вида `Клиенты/<Клиент>/Сделка - …` и гарантирует наличие папки【F:services/folder_utils.py†L200-L239】.
