import logging
import os

import openai
from database.models import Client, Deal, Policy, Task

logger = logging.getLogger(__name__)


def _gather_context(limit: int = 5) -> str:
    """Return short context about DB state."""
    try:
        clients = [c.name for c in Client.active().limit(limit)]
        deals = [str(d) for d in Deal.active().limit(limit)]
        policies = [p.policy_number for p in Policy.active().limit(limit)]
        tasks = [t.title for t in Task.active().limit(limit)]
    except Exception as exc:
        logger.error("Не удалось собрать контекст БД: %s", exc)
        return ""

    parts = [
        f"Клиенты: {', '.join(clients)}" if clients else "",
        f"Сделки: {', '.join(deals)}" if deals else "",
        f"Полисы: {', '.join(policies)}" if policies else "",
        f"Задачи: {', '.join(tasks)}" if tasks else "",
    ]
    return "\n".join(p for p in parts if p)


def ask_consultant(question: str) -> str:
    """Ask OpenAI a question with DB context and return the answer."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")

    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    context = _gather_context()
    messages = [
        {
            "role": "system",
            "content": (
                "Ты консультант CRM. Отвечай на вопросы пользователя на русском, "
                "используя переданный контекст базы данных."
            ),
        },
    ]
    if context:
        messages.append({"role": "system", "content": context})
    messages.append({"role": "user", "content": question})

    try:
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
        )
    except Exception as exc:
        logger.error("Ошибка запроса к OpenAI: %s", exc)
        raise RuntimeError(f"Ошибка запроса к OpenAI: {exc}") from exc

    return resp.choices[0].message.content.strip()
