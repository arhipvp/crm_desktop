from __future__ import annotations

from ui.common.combo_helpers import create_fk_combobox

"""ui/base/base_edit_form.py – универсальная форма CRUD.

Изменения:
──────────
• Для любого `DateField(null=True)` теперь используется `OptionalDateEdit`,
  что позволяет очищать дату (✕ или Del) → в БД пишется NULL.
• Обычные обязательные даты остались на `TypableDateEdit`.
• Код автосохранения/валидаторов не трогался.
"""
import logging

import peewee
from peewee import BooleanField, DateField, ForeignKeyField
from PySide6.QtCore import QDate, QDateTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from ui.common.date_utils import OptionalDateEdit, TypableDateEdit
from ui.common.styled_widgets import styled_button

logger = logging.getLogger(__name__)


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

        self.setWindowTitle(
            f"Редактировать {entity_name}" if instance else f"Добавить {entity_name}"
        )
        self.setMinimumWidth(420)

        # ── layout ──
        self.layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        self.layout.addLayout(self.form_layout)

        # build widgets
        self.build_form()
        if self.instance:
            self.fill_from_obj(self.instance)
        self._create_button_panel()

    # ------------------------------------------------------------------
    # UI helpers
    # ------------------------------------------------------------------
    def _create_button_panel(self):
        btns = QHBoxLayout()
        self.save_btn = styled_button("Сохранить", icon="💾", role="primary")
        self.save_btn.setDefault(True)
        self.cancel_btn = styled_button("Отмена", icon="❌")
        self.cancel_btn.setShortcut("Esc")

        self.save_btn.clicked.connect(self.save)
        self.cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.save_btn)
        btns.addWidget(self.cancel_btn)
        self.layout.addLayout(btns)

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
                    widget = OptionalDateEdit() if field.null else TypableDateEdit()

            # ---------- Default (Char / Text / Numeric) ----------
            else:
                field_name = name
                widget = QLineEdit()

            # если потомок уже создал виджет с таким именем – пропускаем
            if field_name in self.fields:
                continue

            self.fields[field_name] = widget
            self.form_layout.addRow(QLabel(self._prettify(field_name)), widget)

            # вызов хука update_context, если он определён
        if hasattr(self, "update_context"):
            self.update_context()

    # ------------------------------------------------------------------
    # Utils
    # ------------------------------------------------------------------
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
                    value = int(value) if value is not None else None
                elif isinstance(field, peewee.FloatField):
                    value = float(value) if value is not None else None
                elif isinstance(field, peewee.DateField):
                    value = (
                        QDate.fromString(txt, "dd.MM.yyyy").toPython() if txt else None
                    )
                elif isinstance(field, peewee.DateTimeField):
                    value = (
                        QDateTime.fromString(txt, "yyyy-MM-dd").toPython()
                        if txt
                        else None
                    )

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
