from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.forms.policy_form import PolicyForm


class PolicyPreviewDialog(QDialog):
    """Окно сверки данных полиса при импорте RESO."""

    def __init__(
        self,
        data: dict,
        *,
        existing_policy=None,
        policy_form_cls: type[PolicyForm] = PolicyForm,
        policy_number: str | None = None,
        start_date=None,
        end_date=None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Предпросмотр полиса")
        self.saved_instance = None
        self.use_existing = False

        layout = QVBoxLayout(self)
        content = QHBoxLayout()
        layout.addLayout(content)

        # -------- левая часть: форма создания полиса --------
        self.form = policy_form_cls(parent=self)
        # убираем внутренние кнопки формы
        if hasattr(self.form, "save_btn"):
            self.form.save_btn.hide()
        if hasattr(self.form, "cancel_btn"):
            self.form.cancel_btn.hide()

        if policy_number and "policy_number" in self.form.fields:
            self.form.fields["policy_number"].setText(policy_number)
        if start_date and "start_date" in self.form.fields:
            self.form.fields["start_date"].setDate(start_date)
        if end_date and "end_date" in self.form.fields:
            self.form.fields["end_date"].setDate(end_date)
        content.addWidget(self.form)

        # -------- правая часть: найденный полис --------
        right = QVBoxLayout()
        if existing_policy is not None:
            lbl = QLabel("Найденный полис:")
            right.addWidget(lbl)
            table = QTableWidget(0, 2)
            table.setHorizontalHeaderLabels(["Поле", "Значение"])
            fields = {
                "Номер": existing_policy.policy_number,
                "Клиент": getattr(existing_policy.client, "name", ""),
                "Начало": getattr(existing_policy, "start_date", ""),
                "Окончание": getattr(existing_policy, "end_date", ""),
                "Компания": getattr(existing_policy, "insurance_company", ""),
                "Тип": getattr(existing_policy, "insurance_type", ""),
            }
            for row, (k, v) in enumerate(fields.items()):
                table.insertRow(row)
                table.setItem(row, 0, QTableWidgetItem(str(k)))
                table.setItem(row, 1, QTableWidgetItem("" if v is None else str(v)))
            table.resizeColumnsToContents()
            right.addWidget(table)
            use_btn = QPushButton("Использовать найденный", self)
            use_btn.clicked.connect(self._use_existing)
            right.addWidget(use_btn)
        else:
            right.addWidget(QLabel("Полис не найден."))
        content.addLayout(right)

        # -------- кнопки диалога --------
        btns = QHBoxLayout()
        create_btn = QPushButton("Создать полис", self)
        create_btn.clicked.connect(self._create_policy)
        cancel_btn = QPushButton("Отмена", self)
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(create_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

        self.form.accepted.connect(self._on_form_accepted)
        self.form.rejected.connect(self.reject)

    # ------------------------------------------------------------------
    def _create_policy(self):
        self.form.save()

    def _use_existing(self):
        self.use_existing = True
        self.accept()

    def _on_form_accepted(self):
        self.saved_instance = getattr(self.form, "saved_instance", None)
        if self.saved_instance:
            self.accept()
