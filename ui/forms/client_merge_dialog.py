from __future__ import annotations

import base64
from typing import Any, Sequence

from PySide6.QtCore import Qt, QSignalBlocker, QByteArray
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ui.common.message_boxes import show_error
from ui import settings as ui_settings


class ClientMergeDialog(QDialog):
    """Диалог объединения клиентов с выбором основного и итоговых значений."""

    SETTINGS_KEY = "client_merge_dialog"

    _FIELDS: tuple[tuple[str, str], ...] = (
        ("name", "Имя"),
        ("phone", "Телефон"),
        ("email", "Email"),
        ("is_company", "Статус компании"),
    )

    def __init__(self, clients: Sequence[Any], parent=None) -> None:
        super().__init__(parent)
        self._clients = list(clients or [])
        if len(self._clients) < 2:
            raise ValueError("Для объединения требуется минимум два клиента")

        self.setWindowTitle("Объединение клиентов")
        self.setMinimumSize(640, 480)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                "Выберите основного клиента и скорректируйте итоговые значения.\n"
                "Подсвечены поля, отличающиеся от выбранного основного клиента."
            )
        )

        self.primary_combo = QComboBox()
        for client in self._clients:
            client_id = self._get_client_id(client)
            self.primary_combo.addItem(self._describe_client(client), client_id)
        self.primary_combo.currentIndexChanged.connect(self._on_primary_changed)
        layout.addWidget(self.primary_combo)

        self.comparison_table = QTableWidget(len(self._FIELDS), len(self._clients) + 1)
        headers = ["Поле"] + [self._describe_client(c) for c in self._clients]
        self.comparison_table.setHorizontalHeaderLabels(headers)
        self._column_to_client_id: dict[int, Any] = {}

        for row, (field, title) in enumerate(self._FIELDS):
            key_item = QTableWidgetItem(title)
            key_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
            self.comparison_table.setItem(row, 0, key_item)
            for col, client in enumerate(self._clients, start=1):
                value_item = QTableWidgetItem(self._format_value(field, client))
                value_item.setFlags(Qt.ItemIsSelectable | Qt.ItemIsEnabled)
                self.comparison_table.setItem(row, col, value_item)
                self._column_to_client_id[col] = self._get_client_id(client)

        self.comparison_table.resizeColumnsToContents()
        layout.addWidget(self.comparison_table)

        self.final_group = QGroupBox("Итоговые значения")
        form_layout = QFormLayout(self.final_group)
        self.name_edit = QLineEdit()
        self.phone_edit = QLineEdit()
        self.email_edit = QLineEdit()
        self.is_company_checkbox = QCheckBox("Компания")
        self.note_edit = QPlainTextEdit()
        self.active_checkbox = QCheckBox("Активный клиент")

        form_layout.addRow("Имя", self.name_edit)
        form_layout.addRow("Телефон", self.phone_edit)
        form_layout.addRow("Email", self.email_edit)
        form_layout.addRow("Статус", self.is_company_checkbox)
        form_layout.addRow("Заметки", self.note_edit)
        form_layout.addRow("Активность", self.active_checkbox)
        layout.addWidget(self.final_group)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self._baseline_values: dict[str, Any] = {}
        self._connect_highlight_handlers()
        self._on_primary_changed()

        geometry_b64 = ui_settings.get_window_settings(self.SETTINGS_KEY).get("geometry")
        if geometry_b64:
            try:
                geometry_bytes = base64.b64decode(geometry_b64)
                self.restoreGeometry(QByteArray(geometry_bytes))
            except Exception:  # pragma: no cover - восстановление необязательно
                pass

    # ------------------------------------------------------------------
    # Публичные геттеры
    # ------------------------------------------------------------------

    def get_primary_client_id(self) -> Any:
        idx = self.primary_combo.currentIndex()
        if idx < 0:
            return None
        return self.primary_combo.currentData()

    def get_duplicate_client_ids(self) -> list[Any]:
        primary_id = self.get_primary_client_id()
        ids: list[Any] = []
        for client in self._clients:
            client_id = self._get_client_id(client)
            if client_id is not None and client_id != primary_id:
                ids.append(client_id)
        return ids

    def get_final_values(self) -> dict[str, Any]:
        name = self.name_edit.text().strip()
        phone = self.phone_edit.text().strip()
        email = self.email_edit.text().strip()
        note = self.note_edit.toPlainText().strip()
        return {
            "name": name,
            "phone": phone or None,
            "email": email or None,
            "is_company": self.is_company_checkbox.isChecked(),
            "note": note or None,
            "is_active": self.active_checkbox.isChecked(),
        }

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def accept(self) -> None:  # type: ignore[override]
        if len(self._clients) < 2:
            show_error("Для объединения выберите минимум двух клиентов")
            return

        primary_id = self.get_primary_client_id()
        if primary_id is None:
            show_error("Выберите основного клиента")
            return

        final_values = self.get_final_values()
        if not final_values["name"]:
            show_error("Имя клиента обязательно")
            return

        self._save_geometry()
        super().accept()

    def reject(self) -> None:  # type: ignore[override]
        self._save_geometry()
        super().reject()

    def closeEvent(self, event):  # type: ignore[override]
        self._save_geometry()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Внутренняя логика
    # ------------------------------------------------------------------

    def _connect_highlight_handlers(self) -> None:
        self.name_edit.textChanged.connect(lambda: self._highlight_final_field("name"))
        self.phone_edit.textChanged.connect(lambda: self._highlight_final_field("phone"))
        self.email_edit.textChanged.connect(lambda: self._highlight_final_field("email"))
        self.is_company_checkbox.toggled.connect(
            lambda _: self._highlight_final_field("is_company")
        )
        self.note_edit.textChanged.connect(
            lambda: self._highlight_final_field("note")
        )
        self.active_checkbox.toggled.connect(
            lambda _: self._highlight_final_field("is_active")
        )

    def _on_primary_changed(self) -> None:
        primary_id = self.get_primary_client_id()
        client = next(
            (c for c in self._clients if self._get_client_id(c) == primary_id),
            None,
        )
        self._populate_final_fields(client)
        self._update_comparison_highlight(primary_id)

    def _populate_final_fields(self, client: Any | None) -> None:
        baseline = {
            "name": self._get_attribute(client, "name"),
            "phone": self._get_attribute(client, "phone"),
            "email": self._get_attribute(client, "email"),
            "is_company": bool(self._get_attribute(client, "is_company")),
            "note": self._get_attribute(client, "note"),
            "is_active": self._is_client_active(client),
        }
        self._baseline_values = baseline

        with QSignalBlocker(self.name_edit):
            self.name_edit.setText(baseline.get("name") or "")
        with QSignalBlocker(self.phone_edit):
            self.phone_edit.setText(baseline.get("phone") or "")
        with QSignalBlocker(self.email_edit):
            self.email_edit.setText(baseline.get("email") or "")
        with QSignalBlocker(self.is_company_checkbox):
            self.is_company_checkbox.setChecked(bool(baseline.get("is_company")))
        with QSignalBlocker(self.note_edit):
            self.note_edit.setPlainText(baseline.get("note") or "")
        with QSignalBlocker(self.active_checkbox):
            self.active_checkbox.setChecked(bool(baseline.get("is_active")))

        self._refresh_final_highlights()

    def _refresh_final_highlights(self) -> None:
        for field in ("name", "phone", "email", "is_company", "note", "is_active"):
            self._highlight_final_field(field)

    def _highlight_final_field(self, field: str) -> None:
        baseline = self._baseline_values.get(field)
        current = self._current_value(field)
        changed = self._values_differ(baseline, current)
        widget = self._widget_for_field(field)
        if widget is None:
            return
        widget.setStyleSheet("background:#fff0b3;" if changed else "")

    def _widget_for_field(self, field: str):
        return {
            "name": self.name_edit,
            "phone": self.phone_edit,
            "email": self.email_edit,
            "is_company": self.is_company_checkbox,
            "note": self.note_edit,
            "is_active": self.active_checkbox,
        }.get(field)

    def _current_value(self, field: str) -> Any:
        if field == "name":
            return self.name_edit.text().strip()
        if field == "phone":
            return self.phone_edit.text().strip()
        if field == "email":
            return self.email_edit.text().strip()
        if field == "is_company":
            return self.is_company_checkbox.isChecked()
        if field == "note":
            return self.note_edit.toPlainText().strip()
        if field == "is_active":
            return self.active_checkbox.isChecked()
        return None

    def _values_differ(self, left: Any, right: Any) -> bool:
        if isinstance(left, str):
            left = left.strip()
        if isinstance(right, str):
            right = right.strip()
        return str(left) != str(right)

    def _update_comparison_highlight(self, primary_id: Any | None) -> None:
        primary_column = next(
            (col for col, cid in self._column_to_client_id.items() if cid == primary_id),
            None,
        )
        if primary_column is None:
            return

        highlight_color = QColor("#fff0b3")
        for row in range(self.comparison_table.rowCount()):
            primary_item = self.comparison_table.item(row, primary_column)
            row_changed = False
            for col in range(1, self.comparison_table.columnCount()):
                item = self.comparison_table.item(row, col)
                if item is None:
                    continue
                if col == primary_column:
                    item.setBackground(Qt.white)
                else:
                    changed = (
                        primary_item is not None
                        and item.text() != primary_item.text()
                    )
                    item.setBackground(highlight_color if changed else Qt.white)
                    row_changed = row_changed or changed
            key_item = self.comparison_table.item(row, 0)
            if key_item is not None:
                key_item.setBackground(highlight_color if row_changed else Qt.white)

    def _format_value(self, field: str, client: Any) -> str:
        value = self._get_attribute(client, field)
        if field == "is_company":
            return "Да" if bool(value) else "Нет"
        if value in (None, ""):
            return ""
        return str(value)

    def _describe_client(self, client: Any) -> str:
        name = self._get_attribute(client, "name") or "Без имени"
        client_id = self._get_client_id(client)
        if client_id is None:
            return str(name)
        return f"{name} (ID: {client_id})"

    def _get_client_id(self, client: Any) -> Any:
        if client is None:
            return None
        if isinstance(client, dict):
            return client.get("id")
        return getattr(client, "id", None)

    def _get_attribute(self, client: Any | None, attr: str) -> Any:
        if client is None:
            return None
        if isinstance(client, dict):
            return client.get(attr)
        return getattr(client, attr, None)

    def _is_client_active(self, client: Any | None) -> bool:
        if client is None:
            return True
        is_deleted = self._get_attribute(client, "is_deleted")
        if is_deleted is None:
            return True
        return not bool(is_deleted)

    def _save_geometry(self) -> None:
        try:
            geometry = self.saveGeometry()
            geometry_b64 = base64.b64encode(bytes(geometry)).decode("ascii")
            ui_settings.set_window_settings(
                self.SETTINGS_KEY,
                {"geometry": geometry_b64},
            )
        except Exception:  # pragma: no cover - сохранение необязательно
            pass

