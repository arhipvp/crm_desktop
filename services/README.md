# Каталог `services`

Сервисные модули инкапсулируют бизнес‑логику приложения. Здесь реализованы функции работы с клиентами, сделками, расходами и интеграциями.

Основные файлы:

- `clients/client_service.py` – CRUD‑операции для клиентов.
- `deal_service.py` – управление сделками и связанными папками на Google Drive.
- `policies/policy_service.py` – логика страховых полисов.
- `task_crud.py`, `task_queue.py`, `task_notifications.py` – задачи и взаимодействие с Telegram‑ботом.
- `sheets_service.py` и `export_service.py` – экспорт данных в Excel/CSV и синхронизация с Google Sheets.
- `ai_*_service.py` – функции, использующие OpenAI для работы с текстом и PDF.

Дополнительные утилиты лежат в `folder_utils.py`, `query_utils.py`, `validators.py` и других файлах.
