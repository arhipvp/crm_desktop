import datetime as dt
import os
import sys

from openpyxl import load_workbook

# Добавляем путь к корню проекта
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
sys.path.append(BASE_DIR)
from PySide6.QtWidgets import QApplication

# Теперь корректные импорты
from database.db import db
from database.models import Client, Policy
from services.client_service import get_or_create_client_by_name
from services.policy_service import add_policy
from services.task_service import add_task  # если нужно
from ui.common.client_import_dialog import ClientImportDialog

EXCEL_FILENAME = "policies_import.xlsx"


def parse_date(value) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    try:
        return dt.datetime.strptime(str(value), "%d.%m.%Y").date()
    except Exception:
        return None


def run_import():
    filepath = os.path.join(os.path.dirname(__file__), EXCEL_FILENAME)
    wb = load_workbook(filename=filepath)
    ws = wb.active

    headers = [cell.value for cell in ws[1]]
    rows = list(ws.iter_rows(min_row=2, values_only=True))

    success, skipped = 0, 0
    # Убедимся, что есть QApplication
    if not QApplication.instance():
        app = QApplication(sys.argv)

    with db.atomic():
        for row in rows:
            data = dict(zip(headers, row))
            client_name = str(data.get("ФИО клиента", "")).strip()
            policy_number = str(data.get("Номер полиса", "")).strip()
            start_date = parse_date(data.get("Дата начала"))
            end_date = parse_date(data.get("Дата окончания"))

            if not client_name or not policy_number or not start_date or not end_date:
                print(f"❌ Пропущено: не хватает обязательных данных → {data}")
                skipped += 1
                continue

            # Создаём или получаем клиента
            client, created = get_or_create_client_by_name(client_name)

            if created or not client.phone:
                dlg = ClientImportDialog(suggested_name=client.name, suggested_phone=client.phone)

                if dlg.exec():
                    client = dlg.client
                else:
                    print(f"⛔ Импорт прерван по пользователю для клиента: {client_name}")
                    skipped += 1
                    continue


            # Проверка на дубликат номера
            original_number = policy_number
            suffix = 1
            while Policy.get_or_none(Policy.policy_number == policy_number):
                policy_number = f"{original_number}-{suffix}"
                suffix += 1

            # Добавляем полис
            # Добавляем полис через словарь
            policy_data = {
                "policy_number": policy_number,
                "client_id": client.id,
                "start_date": start_date,
                "end_date": end_date,
                "insurance_type": data.get("Тип страхования"),
                "insurance_company": data.get("Компания"),
                "contractor": data.get("Контрагент"),
                "sales_channel": data.get("Канал продаж"),
                "vehicle_brand": data.get("Марка авто"),
                "vehicle_model": data.get("Модель авто"),
                "vehicle_vin": data.get("VIN"),
                "note": data.get("Комментарий"),
            }

            policy = add_policy(
                **policy_data,
                payments=[{
                    "amount": float(data.get("Сумма", 0)) or 0,
                    "payment_date": start_date
                }],
                first_payment_paid=True
            )



            print(f"✅ Добавлен полис: {policy.policy_number} (клиент: {client.name})")
            success += 1

    print(f"\n✅ Импорт завершён: {success} добавлено, {skipped} пропущено.")


if __name__ == "__main__":
    run_import()
