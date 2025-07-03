import json
import logging
import os
from typing import List

import openai
from PyPDF2 import PdfReader

PROMPT = """Ты — ассистент, отвечающий за импорт данных из страховых полисов в CRM. На основе загруженного документа (PDF, скан или текст) необходимо сформировать один JSON строго по следующему шаблону:
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

logger = logging.getLogger(__name__)


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


def process_policy_files_with_ai(paths: List[str]) -> List[dict]:
    """Send policy files to OpenAI and return parsed JSON data."""
    if not paths:
        return []

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set")

    base_url = os.getenv("OPENAI_BASE_URL")
    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    results: List[dict] = []
    for path in paths:
        text = _read_text(path)
        messages = [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": text[:16000]},
        ]
        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0,
            )
        except Exception as e:
            raise RuntimeError(f"OpenAI request failed for {path}: {e}") from e

        answer = resp.choices[0].message.content
        try:
            data = json.loads(answer)
        except Exception:
            try:
                start = answer.index("{")
                end = answer.rindex("}") + 1
                data = json.loads(answer[start:end])
            except Exception as e:
                raise ValueError(f"Failed to parse JSON for {path}: {e}") from e
        results.append(data)
    return results
