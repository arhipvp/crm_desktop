from __future__ import annotations

from ui.common.combo_helpers import create_fk_combobox

"""ui/base/base_edit_form.py – универсальная форма CRUD.

Изменения:
──────────
• Для любого `DateField(null=True)` теперь используется `QDateEdit` с возможностью очистки,
  что позволяет очищать дату (✕ или Del) → в БД пишется NULL.
• Обычные обязательные даты остались на `TypableDateEdit`.
• Код автосохранения/валидаторов не трогался.
"""
import logging
import datetime as dt

import peewee
from peewee import BooleanField, DateField, ForeignKeyField
from PySide6.QtCore import QDate, QDateTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui.common.date_utils import TypableDateEdit, configure_optional_date_edit
from ui.common.message_boxes import confirm
from ui.common.styled_widgets import styled_button
from services.validators import normalize_number
from utils.screen_utils import get_scaled_size

logger = logging.getLogger(__name__)


class TwoColumnFormLayout:
    """Менеджер строк, раскладывающий поля формы по двум колонкам."""

    def __init__(self, container: QWidget):
        self.container = container
        self.grid = QGridLayout(container)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setColumnStretch(1, 1)
        self.grid.setColumnStretch(3, 1)
        self.grid.setHorizontalSpacing(24)
        self.rows: list[tuple[QWidget, QWidget]] = []

    def _normalize_label(self, label: QLabel | str | QWidget) -> QWidget:
        if isinstance(label, QWidget):
            return label

        text = str(label)
        if text and not text.endswith(":"):
            text = text + ":"
        widget = QLabel(text, parent=self.container)
        return widget

    def _refresh_layout(self) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if widget := item.widget():
                widget.setParent(self.container)

        column_rows = [0, 0]
        for index, (label, field) in enumerate(self.rows):
            column = index % 2
            row = column_rows[column]
            base_col = column * 2
            self.grid.addWidget(label, row, base_col)
            self.grid.addWidget(field, row, base_col + 1)
            column_rows[column] += 1

    def addRow(self, label: QLabel | str | QWidget, field: QWidget) -> None:
        label_widget = self._normalize_label(label)
        self.rows.append((label_widget, field))
        self._refresh_layout()

    def insertRow(
        self, position: int, label: QLabel | str | QWidget, field: QWidget
    ) -> None:
        label_widget = self._normalize_label(label)
        if position < 0:
            position = 0
        position = min(position, len(self.rows))
        self.rows.insert(position, (label_widget, field))
        self._refresh_layout()


