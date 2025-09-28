import json
import logging
from typing import Callable, List, Tuple

import openai
from PyPDF2 import PdfReader

from config import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)

try:
    from jsonschema import ValidationError, validate
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    ValidationError = Exception

    def validate(instance, schema):  # type: ignore[unused-argument]
        """Резервная проверка, если jsonschema не установлен."""
        logger.warning(
            "Пакет 'jsonschema' не установлен, проверка схемы пропущена"
        )

DEFAULT_PROMPT = """Ты — ассистент, отвечающий за импорт данных из страховых полисов в CRM. На основе загруженного документа (PDF, скан или текст) необходимо сформировать один JSON строго по следующему шаблону:
{
  "client_name": "Тестовый клиент",
  "policy": {
    "policy_number": "TEST-002-ZXC",
    "insurance_type": "КАСКО",
    "insurance_company": "Ингосстрах",
    "contractor": "",
    "sales_channel": "",
    "start_date": "2025-07-01",
    "end_date": "2026-06-30",
    "vehicle_brand": "Hyundai",
    "vehicle_model": "Solaris",
    "vehicle_vin": "Z94CB41ABFR123456",
    "note": "импортировано через ChatGPT"
  },
  "payments": [
    {
      "amount": 2000,
      "payment_date": "2025-07-05",
      "actual_payment_date": "2025-07-05"
    }
  ]
}
📌 ОБЩИЕ ПРАВИЛА
Только по документу. Никаких догадок или вымышленных данных.

Один полис = один JSON. Даже если имя клиента одно.

Объединяй полисы в один JSON только если:
Один и тот же страхуемый объект,
Совпадает период страхования,
Одна страховая компания.

🧠 СПЕЦИАЛЬНЫЕ ПРАВИЛА
note
Всегда "импортировано через ChatGPT" — без исключений.

actual_payment_date
Всегда равен payment_date, даже если явно не указан.

contractor
Всегда пустое поле. Никогда не заполняется, даже если страхователь указан в документе.

sales_channel
Если в документе указаны фамилии агентов ("Марьинских", "Лежнев", "Музыченко") — это канал продаж

insurance_type
Если страхуется жизнь и здоровье заемщика по ипотеке — указывать "Ипотека".
Если можно определить тип полиса (например, "Жизнь" или "Квартира"), указывать его.
Не использовать "Несчастный случай", даже если он явно указан.

vehicle_vin
Если указан — обязательно включить.
Если не указан — оставить пустым ("").

payments
Если есть общий график — использовать его.
Если указаны только частичные платежи — использовать их.
Если вообще нет дат платежей — считать, что первый платеж = start_date.

Формат дат
Всегда в ISO-формате: YYYY-MM-DD.
Дата окончания полиса не может быть больше даты начала + 1 год. Если полис больше чем на 1 год, то ставь дату окончания полиса = дата начала действия + 1 год

🧹 ОБРАБОТКА ТЕКСТА
Удаляй пробелы, табуляции, переносы строк и мусор.
Значения полей должны быть очищены и отформатированы.
Не допускаются значения null, -, N/A, undefined и т.п.

📋 ПОРЯДОК ОБРАБОТКИ
Определи количество полисов в документе.
Для каждого полиса:
Определи объект страхования, страховую, тип, даты.
Если объект, даты и страховая совпадают — объединяй номера через запятую в policy_number.
Иначе — создавай отдельный JSON.
Извлеки и очисти все поля по правилам выше.
Сформируй итоговый JSON.

✅ ЧЕКЛИСТ ПЕРЕД ВЫДАЧЕЙ JSON
 note = "импортировано через ChatGPT"
 actual_payment_date = payment_date
 Все даты в формате YYYY-MM-DD
 VIN указан? → обязателен
 contractor = "" всегда
 insurance_type корректно определён (при возможности)
 Не используется "Несчастный случай"
 Несколько полисов объединены корректно?
 Нет null, -, N/A и прочего
"""


