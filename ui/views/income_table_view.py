from peewee import prefetch
from PySide6.QtCore import Qt

from database.models import Client, Income, Payment, Policy, Deal
from services.income_service import build_income_query, mark_income_deleted
from ui.base.base_table_model import BaseTableModel
from ui.base.base_table_view import BaseTableView
from ui.common.message_boxes import confirm, show_error
from ui.forms.income_form import IncomeForm


class IncomeTableModel(BaseTableModel):
    VIRTUAL_FIELDS = [
        "payment_info",
        "deal_desc",
        "client_name",
        "contractor",
        "amount",
        "received",
    ]

    def __init__(self, objects, model_class, parent=None):
        super().__init__(objects, model_class, parent)
        self.fields = []  # отключаем стандартные поля модели

        self.virtual_fields = self.VIRTUAL_FIELDS
        self.headers = [
            "Полис",          # 0
            "Сделка",         # 1
            "Клиент",         # 2
            "Дата начала",    # 3
            "Дата платежа",   # 4
            "Сумма платежа",  # 5
            "Сумма комиссии", # 6
            "Дата получения", # 7
        ]

    def columnCount(self, parent=None):
        return len(self.headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        obj = self.objects[index.row()]
        col = index.column()
        if role != Qt.DisplayRole:
            return None

        payment = getattr(obj, "payment", None)
        policy = getattr(payment, "policy", None) if payment else None
        deal = getattr(policy, "deal", None) if policy else None

        if col == 0:
            return policy.policy_number if policy else "—"
        elif col == 1:
            return deal.description if deal else "—"
        elif col == 2:
            return policy.client.name if policy and policy.client else "—"
        elif col == 3:
            return (
                policy.start_date.strftime("%d.%m.%Y")
                if policy and policy.start_date
                else "—"
            )
        elif col == 4:
            return (
                payment.payment_date.strftime("%d.%m.%Y")
                if payment and payment.payment_date
                else "—"
            )
        elif col == 5:
            return (
                f"{payment.amount:,.2f} ₽" if payment and payment.amount else "0 ₽"
            )
        elif col == 6:
            return f"{obj.amount:,.2f} ₽" if obj.amount else "0 ₽"
        elif col == 7:
            return (
                obj.received_date.strftime("%d.%m.%Y")
                if obj.received_date
                else "—"
            )

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole or orientation != Qt.Horizontal:
            return None
        if 0 <=
