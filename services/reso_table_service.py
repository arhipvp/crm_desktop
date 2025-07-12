"""Utilities to load payout tables from the RESO insurance company."""

from __future__ import annotations

import os
import pandas as pd

from PySide6.QtWidgets import QDialog, QInputDialog
from ui.forms.policy_form import PolicyForm
from ui.forms.income_form import IncomeForm
from ui.forms.policy_preview_dialog import PolicyPreviewDialog
from database.models import Payment


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


def import_reso_payouts(
    path: str | os.PathLike,
    *,
    parent=None,
    select_row_func=select_row_from_table,
    preview_cls: type[QDialog] = PolicyPreviewDialog,
    policy_form_cls: type[PolicyForm] = PolicyForm,
    income_form_cls: type[IncomeForm] = IncomeForm,
) -> int:
    """Import a single RESO payout entry interactively.

    The user chooses a row from the table, previews it and either attaches the
    income to an existing policy or creates a new one. Returns ``1`` if the
    operation was completed, otherwise ``0``.
    """

    df = load_reso_table(path)
    row = select_row_func(df, parent=parent)
    if row is None:
        return 0

    preview = preview_cls(row.to_dict(), parent=parent)
    if not preview.exec():
        return 0

    number = str(row.get("НОМЕР ПОЛИСА", "")).strip()
    start_date, end_date = _parse_date_range(str(row.get("НАЧИСЛЕНИЕ,С-ПО", "")))
    existing_policy = None
    if number and start_date and end_date:
        from database.models import Policy

        existing_policy = Policy.get_or_none(
            (Policy.policy_number == number)
            & (Policy.start_date == start_date)
            & (Policy.end_date == end_date)
        )

    if existing_policy is not None:
        policy = existing_policy
    else:
        pol_form = policy_form_cls(parent=parent)
        if "policy_number" in pol_form.fields:
            pol_form.fields["policy_number"].setText(number)
        if start_date and "start_date" in pol_form.fields:
            pol_form.fields["start_date"].setDate(start_date)
        if end_date and "end_date" in pol_form.fields:
            pol_form.fields["end_date"].setDate(end_date)
        if not pol_form.exec():
            return 0

        policy = getattr(pol_form, "saved_instance", None)
        if not policy:
            return 0

    amount = row.get("arhvp")

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
                (Income.payment == pay.id)
                & (Income.received_date.is_null(True))
            )
            .order_by(Income.id)
            .first()
        )

    if existing_income:
        inc_form = income_form_cls(instance=existing_income, parent=parent)
    else:
        inc_form = income_form_cls(
            parent=parent, deal_id=getattr(policy, "deal_id", None)
        )
        if pay:
            inc_form.prefill_payment(pay.id)

    if "amount" in inc_form.fields and amount not in (None, ""):
        inc_form.fields["amount"].setText(str(amount))
    inc_form.exec()
    return 1
