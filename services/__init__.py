"""Пакет прикладных сервисов.

Умышленно не выполняем массовые импорты подмодулей на уровне пакета,
чтобы избежать тяжёлых транзитивных зависимостей (OpenAI, PySide6, pandas)
при простом ``import services`` или ``from services import X``.

Импортируйте нужные подмодули напрямую, например:
    from services import task_service as ts
    from services import executor_service as es
    from services.deal_service import get_deal_by_id
"""

__all__: list[str] = []