class BaseEditForm(QDialog):
    """Универсальная форма создания/редактирования, строится по Peewee‑модели."""

    EXTRA_HIDDEN: set[str] = set()

    def __init__(
        self, instance=None, model_class=None, entity_name="объект", parent=None
    ):
        super().__init__(parent)
        self.instance = instance
        self.model_class = model_class or type(instance)
        self.entity_name = entity_name
        self.fields: dict[str, object] = {}
        self._dirty = False

        self.setWindowTitle(
            f"Редактировать {entity_name}" if instance else f"Добавить {entity_name}"
        )
        self.setMinimumWidth(640)

        # ── layout ──
        self.layout = QVBoxLayout(self)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.layout.addWidget(self.scroll_area)

        self.form_widget = QWidget()
        self.scroll_area.setWidget(self.form_widget)
        self.form_layout = TwoColumnFormLayout(self.form_widget)

        # build widgets
        self.build_form()
        if self.instance:
            self.fill_from_obj(self.instance)
        self._create_button_panel()
        # Размеры формы определяем по содержимому
        self.adjustSize()
        self.setMinimumHeight(self.height())
        self.resize(get_scaled_size(960, 720))
        self._dirty = False

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _create_button_panel(self):
        btns = QHBoxLayout()
        self.save_btn = styled_button(
            "Сохранить", icon="💾", role="primary", shortcut="Ctrl+S"
        )
        self.save_btn.setDefault(True)
        self.cancel_btn = styled_button("Отмена", icon="❌", shortcut="Esc")

        self.save_btn.clicked.connect(self.save)
        self.cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.save_btn)
        btns.addWidget(self.cancel_btn)
        self.layout.addLayout(btns)

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------
    def closeEvent(self, event):
        if self._dirty:
            if not confirm("Есть несохранённые изменения. Закрыть без сохранения?"):
                event.ignore()
                return
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Build form
    # ------------------------------------------------------------------
    def build_form(self):
        """Строит виджеты для всех полей модели."""
        self.build_custom_fields()  # кастомные поля до автогенерации

        for field in self.get_fields():
            name = field.name
            if name in ("id", "is_deleted"):
                continue

            # ---------- ForeignKey → <name>_id ----------
            if isinstance(field, ForeignKeyField):
                field_name = f"{name}_id"
                rel_model = field.rel_model

                if hasattr(rel_model, "__str__"):
                    widget = create_fk_combobox(rel_model)
                else:
                    widget = QLineEdit()

            # ---------- Boolean ----------
            elif isinstance(field, BooleanField):
                field_name = name
                widget = QCheckBox()

            # ---------- Date ----------
            elif isinstance(field, DateField):
                field_name = name
                # Для поля end_date — всегда TypableDateEdit (без крестика)
                if field_name == "end_date":
                    widget = TypableDateEdit()
                else:
                    if field.null:
                        widget = QDateEdit()
                        widget.setCalendarPopup(True)
                        widget.setSpecialValueText("—")
                        configure_optional_date_edit(widget)
                    else:
                        widget = TypableDateEdit()
                        if self.instance is None:
                            widget.setDate(QDate.currentDate())

            # ---------- Default (Char / Text / Numeric) ----------
            else:
                field_name = name
                widget = QLineEdit()

            # если потомок уже создал виджет с таким именем – пропускаем
            if field_name in self.fields:
                continue

            self.fields[field_name] = widget
            self.form_layout.addRow(self._prettify(field_name), widget)

            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self._mark_dirty)
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(self._mark_dirty)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self._mark_dirty)
            elif isinstance(widget, QDateEdit):
                widget.dateChanged.connect(self._mark_dirty)

            # вызов хука update_context, если он определён
        if hasattr(self, "update_context"):
            self.update_context()

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------
    def _mark_dirty(self, *_):
        self._dirty = True

    def _prettify(self, name: str) -> str:
        return name.replace("_", " ").capitalize() + ":"

    # ------------------------------------------------------------------
    # Fill form from obj
    # ------------------------------------------------------------------
    def fill_from_obj(self, obj):
        for name, widget in self.fields.items():
            # FK → .id
            if name.endswith("_id"):
                rel = name[:-3]
                value = getattr(obj, rel, None)
                value = value.id if value else None
                if isinstance(widget, QComboBox):
                    if value is not None:  # ← вот это добавляем
                        idx = widget.findData(value)
                        if idx >= 0:
                            widget.setCurrentIndex(idx)
                continue

            else:
                value = getattr(obj, name, "")

            if isinstance(widget, QLineEdit):
                widget.setText(str(value) if value is not None else "")
            elif isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QComboBox):
                idx = widget.findData(value)
                if idx >= 0:
                    widget.setCurrentIndex(idx)
            elif isinstance(widget, QDateEdit):
                if value:
                    widget.setDate(QDate(value.year, value.month, value.day))

    # ------------------------------------------------------------------
    # Collect & Save
    # ------------------------------------------------------------------
    def collect_data(self) -> dict:
        """Собирает данные со всех виджетов и приводит к типам Peewee."""
        data: dict = {}
        for name, widget in self.fields.items():
            value = None

            # ---------- QLineEdit ----------
            if isinstance(widget, QLineEdit):
                txt = widget.text().strip()
                value = txt or None

                lookup_name = name[:-3] if name.endswith("_id") else name
                field = self.model_class._meta.fields.get(lookup_name)

                if isinstance(field, peewee.IntegerField):
                    if value is not None:
                        value = int(normalize_number(value))
                elif isinstance(field, peewee.FloatField):
                    if value is not None:
                        value = float(normalize_number(value))
                elif isinstance(field, peewee.DecimalField):
                    if value is not None:
                        from decimal import Decimal, InvalidOperation

                        num = normalize_number(value)
                        try:
                            value = Decimal(num) if num is not None else None
                        except (InvalidOperation, TypeError):
                            # Fallback: try float -> Decimal to be permissive
                            value = Decimal(str(float(num))) if num is not None else None
                elif isinstance(field, peewee.DateField):
                    value = (
                        QDate.fromString(txt, "dd.MM.yyyy").toPython() if txt else None
                    )
                elif isinstance(field, peewee.DateTimeField):
                    if txt:
                        try:
                            value = dt.datetime.fromisoformat(txt)
                        except ValueError:
                            value = QDateTime.fromString(txt, "yyyy-MM-dd").toPython()
                    else:
                        value = None

            # ---------- QCheckBox ----------
            elif isinstance(widget, QCheckBox):
                value = widget.isChecked()

            # ---------- QComboBox ----------
            elif isinstance(widget, QComboBox):
                value = widget.currentData()

            # ---------- DateEdit ----------
            elif isinstance(widget, QDateEdit):
                qd = widget.date()
                value = None if qd == widget.minimumDate() else qd.toPython()

            data[name] = value
        return data

    # ------------------------------------------------------------------
    # Template methods
    # ------------------------------------------------------------------
    def save(self):
        try:
            saved = self.save_data()
            if saved:
                self.saved_instance = saved
                self._dirty = False
                self.accept()
        except Exception:
            logger.exception("❌ Ошибка при сохранении в %s", self.__class__.__name__)
            QMessageBox.critical(
                self, "Ошибка", f"Не удалось сохранить {self.entity_name}."
            )

    def save_data(self):
        raise NotImplementedError

    # child‑hooks -------------------------------------------------------
    def get_fields(self):
        HIDDEN = {"drive_folder_path", "drive_folder_link", "is_deleted"}
        custom_hidden = getattr(self, "EXTRA_HIDDEN", set())
        if not hasattr(self.model_class, "_meta") or not hasattr(
            self.model_class._meta, "sorted_fields"
        ):
            return []
        return [
            f
            for f in self.model_class._meta.sorted_fields
            if f.name not in HIDDEN | custom_hidden
        ]

    def build_custom_fields(self):
        """Потомки могут добавить дополнительные виджеты до автогенерации."""
        pass
