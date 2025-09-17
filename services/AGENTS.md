# Руководство для `services`

- Все операции записи в базу данных оборачивайте в `db.atomic()` для обеспечения транзакционности:

```python
from playhouse.shortcuts import db  # пример, используйте фактический объект
with db.atomic():
    ...
```

- Для повторяющихся запросов используйте утилиты из [`query_utils.py`](./query_utils.py).

## Тесты
При изменениях в сервисах запускайте релевантные тесты с таймаутом:

```bash
PYTEST_TIMEOUT=120 pytest -vv tests/test_policy_payments.py
PYTEST_TIMEOUT=120 pytest -vv tests/test_expense_service.py
PYTEST_TIMEOUT=120 pytest -vv tests/test_income_service.py
```

Эти тесты проверяют целостность транзакций, корректность расчетов по расходам и синхронизацию платежей между сервисами.
