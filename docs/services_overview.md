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
- `get_payments_page` возвращает страницу платежей с поиском и сортировкой【F:services/payment_service.py†L47-L78】.
- `mark_payment_deleted` помечает платёж и связанные доходы/расходы удалёнными, `restore_payment` снимает пометку【F:services/payment_service.py†L81-L137】.
- `mark_payments_paid` массово отмечает платежи как оплаченные【F:services/payment_service.py†L140-L157】.

## income_service
- `get_incomes_page` поддерживает фильтрацию, сортировку и пагинацию доходов【F:services/income_service.py†L83-L143】.
- `mark_incomes_deleted` позволяет массово пометить доходы удалёнными【F:services/income_service.py†L72-L80】.
- `add_income` создаёт запись и уведомляет исполнителя при поступлении средств【F:services/income_service.py†L166-L195】.

## expense_service
- `get_expenses_page` возвращает расходы с фильтрами по дате, сделке и статусу【F:services/expense_service.py†L159-L199】.
- `mark_expenses_deleted` массово помечает расходы удалёнными【F:services/expense_service.py†L56-L63】.
- `add_expense` связывает расход с платежом и полисом, валидируя входные данные【F:services/expense_service.py†L70-L105】.

## executor_service
- `ensure_executors_from_env` создаёт записи исполнителей на основе `APPROVED_EXECUTOR_IDS` из переменных окружения【F:services/executor_service.py†L17-L21】.
- `assign_executor` очищает прежние привязки и создаёт новую запись с датой назначения【F:services/executor_service.py†L60-L66】.

## ai_consultant_service
- `_gather_context` собирает сведения из последних записей клиентов, сделок, полисов и задач【F:services/ai_consultant_service.py†L10-L27】.
- `ask_consultant` отправляет вопрос в OpenAI, добавляя контекст БД и выбранную модель【F:services/ai_consultant_service.py†L30-L63】.

## ai_policy_service
- `process_policy_text_with_ai` импортирует полис, отправляя текст или PDF в OpenAI и получая JSON‑структуру и протокол диалога【F:services/policies/ai_policy_service.py†L196-L209】【F:services/policies/ai_policy_service.py†L350-L359】.
- Системный промпт задаётся переменной окружения `AI_POLICY_PROMPT`【F:config.py†L24】【F:config.py†L49】【F:services/policies/ai_policy_service.py†L117-L119】.

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
