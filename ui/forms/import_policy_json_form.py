# ui/forms/import_policy_json_form.py

import json
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout,
    QMessageBox, QInputDialog
)

from services.client_service import get_all_clients, add_client
from ui.forms.policy_form import PolicyForm


class ImportPolicyJsonForm(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Импорт полиса из JSON")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlaceholderText(
            '{\n  "client_name": "Иванов Иван",\n  "policy": { ... },\n  "payments": [ ... ]\n}'
        )
        layout.addWidget(self.text_edit)

        # Кнопки внизу
        btn_layout = QHBoxLayout()
        btn_import = QPushButton("Импортировать", self)
        btn_import.clicked.connect(self.on_import_clicked)
        btn_cancel = QPushButton("Отмена", self)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_import)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

    def on_import_clicked(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Вставьте JSON с данными полиса.")
            return

        try:
            data = json.loads(text)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка JSON", f"Ошибка разбора JSON:\n{e}")
            return

        # Проверка ключей
        if not isinstance(data, dict) or "client_name" not in data or "policy" not in data or "payments" not in data:
            QMessageBox.warning(self, "Ошибка", "JSON должен содержать ключи: client_name, policy, payments")
            return

        client_name = data["client_name"].strip()
        if not client_name:
            QMessageBox.warning(self, "Ошибка", "client_name не должен быть пустым.")
            return

        # Поиск клиента
        matches = [
            c for c in get_all_clients()
            if client_name.lower() in c.name.lower()
        ]

        if not matches:
            resp = QMessageBox.question(
                self, "Клиент не найден",
                f"Клиент «{client_name}» не найден. Создать нового?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if resp != QMessageBox.Yes:
                return
            client = add_client(name=client_name)
        elif len(matches) == 1:
            client = matches[0]
        else:
            names = [c.name for c in matches]
            selected_name, ok = QInputDialog.getItem(
                self, "Выбор клиента",
                f"Найдено несколько клиентов по имени «{client_name}». Выберите нужного:",
                names, editable=False
            )
            if not ok:
                return
            client = next(c for c in matches if c.name == selected_name)

        # Подготовка и запуск формы
        policy_data = data.get("policy", {})
        payments_data = data.get("payments", [])

        form = PolicyForm(
            forced_client=client,
            parent=self
        )

        # Заполняем поля из policy
        for key, val in policy_data.items():
            if key in form.fields:
                widget = form.fields[key]
                if hasattr(widget, "setText"):
                    widget.setText(str(val))
                elif hasattr(widget, "setCurrentText"):
                    widget.setCurrentText(str(val))
                elif hasattr(widget, "setDate") and isinstance(val, str):
                    from datetime import datetime
                    try:
                        dt = datetime.strptime(val, "%Y-%m-%d").date()
                        widget.setDate(dt)
                    except ValueError:
                        pass  # игнорируем ошибки даты

        # Заполняем черновые платежи
        form._draft_payments = payments_data
        for pay in payments_data:
            if isinstance(pay.get("payment_date"), str):
                try:
                    pay["payment_date"] = datetime.strptime(pay["payment_date"], "%Y-%m-%d").date()
                except Exception:
                    pass
            if isinstance(pay.get("actual_payment_date"), str):
                try:
                    pay["actual_payment_date"] = datetime.strptime(pay["actual_payment_date"], "%Y-%m-%d").date()
                except Exception:
                    pass
            form.add_payment_row(pay)

        form.exec()
        self.accept()