def _get_prompt() -> str:
    """Вернуть системный промпт для распознавания полисов."""
    return settings.ai_policy_prompt or DEFAULT_PROMPT


def _log_conversation(path: str, messages: List[dict]) -> str:
    """Сохранить диалог с OpenAI для отладки и вернуть транскрипт."""
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    logger.info("Диалог с OpenAI для %s:\n%s", path, transcript)
    return transcript

# Количество попыток получить корректный JSON от модели
MAX_ATTEMPTS = 3

# Дополнительная инструкция, отправляемая модели при ошибке разбора JSON
REMINDER = (
    "Ответ должен содержать только один валидный JSON без каких-либо пояснений."
)

# JSON‑схема результата для функции OpenAI и валидации ответа
POLICY_SCHEMA = {
    "type": "object",
    "properties": {
        "client_name": {"type": "string"},
        "policy": {
            "type": "object",
            "properties": {
                "policy_number": {"type": "string"},
                "insurance_type": {"type": "string"},
                "insurance_company": {"type": "string"},
                "contractor": {"type": "string"},
                "sales_channel": {"type": "string"},
                "start_date": {"type": "string"},
                "end_date": {"type": "string"},
                "vehicle_brand": {"type": "string"},
                "vehicle_model": {"type": "string"},
                "vehicle_vin": {"type": "string"},
                "note": {"type": "string"},
            },
            "required": [
                "policy_number",
                "insurance_type",
                "insurance_company",
                "contractor",
                "sales_channel",
                "start_date",
                "end_date",
                "vehicle_brand",
                "vehicle_model",
                "vehicle_vin",
                "note",
            ],
            "additionalProperties": False,
        },
        "payments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "payment_date": {"type": "string"},
                    "actual_payment_date": {"type": "string"},
                },
                "required": ["amount", "payment_date", "actual_payment_date"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["client_name", "policy", "payments"],
    "additionalProperties": False,
}

POLICY_FUNCTION = {
    "name": "extract_policy",
    "description": "Структурированный JSON результата распознавания полиса",
    "parameters": POLICY_SCHEMA,
}


def _read_text(path: str) -> str:
    """Извлечь текст из PDF или текстового файла."""
    if path.lower().endswith(".pdf"):
        try:
            reader = PdfReader(path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text:
                return text
        except Exception as e:
            logger.warning("Не удалось прочитать PDF %s: %s", path, e)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "ignore")


class AiPolicyError(ValueError):
    """Вызывается, когда модель не смогла сформировать корректный JSON."""

    def __init__(self, message: str, messages: List[dict], transcript: str):
        super().__init__(message)
        self.messages = messages
        self.transcript = transcript


def _chat(
    messages: List[dict],
    progress_cb: Callable[[str, str], None] | None = None,
    *,
    cancel_cb: Callable[[], bool] | None = None,
) -> str:
    api_key = settings.openai_api_key
    if not api_key:
        raise ValueError("OPENAI_API_KEY не задан")
    base_url = settings.openai_base_url
    model = settings.openai_model
    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    tools = [{"type": "function", "function": POLICY_FUNCTION}]
    tool_choice = {"type": "function", "function": {"name": POLICY_FUNCTION["name"]}}

    def _check_cancel() -> None:
        if cancel_cb and cancel_cb():
            logger.info("Отмена запроса к OpenAI по инициативе пользователя")
            raise InterruptedError("Запрос к OpenAI отменен")

    if progress_cb:
        _check_cancel()
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            stream=True,
            tools=tools,
            tool_choice=tool_choice,
        )
        parts: List[str] = []
        try:
            for chunk in stream:
                _check_cancel()
                delta = chunk.choices[0].delta if chunk.choices else None
                tool_calls = delta.tool_calls if delta else None
                if not tool_calls:
                    continue
                func = tool_calls[0].function if tool_calls else None
                if not func:
                    continue
                part = func.arguments or ""
                if part:
                    parts.append(part)
                    progress_cb("assistant", part)
        finally:
            close_method = getattr(stream, "close", None)
            if callable(close_method):
                close_method()
        return "".join(parts)

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        tools=tools,
        tool_choice=tool_choice,
    )
    return resp.choices[0].message.tool_calls[0].function.arguments


