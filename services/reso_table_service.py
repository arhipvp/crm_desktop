"""Utilities to load payout tables from the RESO insurance company."""

from __future__ import annotations

import os
import pandas as pd

from ui.forms.policy_form import PolicyForm
from ui.forms.income_form import IncomeForm
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


def import_reso_payouts(
    path: str | os.PathLike,
    *,
    parent=None,
    policy_form_cls: type[PolicyForm] = PolicyForm,
    income_form_cls: type[IncomeForm] = IncomeForm,
) -> int:
    """Sequentially import policies and incomes from a RESO table.

    For each unique policy number the user is shown a ``PolicyForm`` and then an
    ``IncomeForm`` with the amount from the ``arhvp`` column. Returns the number
    of processed policies.
    """

    df = load_reso_table(path)
    seen: set[str] = set()
    processed = 0

    for _, row in df.iterrows():
        number = str(row.get("НОМЕР ПОЛИСА", "")).strip()
        if not number or number in seen:
            continue
        seen.add(number)

        pol_form = policy_form_cls(parent=parent)
        if "policy_number" in pol_form.fields:
            pol_form.fields["policy_number"].setText(number)
        if not pol_form.exec():
            continue

        policy = getattr(pol_form, "saved_instance", None)
        if not policy:
            continue

        amount = row.get("arhvp")
        inc_form = income_form_cls(parent=parent, deal_id=getattr(policy, "deal_id", None))
        pay = (
            policy.payments.order_by(Payment.id).first()
            if hasattr(policy, "payments")
            else None
        )
        if pay:
            inc_form.prefill_payment(pay.id)
        if "amount" in inc_form.fields and amount not in (None, ""):
            inc_form.fields["amount"].setText(str(amount))
        inc_form.exec()
        processed += 1

    return processed
