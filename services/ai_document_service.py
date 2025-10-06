"""Сервис для суммаризации произвольных документов через OpenAI."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Iterable, List

import openai

from config import get_settings
from services.policies.ai_policy_service import _read_text


logger = logging.getLogger(__name__)

settings = get_settings()


DEFAULT_PROMPT = """Ты — ассистент CRM, который помогает менеджеру составить краткую заметку по документам.

На вход подаются фрагменты текста из разных файлов. Для каждого файла тебе нужно:
1. Внимательно прочитать содержимое.
2. Сформулировать краткую, структурированную заметку (до 8 предложений) о ключевой информации.
3. Отдельно перечислить важные даты и суммы, если они встречаются.
4. Если информации слишком мало, честно укажи, что данных недостаточно для выводов.

Формат ответа:
— Краткий итог: <основные выводы одной строкой>.
— Подробности: <несколько предложений или маркированных пунктов>.
— Даты и суммы: <выдели даты и суммы списком либо напиши «нет данных»>.

Не придумывай факты, которых нет в тексте. Пиши на русском языке."""


def _get_prompt() -> str:
    """Вернуть системный промпт для суммаризации документов."""

    return settings.ai_document_prompt or DEFAULT_PROMPT


def _log_conversation(label: str, messages: List[dict]) -> str:
    """Логировать диалог с OpenAI и вернуть его текст."""

    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    logger.info("Диалог с OpenAI для %s:\n%s", label, transcript)
    return transcript


class AiDocumentError(ValueError):
    """Ошибка суммаризации, содержащая протокол диалога."""

    def __init__(self, message: str, messages: List[dict], transcript: str):
        super().__init__(message)
        self.messages = messages
        self.transcript = transcript


def _collect_initial_messages(text: str) -> List[dict]:
    return [
        {"role": "system", "content": _get_prompt()},
        {"role": "user", "content": text[:16000]},
    ]


def _check_cancel(callback: Callable[[], bool] | None) -> None:
    if callback and callback():
        logger.info("Запрос к OpenAI отменен пользователем")
        raise InterruptedError("Запрос к OpenAI отменен")


def _stream_completion(
    client: openai.OpenAI,
    *,
    model: str,
    messages: List[dict],
    progress_cb: Callable[[str, str], None] | None,
    cancel_cb: Callable[[], bool] | None,
) -> str:
    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        stream=True,
    )
    parts: List[str] = []
    try:
        for chunk in stream:
            _check_cancel(cancel_cb)
            delta = chunk.choices[0].delta if chunk.choices else None
            content = getattr(delta, "content", None) if delta else None
            if not content:
                continue
            parts.append(content)
            if progress_cb:
                progress_cb("assistant", content)
    finally:
        close_method = getattr(stream, "close", None)
        if callable(close_method):
            close_method()
    return "".join(parts)


def _plain_completion(
    client: openai.OpenAI,
    *,
    model: str,
    messages: List[dict],
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
    )
    choice = response.choices[0]
    message = getattr(choice, "message", None)
    return (getattr(message, "content", None) or "").strip()


def summarize_documents_interactive(
    text: str,
    *,
    progress_cb: Callable[[str, str], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
    label: str = "documents",
) -> tuple[str, str]:
    """Сформировать заметку по тексту и вернуть её вместе с расшифровкой диалога."""

    if not text.strip():
        return "", ""

    messages = _collect_initial_messages(text)

    if progress_cb:
        for message in messages:
            _check_cancel(cancel_cb)
            progress_cb(message["role"], message["content"])

    api_key = settings.openai_api_key
    if not api_key:
        raise ValueError("OPENAI_API_KEY не задан")

    client = openai.OpenAI(api_key=api_key, base_url=settings.openai_base_url)

    try:
        _check_cancel(cancel_cb)
        if progress_cb:
            note = _stream_completion(
                client,
                model=settings.openai_model,
                messages=messages,
                progress_cb=progress_cb,
                cancel_cb=cancel_cb,
            )
        else:
            note = _plain_completion(
                client,
                model=settings.openai_model,
                messages=messages,
            )
    except InterruptedError:
        raise
    except Exception as exc:  # pragma: no cover - защитный код
        transcript = _log_conversation(label, messages)
        raise AiDocumentError(
            f"Ошибка при обращении к OpenAI: {exc}", messages, transcript
        ) from exc

    messages.append({"role": "assistant", "content": note})
    _check_cancel(cancel_cb)
    transcript = _log_conversation(label, messages)
    return note, transcript


def _iter_paths(paths: Iterable[str]) -> Iterable[Path]:
    for raw_path in paths:
        yield Path(raw_path)


def summarize_document_files(paths: list[str]) -> tuple[str, str]:
    """Прочитать файлы, объединить текст и отправить его на суммаризацию."""

    if not paths:
        return "", ""

    collected: list[tuple[str, str]] = []
    for path in _iter_paths(paths):
        text = _read_text(str(path))
        collected.append((path.name, text))

    if not any(text.strip() for _, text in collected):
        return "", ""

    parts: list[str] = []
    for name, text in collected:
        part = f"### {name}\n{text}".strip()
        parts.append(part)

    combined_text = "\n\n".join(parts)

    label = ", ".join(name for name, _ in collected)
    try:
        return summarize_documents_interactive(combined_text, label=label)
    except AiDocumentError as exc:
        raise ValueError(
            f"Не удалось подготовить заметку по файлам {label}: {exc}\nДиалог:\n{exc.transcript}"
        ) from exc