def recognize_policy_interactive(
    text: str,
    *,
    messages: List[dict] | None = None,
    progress_cb: Callable[[str, str], None] | None = None,
    cancel_cb: Callable[[], bool] | None = None,
) -> Tuple[dict, str, List[dict]]:
    """Распознать полис и вернуть JSON, транскрипт и сообщения.

    Если передан параметр ``messages``, диалог продолжается с них.
    """
    def _check_cancel() -> None:
        if cancel_cb and cancel_cb():
            logger.info("Распознавание полиса отменено пользователем")
            raise InterruptedError("Распознавание полиса отменено")

    if messages is None:
        messages = [
            {"role": "system", "content": _get_prompt()},
            {"role": "user", "content": text[:16000]},
        ]
    _check_cancel()
    if progress_cb:
        for m in messages:
            _check_cancel()
            progress_cb(m["role"], m["content"])

    for attempt in range(MAX_ATTEMPTS):
        _check_cancel()
        answer = _chat(messages, progress_cb, cancel_cb=cancel_cb)
        messages.append({"role": "assistant", "content": answer})
        try:
            data = json.loads(answer)
            validate(instance=data, schema=POLICY_SCHEMA)
        except json.JSONDecodeError as exc:
            if attempt == MAX_ATTEMPTS - 1:
                transcript = _log_conversation("text", messages)
                raise AiPolicyError(
                    f"Не удалось разобрать JSON: {exc}", messages, transcript
                ) from exc
            if progress_cb:
                _check_cancel()
                progress_cb("user", REMINDER)
            messages.append({"role": "user", "content": REMINDER})
            continue
        except ValidationError as exc:
            logger.warning("Ошибка валидации схемы в %s: %s", list(exc.path), exc.message)
            if attempt == MAX_ATTEMPTS - 1:
                transcript = _log_conversation("text", messages)
                raise AiPolicyError(
                    f"Ошибка валидации схемы: {exc.message}", messages, transcript
                ) from exc
            if progress_cb:
                _check_cancel()
                progress_cb("user", REMINDER)
            messages.append({"role": "user", "content": REMINDER})
            continue
        _check_cancel()
        transcript = _log_conversation("text", messages)
        return data, transcript, messages


def process_policy_files_with_ai(paths: List[str]) -> Tuple[List[dict], List[str]]:
    """Отправить файлы полисов в OpenAI и вернуть распарсенные данные JSON и транскрипты."""
    if not paths:
        return [], []

    results: List[dict] = []
    conversations: List[str] = []
    for path in paths:
        text = _read_text(path)
        try:
            data, transcript, _ = recognize_policy_interactive(text)
        except AiPolicyError as exc:
            raise ValueError(
                f"Не удалось разобрать JSON для {path}: {exc}\nДиалог:\n{exc.transcript}"
            ) from exc
        results.append(data)
        conversations.append(transcript)
    return results, conversations


def process_policy_bundle_with_ai(paths: List[str]) -> Tuple[dict, str]:
    """Отправить несколько файлов как один полис в OpenAI.

    Содержимое всех файлов объединяется и обрабатывается как один полис.
    """
    if not paths:
        return {}, ""

    text = "\n".join(_read_text(p) for p in paths)
    return process_policy_text_with_ai(text)


def process_policy_text_with_ai(text: str) -> Tuple[dict, str]:
    """Отправить текст полиса в OpenAI и вернуть распарсенные данные JSON и транскрипт."""
    if not text:
        return {}, ""

    try:
        data, transcript, _ = recognize_policy_interactive(text)
    except AiPolicyError as exc:
        raise ValueError(
            f"Не удалось разобрать JSON: {exc}\nДиалог:\n{exc.transcript}"
        ) from exc
    return data, transcript

