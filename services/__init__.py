"""Пакет прикладных сервисов.

Умышленно не выполняем массовые импорты подмодулей на уровне пакета,
чтобы избежать тяжёлых транзитивных зависимостей (OpenAI, PySide6, pandas)
при простом ``import services`` или ``from services import X``.

Импортируйте нужные подмодули напрямую, например:
    from services import task_crud as tc
    from services import task_queue as tq
    from services.task_notifications import notify_task
"""

__all__: list[str] = []
