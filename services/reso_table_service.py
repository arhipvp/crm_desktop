"""Utilities to load payout tables from the RESO insurance company."""

from __future__ import annotations

import os
from datetime import date, datetime
import logging
import pandas as pd

from PySide6.QtWidgets import QDialog, QInputDialog
from ui.forms.column_mapping_dialog import ColumnMappingDialog
from ui.forms.policy_form import PolicyForm
from ui.forms.income_form import IncomeForm
from ui.forms.income_update_dialog import IncomeUpdateDialog
from ui.forms.policy_preview_dialog import PolicyPreviewDialog
from ui.forms.client_form import ClientForm
from database.models import Payment
from services.validators import normalize_number

logger = logging.getLogger(__name__)


COLUMNS = [
    "АГЕНТСТВО",
    "АГЕНТ",
    "ДАТА ВЫПЛАТЫ",
    "ТИП НАЧИСЛЕНИЯ",
    "НОМЕР ПОЛИСА",
    "УЧ.№ АДДЕНДУМА",
    "СТРАХОВАТЕЛЬ",
    "НАЧИСЛЕНИЕ,С-ПО",
    "ПРЕМИЯ,РУБ.",
    "СУММА/ПРЕМИЯ,%",
    "СУММА,РУБ",
    "УСН",
    "ДАТА ПРОВОДКИ",
    "ПРИМЕЧАНИЕ",
    "НОМЕР БОРДЕРО",
    "ДАТА БОРДЕРО",
    "АГЕНТ-ПРОДАВЕЦ_ПОЛИСА",
    "ПРОДУКТ",
    "КРЕДИТНАЯ ОРГАНИЗАЦИЯ",
    "ВЛАДЕЛЕЦ ПОРТФЕЛЯ",
    "Источник",
    "Минус",
    "arhvp",
    "peraa",
    "nikrk",
    "ПКВ",
]


def load_reso_table(path: str | os.PathLike) -> pd.DataFrame:
    """Load a RESO payout table from *path* into a :class:`pandas.DataFrame`."""

    path_str = str(path)
    if path_str.lower().endswith((".xlsx", ".xls")):
        df = pd.read_excel(path_str, dtype=str)
    else:
        try:
            df = pd.read_csv(path_str, sep="\t", dtype=str, encoding="utf-8-sig")
        except Exception:
            df = pd.read_csv(path_str, sep=";", dtype=str, encoding="utf-8-sig")

    df.columns = [c.strip() for c in df.columns]
    return df


def _parse_date_range(text: str):
    """Return (start, end) dates from a ``ДД.ММ.ГГГГ -ДД.ММ.ГГГГ`` string."""
    if not text or "-" not in text:
        return None, None
    start_s, end_s = [t.strip() for t in text.split("-", 1)]
    for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            from datetime import datetime

            start = datetime.strptime(start_s, fmt).date()
            end = datetime.strptime(end_s, fmt).date()
            return start, end
        except Exception:
            continue
    return None, None


def _parse_amount(value) -> float:
    """Convert a payout amount cell to float."""
    if value in (None, ""):
        return 0.0
    try:
        return float(normalize_number(value))
    except Exception:
        return 0.0


def select_row_from_table(df: pd.DataFrame, parent=None) -> pd.Series | None:
    """Prompt the user to select a specific row from the RESO table."""
    if df.empty:
        return None
    items = [
        f"{i+1}. {r.get('НОМЕР ПОЛИСА', '')} {r.get('НАЧИСЛЕНИЕ,С-ПО', '')}"
        for i, r in df.iterrows()
    ]
    choice, ok = QInputDialog.getItem(
        parent,
        "Выберите запись",
        "Строка таблицы:",
        items,
        editable=False,
    )
    if not ok:
        return None
    idx = int(choice.split(".", 1)[0]) - 1
    if 0 <= idx < len(df):
        return df.iloc[idx]
    return None


def select_policy_from_table(
    df: pd.DataFrame, policy_col: str, parent=None
) -> pd.Series | None:
    """Prompt the user to choose a policy number and return the first matching row."""
    if df.empty or policy_col not in df.columns:
        return None
    numbers = [str(n).strip() for n in df[policy_col].dropna().unique()]
    if not numbers:
        return None
    choice, ok = QInputDialog.getItem(
        parent,
        "Выберите полис",
        "Номер полиса:",
        numbers,
        editable=False,
    )
    if not ok:
        return None
    match = df[df[policy_col].astype(str).str.strip() == choice]
    if not match.empty:
        return match.iloc[0]
    return None


