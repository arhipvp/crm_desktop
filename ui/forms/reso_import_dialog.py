from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHBoxLayout,
)
from database.models import Policy
from services.reso_table_service import load_reso_table, import_reso_payouts


class ResoImportDialog(QDialog):
    """Предварительный просмотр импорта выплат RESO."""

    def __init__(self, path: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Импорт выплат RESO")
        self.resize(800, 500)
        self.path = path

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Ниже показаны найденные записи. После проверки нажмите 'Импортировать'."
            )
        )

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            [
                "Полис",
                "Период",
                "Сумма",
                "Действие",
            ]
        )
        layout.addWidget(self.table)

        self._populate()

        btns = QHBoxLayout()
        self.import_btn = QPushButton("Импортировать")
        self.import_btn.clicked.connect(self._do_import)
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(cancel_btn)
        btns.addWidget(self.import_btn)
        layout.addLayout(btns)

        self.processed = 0

    # ------------------------------------------------------------------
    def _populate(self):
        df = load_reso_table(self.path)
        policy_col = "НОМЕР ПОЛИСА"
        period_col = "НАЧИСЛЕНИЕ,С-ПО"
        amount_col = "arhvp"
        policies = [str(n).strip() for n in df[policy_col].dropna().unique()]
        for num in policies:
            rows = df[df[policy_col].astype(str).str.strip() == num]
            amount = (
                rows[amount_col]
                .map(
                    lambda v: float(str(v).replace(" ", "").replace(",", "."))
                    if v not in (None, "")
                    else 0.0
                )
                .sum()
            )
            period = rows.iloc[0].get(period_col, "")
            exists = Policy.get_or_none(Policy.policy_number == num)
            action = "Обновить" if exists else "Создать"
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(num))
            self.table.setItem(row, 1, QTableWidgetItem(str(period)))
            self.table.setItem(row, 2, QTableWidgetItem(str(amount)))
            self.table.setItem(row, 3, QTableWidgetItem(action))
        self.table.resizeColumnsToContents()

    def _do_import(self):
        self.processed = import_reso_payouts(self.path, parent=self)
        self.accept()
