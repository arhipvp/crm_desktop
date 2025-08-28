"""Подпакет сервисов, связанных с полисами.

Не импортируем подмодули по умолчанию, чтобы не тянуть опциональные
зависимости (например, OpenAI) без необходимости.

Импортируйте напрямую:
    from services.policies import policy_service
    from services.policies import ai_policy_service
"""

__all__: list[str] = []