def import_reso_payouts(
    path: str | os.PathLike,
    *,
    parent=None,
    column_map_cls: type[QDialog] = ColumnMappingDialog,
    preview_cls: type[QDialog] = PolicyPreviewDialog,
    policy_form_cls: type[PolicyForm] = PolicyForm,
    income_form_cls: type[IncomeForm] = IncomeForm,
    client_form_cls: type[ClientForm] = ClientForm,
) -> int:
    """Import RESO payout table sequentially.

    Each unique policy number in the table is processed one by one. For every
    policy the user can create a new policy, attach the payout to an existing
    one or skip it. Returns the number of successfully processed policies.
    """

    df = load_reso_table(path)
    file_date = date.fromtimestamp(os.path.getctime(path))

    mapping = {
        "policy_number": "НОМЕР ПОЛИСА",
        "period": "НАЧИСЛЕНИЕ,С-ПО",
        "amount": "arhvp",
        "premium": "ПРЕМИЯ,РУБ.",
        "insurance_type": "ПРОДУКТ",
        "sales_channel": "Источник",
    }
    if column_map_cls is not None:
        dlg = column_map_cls(list(df.columns), parent=parent)
        if not dlg.exec():
            return 0
        mapping = dlg.get_mapping()

    policy_col = mapping["policy_number"]
    premium_col = mapping.get("premium")
    type_col = mapping.get("insurance_type")
    channel_col = mapping.get("sales_channel")
    numbers = [str(n).strip() for n in df[policy_col].dropna().unique()]
    total = len(numbers)
    processed = 0

    for idx, number in enumerate(numbers, start=1):
        logger.info("🔄 %s/%s: обработка полиса %s", idx, total, number)
        selected_rows = df[df[policy_col].astype(str).str.strip() == number]
        if selected_rows.empty:
            continue
        row = selected_rows.iloc[0]
        forced_client = None
        if "СТРАХОВАТЕЛЬ" in df.columns:
            raw_client = str(row.get("СТРАХОВАТЕЛЬ", "")).strip()
            if raw_client:
                import re
                from services.client_service import find_similar_clients

                m = re.match(r"(.*?)\s*\[\d+\]$", raw_client)
                name = m.group(1) if m else raw_client
                matches = find_similar_clients(name)
                if len(matches) == 1:
                    forced_client = matches[0]
                else:
                    form = client_form_cls(parent=parent)
                    if "name" in getattr(form, "fields", {}):
                        widget = form.fields["name"]
                        if hasattr(widget, "setText"):
                            widget.setText(name)
                    if form.exec() == QDialog.Accepted:
                        forced_client = getattr(form, "saved_instance", None)
                        if not forced_client:
                            continue
                    else:
                        continue
        start_date, end_date = _parse_date_range(str(row.get(mapping["period"], "")))

        existing_policy = None
        if number:
            from database.models import Policy

            existing_policy = Policy.get_or_none(Policy.policy_number == number)

        progress = f"{idx}/{total}"
        preview = preview_cls(
            row.to_dict(),
            existing_policy=existing_policy,
            policy_form_cls=policy_form_cls,
            policy_number=number,
            start_date=start_date,
            end_date=end_date,
            parent=parent,
            progress=progress,
            forced_client=forced_client,
        )

        form = getattr(preview, "form", None)
        if form:
            if "insurance_company" in form.fields:
                widget = form.fields["insurance_company"]
                if hasattr(widget, "setCurrentText"):
                    widget.setCurrentText("Ресо")
            if "insurance_type" in form.fields and type_col in df.columns:
                ins_type = str(row.get(type_col, "")).strip()
                if ins_type and hasattr(form.fields["insurance_type"], "setCurrentText"):
                    form.fields["insurance_type"].setCurrentText(ins_type)
            if "sales_channel" in form.fields and channel_col in df.columns:
                channel = str(row.get(channel_col, "")).strip()
                if channel and hasattr(form.fields["sales_channel"], "setCurrentText"):
                    form.fields["sales_channel"].setCurrentText(channel)
            if premium_col in df.columns:
                prem = _parse_amount(row.get(premium_col))
                if prem:
                    pay_date = start_date or file_date
                    pay_data = {"payment_date": pay_date, "amount": prem}
                    form._draft_payments = [pay_data]
                    if hasattr(form, "add_payment_row"):
                        form.add_payment_row(pay_data)

        if not preview.exec():
            break
        if getattr(preview, "skipped", False):
            continue

        if preview.use_existing:
            policy = existing_policy
        else:
            policy = preview.saved_instance or existing_policy
        if not policy:
            continue

        amount = selected_rows[mapping["amount"]].map(_parse_amount).sum()

        pay = (
            policy.payments.order_by(Payment.id).first()
            if hasattr(policy, "payments")
            else None
        )
        existing_income = None
        if pay:
            from database.models import Income

            existing_income = (
                Income.select()
                .where(
                    (Income.payment == pay.id) & (Income.received_date.is_null(True))
                )
                .order_by(Income.id)
                .first()
            )

        from PySide6.QtWidgets import QMessageBox

        use_existing = False
        if existing_income is not None:
            new_data = {"amount": amount}
            if file_date:
                new_data["received_date"] = file_date
            dlg = IncomeUpdateDialog(existing_income, new_data, parent=parent)
            if dlg.exec() != QDialog.Accepted:
                continue
            if dlg.choice == "update":
                use_existing = True
        else:
            pay_info = ""
            if pay is not None:
                pdate = getattr(pay, "payment_date", None)
                pdate_s = pdate.strftime("%d.%m.%Y") if pdate else "—"
                pay_info = f" по платежу #{pay.id} от {pdate_s}"
            answer = QMessageBox.question(
                parent,
                "Добавить доход",
                f"Добавить доход{pay_info} на сумму {amount:.2f} ₽?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                continue

        if use_existing:
            inc_form = income_form_cls(instance=existing_income, parent=parent)
        else:
            inc_form = income_form_cls(
                parent=parent, deal_id=getattr(policy, "deal_id", None)
            )
            if pay:
                inc_form.prefill_payment(pay.id)

        if "amount" in inc_form.fields and amount not in (None, ""):
            inc_form.fields["amount"].setText(str(amount))
        if "received_date" in inc_form.fields:
            from ui.common.date_utils import to_qdate

            inc_form.fields["received_date"].setDate(to_qdate(file_date))
        inc_form.exec()
        processed += 1

    return processed
