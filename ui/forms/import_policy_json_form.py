# ui/forms/import_policy_json_form.py

import base64
import json
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from PySide6.QtCore import QByteArray
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QInputDialog,
)

from services.clients import get_all_clients, add_client
from ui.forms.policy_form import PolicyForm
from ui import settings as ui_settings


def _parse_date(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return value


def prepare_policy_payload(
    text: str,
    *,
    forced_client: Optional[Any] = None,
    forced_deal: Optional[Any] = None,
) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]]]:
    """Parse JSON payload for policy import.

    Returns client name, policy dictionary and payments list with normalised dates.
    Raises :class:`ValueError` if payload structure is invalid and propagates
    :class:`json.JSONDecodeError` for malformed JSON.
    """

    text = text.strip()
    data = json.loads(text)

    if (
        not isinstance(data, dict)
        or "client_name" not in data
        or "policy" not in data
        or "payments" not in data
    ):
        raise ValueError(
            "JSON должен содержать ключи: client_name, policy, payments"
        )

    client_name = str(data["client_name"]).strip()
    if not client_name:
        raise ValueError("client_name не должен быть пустым")

    raw_policy = data.get("policy")
    if raw_policy is None:
        raw_policy = {}
    elif not isinstance(raw_policy, dict):
        raise ValueError("policy должен быть объектом")

    policy_data = dict(raw_policy)
    if forced_client is not None:
        policy_data.pop("client_id", None)
        policy_data.pop("client", None)

    if forced_deal is not None:
        policy_data.pop("deal_id", None)
        policy_data.pop("deal", None)

    raw_payments: Iterable[Any] = data.get("payments")
    if raw_payments is None:
        raw_payments = []
    elif not isinstance(raw_payments, list):
        raise ValueError("payments должен быть массивом")

    payments_data: List[Dict[str, Any]] = []
    for item in raw_payments:
        if not isinstance(item, dict):
            raise ValueError("каждый платеж должен быть объектом")
        normalised = dict(item)
        for key in ("payment_date", "actual_payment_date"):
            if key in normalised:
                normalised[key] = _parse_date(normalised[key])
        payments_data.append(normalised)

    return client_name, policy_data, payments_data


SETTINGS_KEY = "import_policy_json_form"


class ImportPolicyJsonForm(QDialog):
    def __init__(self, parent=None, *, forced_client=None, forced_deal=None, json_text=None):
        super().__init__(parent)
        self._forced_client = forced_client
        self._forced_deal = forced_deal
        self.imported_policy = None
        self.setWindowTitle("Импорт полиса из JSON")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlaceholderText(
            '{\n  "client_name": "Иванов Иван",\n  "policy": { ... },\n  "payments": [ ... ]\n}'
        )
        if json_text:
            self.text_edit.setPlainText(json_text)
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

        self._restore_geometry()

    def on_import_clicked(self):
        text = self.text_edit.toPlainText()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Вставьте JSON с данными полиса.")
            return

        try:
            client_name, policy_data, payments_data = prepare_policy_payload(
                text,
                forced_client=self._forced_client,
                forced_deal=self._forced_deal,
            )
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "Ошибка JSON", f"Ошибка разбора JSON:\n{e}")
            return
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", str(e))
            return

        # Поиск клиента (если не передан принудительно)
        if self._forced_client is not None:
            client = self._forced_client
        else:
            matches = [
                c for c in get_all_clients() if client_name.lower() in c.name.lower()
            ]

            if not matches:
                resp = QMessageBox.question(
                    self,
                    "Клиент не найден",
                    f"Клиент «{client_name}» не найден. Создать нового?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if resp != QMessageBox.Yes:
                    return
                client = add_client(name=client_name)
            elif len(matches) == 1:
                client = matches[0]
            else:
                names = [c.name for c in matches]
                selected_name, ok = QInputDialog.getItem(
                    self,
                    "Выбор клиента",
                    f"Найдено несколько клиентов по имени «{client_name}». Выберите нужного:",
                    names,
                    editable=False,
                )
                if not ok:
                    return
                client = next(c for c in matches if c.name == selected_name)

        form = PolicyForm(
            forced_client=client,
            forced_deal=self._forced_deal,
            parent=self,
            context=getattr(self, "_context", None),
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
                    try:
                        dt = datetime.strptime(val, "%Y-%m-%d").date()
                        widget.setDate(dt)
                    except ValueError:
                        pass  # игнорируем ошибки даты

        # В примечание дописываем ФИО страхователя
        note_widget = form.fields.get("note")
        if note_widget and client_name:
            prev = note_widget.text().strip() if hasattr(note_widget, "text") else ""
            sep = "\n" if prev else ""
            note_widget.setText(f"{prev}{sep}{client_name}")

        # Заполняем черновые платежи
        for pay in payments_data:
            form.add_payment_row(pay)

        if form.exec():
            self.imported_policy = getattr(form, "saved_instance", None)
            self.accept()

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def accept(self):  # type: ignore[override]
        self._save_geometry()
        super().accept()

    def reject(self):  # type: ignore[override]
        self._save_geometry()
        super().reject()

    def closeEvent(self, event):  # type: ignore[override]
        self._save_geometry()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Geometry persistence helpers
    # ------------------------------------------------------------------

    def _restore_geometry(self) -> None:
        geometry_b64 = ui_settings.get_window_settings(SETTINGS_KEY).get("geometry")
        if not geometry_b64:
            return
        try:
            geometry_bytes = base64.b64decode(geometry_b64)
        except Exception:  # pragma: no cover - восстановление необязательно
            return
        try:
            self.restoreGeometry(QByteArray(geometry_bytes))
        except Exception:  # pragma: no cover - восстановление необязательно
            pass

    def _save_geometry(self) -> None:
        try:
            geometry = self.saveGeometry()
        except Exception:  # pragma: no cover - сохранение необязательно
            return
        if not geometry:
            return
        try:
            geometry_b64 = base64.b64encode(bytes(geometry)).decode("ascii")
        except Exception:  # pragma: no cover - сохранение необязательно
            return
        settings = ui_settings.get_window_settings(SETTINGS_KEY)
        settings["geometry"] = geometry_b64
        ui_settings.set_window_settings(SETTINGS_KEY, settings)
