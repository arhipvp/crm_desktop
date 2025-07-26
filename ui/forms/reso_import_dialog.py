from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QHBoxLayout,
    QFileDialog,
    QLineEdit,
)
from database.models import Policy
from services.reso_table_service import load_reso_table, import_reso_payouts
from services.validators import normalize_number


class ResoImportDialog(QDialog):
    """Предварительный просмотр импорта выплат RESO."""

    def __init__(self, path: str | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Импорт выплат RESO")
        self.resize(800, 500)
        self.path = path or ""

        layout = QVBoxLayout(self)

        path_row = QHBoxLayout()
        self.path_edit = QLineEdit(self.path)
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self._choose_file)
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        layout.addWidget(
            QLabel(
                "Ниже показаны найденные записи. После проверки нажмите 'Импортировать'."
            )
        )

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(
            [
                "Полис",
                "Страхователь",
                "Период",
                "Премия",
                "Сумма",
                "Действие",
            ]
        )
        layout.addWidget(self.table)

        if self.path:
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
    def _choose_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Выберите таблицу RESO", "", "Excel/CSV (*.xlsx *.xls *.csv *.tsv)"
        )
        if file_path:
            self.path = file_path
            self.path_edit.setText(file_path)
            self._populate()

    # ------------------------------------------------------------------
    def _populate(self):
        self.table.setRowCount(0)
        if not self.path:
            return

        df = load_reso_table(self.path)
        policy_col = "НОМЕР ПОЛИСА"
        period_col = "НАЧИСЛЕНИЕ,С-ПО"
        amount_col = "arhvp"
        prem_col = "ПРЕМИЯ,РУБ."
        client_col = "СТРАХОВАТЕЛЬ"
        policies = [str(n).strip() for n in df[policy_col].dropna().unique()]
        for num in policies:
            rows = df[df[policy_col].astype(str).str.strip() == num]
            amount = (
                rows[amount_col]
                .map(
                    lambda v: float(normalize_number(v)) if v not in (None, "") else 0.0
                )
                .sum()
            )
            prem = (
                rows[prem_col]
                .map(
                    lambda v: float(normalize_number(v)) if v not in (None, "") else 0.0
                )
                .sum()
            ) if prem_col in df.columns else 0.0
            client = rows.iloc[0].get(client_col, "") if client_col in df.columns else ""
            period = rows.iloc[0].get(period_col, "")
            exists = Policy.get_or_none(Policy.policy_number == num)
            action = "Обновить" if exists else "Создать"
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(num))
            self.table.setItem(row, 1, QTableWidgetItem(client))
            self.table.setItem(row, 2, QTableWidgetItem(str(period)))
            self.table.setItem(row, 3, QTableWidgetItem(str(prem)))
            self.table.setItem(row, 4, QTableWidgetItem(str(amount)))
            self.table.setItem(row, 5, QTableWidgetItem(action))
        self.table.resizeColumnsToContents()

    def _do_import(self):
        if not self.path:
            return
        self.processed = import_reso_payouts(self.path, parent=self)
        self.accept()
