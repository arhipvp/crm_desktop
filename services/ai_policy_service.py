import json
import logging
import os
from typing import List, Tuple, Callable

import openai
from PyPDF2 import PdfReader

logger = logging.getLogger(__name__)

try:
    from jsonschema import ValidationError, validate
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    ValidationError = Exception

    def validate(instance, schema):  # type: ignore[unused-argument]
        """Fallback validate if jsonschema is missing."""
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
    """Return system prompt for policy recognition."""
    return os.getenv("AI_POLICY_PROMPT", DEFAULT_PROMPT)


def _log_conversation(path: str, messages: List[dict]) -> str:
    """Log conversation with OpenAI for debugging and return transcript."""
    transcript = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
    logger.info("OpenAI conversation for %s:\n%s", path, transcript)
    return transcript

# Number of attempts to get a valid JSON response from the model
MAX_ATTEMPTS = 3

# Additional instruction sent to the model when JSON parsing fails
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
    """Extract text from a PDF or text file."""
    if path.lower().endswith(".pdf"):
        try:
            reader = PdfReader(path)
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
            if text:
                return text
        except Exception as e:
            logger.warning("Failed to read PDF %s: %s", path, e)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", "ignore")


class AiPolicyError(ValueError):
    """Raised when the model fails to produce valid JSON."""

    def __init__(self, message: str, messages: List[dict], transcript: str):
        super().__init__(message)
        self.messages = messages
        self.transcript = transcript


def _chat(messages: List[dict], progress_cb: Callable[[str, str], None] | None = None) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")
    base_url = os.getenv("OPENAI_BASE_URL")
    model = os.getenv("OPENAI_MODEL", "gpt-4o")
    client = openai.OpenAI(api_key=api_key, base_url=base_url)

    if progress_cb:
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0,
            stream=True,
            functions=[POLICY_FUNCTION],
            function_call={"name": POLICY_FUNCTION["name"]},
        )
        parts: List[str] = []
        for chunk in stream:
            delta = chunk.choices[0].delta
            func = delta.get("function_call") if delta else None
            part = func.get("arguments") if func else ""
            if part:
                parts.append(part)
                progress_cb("assistant", part)
        return "".join(parts)

    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0,
        functions=[POLICY_FUNCTION],
        function_call={"name": POLICY_FUNCTION["name"]},
    )
    return resp.choices[0].message.function_call.arguments


def recognize_policy_interactive(
    text: str,
    *,
    messages: List[dict] | None = None,
    progress_cb: Callable[[str, str], None] | None = None,
) -> Tuple[dict, str, List[dict]]:
    """Recognize policy and return JSON, transcript and messages.

    If ``messages`` передан, диалог продолжается с них.
    """
    if messages is None:
        messages = [
            {"role": "system", "content": _get_prompt()},
            {"role": "user", "content": text[:16000]},
        ]
    if progress_cb:
        for m in messages:
            progress_cb(m["role"], m["content"])

    for attempt in range(MAX_ATTEMPTS):
        answer = _chat(messages, progress_cb)
        messages.append({"role": "assistant", "content": answer})
        try:
            data = json.loads(answer)
            validate(instance=data, schema=POLICY_SCHEMA)
        except json.JSONDecodeError as exc:
            if attempt == MAX_ATTEMPTS - 1:
                transcript = _log_conversation("text", messages)
                raise AiPolicyError(
                    f"Failed to parse JSON: {exc}", messages, transcript
                ) from exc
            if progress_cb:
                progress_cb("user", REMINDER)
            messages.append({"role": "user", "content": REMINDER})
            continue
        except ValidationError as exc:
            logger.warning("Schema validation error at %s: %s", list(exc.path), exc.message)
            if attempt == MAX_ATTEMPTS - 1:
                transcript = _log_conversation("text", messages)
                raise AiPolicyError(
                    f"Schema validation error: {exc.message}", messages, transcript
                ) from exc
            if progress_cb:
                progress_cb("user", REMINDER)
            messages.append({"role": "user", "content": REMINDER})
            continue
        transcript = _log_conversation("text", messages)
        return data, transcript, messages


def process_policy_files_with_ai(paths: List[str]) -> Tuple[List[dict], List[str]]:
    """Send policy files to OpenAI and return parsed JSON data and transcripts."""
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
                f"Failed to parse JSON for {path}: {exc}\nConversation:\n{exc.transcript}"
            ) from exc
        results.append(data)
        conversations.append(transcript)
    return results, conversations


def process_policy_bundle_with_ai(paths: List[str]) -> Tuple[dict, str]:
    """Send multiple files as a single policy to OpenAI.

    The contents of all files are concatenated and processed as one policy.
    """
    if not paths:
        return {}, ""

    text = "\n".join(_read_text(p) for p in paths)
    return process_policy_text_with_ai(text)


def process_policy_text_with_ai(text: str) -> Tuple[dict, str]:
    """Send raw text of a policy to OpenAI and return parsed JSON data and transcript."""
    if not text:
        return {}, ""

    try:
        data, transcript, _ = recognize_policy_interactive(text)
    except AiPolicyError as exc:
        raise ValueError(f"Failed to parse JSON: {exc}\nConversation:\n{exc.transcript}") from exc
    return data, transcript

