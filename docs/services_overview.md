# Обзор сервисного слоя

Сервисные модули содержат бизнес‑логику и интеграции.

## client_service
- допустимые поля описаны в `CLIENT_ALLOWED_FIELDS`; валидация телефонов предотвращает дублирование【F:services/clients/client_service.py†L15-L97】.
- `add_client` нормализует имя и телефон, создаёт только локальную папку и сохраняет путь без ссылки; синхронизация с Google Drive выполняется вручную【F:services/clients/client_service.py†L187-L244】.

## deal_service
- `add_deal` создаёт сделку, формирует запись в журнале и создаёт локальную папку «Сделка - …»【F:services/deal_service.py†L100-L166】.
- `add_deal_from_policy` строит описание сделки из данных полиса и связывает их между собой【F:services/deal_service.py†L169-L216】.

## calculation_service
- `add_calculation` добавляет расчёт к сделке, ограничивает набор полей и уведомляет администратора【F:services/calculation_service.py†L14-L34】.
- `build_calculation_query` формирует запрос с поиском, фильтрами и сортировкой расчётов сделки【F:services/calculation_service.py†L37-L72】.
- `mark_calculations_deleted` массово помечает выбранные расчёты удалёнными【F:services/calculation_service.py†L89-L98】.
- `update_calculation` изменяет допустимые параметры расчёта и, при необходимости, привязывает его к другой сделке【F:services/calculation_service.py†L108-L132】.

## policy_service
- `_check_duplicate_policy` предотвращает создание полиса с существующим номером【F:services/policies/policy_service.py†L108-L146】.
- `add_policy` создаёт локальную папку полиса (синхронизация с Google Drive выполняется вручную), привязывает платежи и уведомляет исполнителя【F:services/policies/policy_service.py†L426-L592】.

## payment_service
- Полный набор CRUD‑операций: `add_payment`, `update_payment`, `mark_payment_deleted` и `restore_payment`【F:services/payment_service.py†L156-L203】【F:services/payment_service.py†L229-L295】【F:services/payment_service.py†L382-L419】.
- `get_payments_page` предоставляет постраничный вывод с фильтрами и сортировкой через `apply_payment_filters` и `build_payment_query`【F:services/payment_service.py†L120-L153】【F:services/payment_service.py†L422-L476】.
- `mark_payments_paid` проставляет фактическую дату оплаты (текущую или переданную) только тем платежам, у которых она ещё не заполнена【F:services/payment_service.py†L206-L223】.

## income_service
- CRUD и массовые пометки: `add_income`, `update_income`, `mark_income_deleted` и `mark_incomes_deleted`【F:services/income_service.py†L185-L215】【F:services/income_service.py†L220-L260】【F:services/income_service.py†L65-L72】【F:services/income_service.py†L74-L82】.
- `get_incomes_page` и `apply_income_filters` обеспечивают фильтрацию, сортировку и пагинацию доходов【F:services/income_service.py†L83-L143】【F:services/income_service.py†L238-L256】.
- `_notify_income_received` уведомляет исполнителя о поступлении средств при создании или обновлении записи【F:services/income_service.py†L145-L162】.

## expense_service
- CRUD и массовые пометки: `add_expense`, `update_expense`, `mark_expense_deleted` и `mark_expenses_deleted`【F:services/expense_service.py†L125-L166】【F:services/expense_service.py†L171-L229】【F:services/expense_service.py†L106-L113】【F:services/expense_service.py†L115-L120】.
- `get_expenses_page` и `apply_expense_filters` предоставляют фильтрацию по дате, сделке и статусу с пагинацией【F:services/expense_service.py†L235-L294】【F:services/expense_service.py†L296-L345】.
- Каждая запись связывается с платежом и полисом для консистентности финансовых данных【F:services/expense_service.py†L158-L160】【F:services/expense_service.py†L207-L223】.

## executor_service
- `ensure_executors_from_env` создаёт записи исполнителей на основе `APPROVED_EXECUTOR_IDS` из переменных окружения【F:services/executor_service.py†L17-L21】.
- `assign_executor` очищает прежние привязки и создаёт новую запись с датой назначения【F:services/executor_service.py†L60-L66】.

## ai_consultant_service
- `_gather_context` собирает сведения из последних записей клиентов, сделок, полисов и задач【F:services/ai_consultant_service.py†L10-L27】.
- `ask_consultant` отправляет вопрос в OpenAI, добавляя контекст БД и выбранную модель【F:services/ai_consultant_service.py†L30-L63】.

## ai_policy_service
- `process_policy_text_with_ai` импортирует полис, отправляя текст или PDF в OpenAI и получая JSON‑структуру и протокол диалога【F:services/policies/ai_policy_service.py†L367-L390】.
- Системный промпт задаётся переменной окружения `AI_POLICY_PROMPT`【F:config.py†L25-L25】【F:config.py†L57-L57】【F:services/policies/ai_policy_service.py†L117-L119】.
- Основные правила дефолтного промпта: не придумывать данные, объединять полисы только при совпадении объекта/периода/страховой, жёстко фиксировать `note` = «импортировано через ChatGPT», держать `actual_payment_date` равным `payment_date`, оставлять `contractor` пустым, тянуть VIN при наличии, соблюдать формат дат ISO и ограничение `end_date ≤ start_date + 1 год`. При необходимости можно переопределить любую из этих инструкций через `AI_POLICY_PROMPT`.
- Полный текст промпта лежит в [`services/policies/ai_policy_service.py`](../services/policies/ai_policy_service.py) внутри константы `DEFAULT_PROMPT`.
- Для многострочного собственного промпта при генерации `.env` удобно применять here-doc (`cat <<'EOF' >> .env`), либо хранить текст в отдельном файле и подставлять его при запуске: `AI_POLICY_PROMPT="$(<prompt.txt)"`.

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

## reso_table_service
- `import_reso_payouts` загружает таблицы выплат RESO и позволяет выбирать строки, из которых создаются клиенты, полисы и доходы【F:services/reso_table_service.py†L53-L66】【F:services/reso_table_service.py†L96-L116】【F:services/reso_table_service.py†L143-L157】.

## folder_utils
- `sanitize_name` удаляет недопустимые символы из имен файлов и папок【F:services/folder_utils.py†L58-L66】.
- `create_client_drive_folder` принимает адаптер `DriveGateway`, создаёт локальную папку клиента в каталоге синхронизации и возвращает кортеж `(локальный путь, опциональная ссылка)`, где ссылка может быть `None`【F:services/folder_utils.py†L121-L142】.
- `create_deal_folder` строит путь вида `Клиенты/<Клиент>/Сделка - …`, используя `DriveGateway`, гарантирует наличие папки и возвращает кортеж `(локальный путь, опциональная ссылка)`; в текущей реализации ссылка отсутствует (`None`)【F:services/folder_utils.py†L147-L170】.
- `create_policy_folder` через `DriveGateway` создаёт локальную папку полиса и возвращает путь в каталоге синхронизации【F:services/folder_utils.py†L175-L198】.

## sheets_service
- `read_sheet` и `append_rows` обеспечивают чтение и дозапись таблиц Google Sheets, идентификаторы которых задаются переменными окружения `GOOGLE_SHEETS_TASKS_ID` и `GOOGLE_SHEETS_CALCULATIONS_ID`【F:services/sheets_service.py†L24-L59】.

## export_service
- `export_objects_to_csv` выгружает ORM‑объекты в CSV, применяя русские заголовки из `RU_HEADERS` и возвращая число экспортированных строк【F:services/export_service.py†L1-L38】.
