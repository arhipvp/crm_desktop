# ui/common/filter_controls.py

from datetime import date

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QSizePolicy,
    QCheckBox,
    QLineEdit,
    QDateEdit,
)

from ui import settings as ui_settings

from ui.common.checkbox_filters import CheckboxFilters
from ui.common.date_utils import get_date_or_none


class FilterControls(QWidget):
    """
    Панель фильтров: поиск + чекбоксы + фильтр по дате + экспорт + кастомные виджеты.

    Parameters
    ----------
    search_callback : callable
        Функция, вызываемая при изменении текста в поиске.
    checkbox_map : dict[str, callable], optional
        Словарь вида {"Метка": функция-переключатель}, по умолчанию None.
    export_callback : callable, optional
        Функция для экспорта в CSV, по умолчанию None.
    search_placeholder : str, optional
        Подсказка для поля поиска, по умолчанию "Поиск…".
    extra_widgets : list[tuple[str, QWidget]], optional
        Дополнительные виджеты (метка + виджет), по умолчанию [].
    date_filter_field : str, optional
        Название поля даты для фильтрации (например, "due_date"), по умолчанию None.
    on_filter : callable, optional
        Универсальная функция, вызываемая при изменении фильтров (дата/чекбоксы).
    reset_callback : callable, optional
        Функция, вызываемая после очистки фильтров, по умолчанию None.
    parent : QWidget, optional
        Родительский виджет.
    settings_name : str, optional
        Имя секции в файле настроек для сохранения фильтров.
    """

    def __init__(
        self,
        search_callback,
        checkbox_map=None,
        export_callback=None,
        search_placeholder="Поиск…",
        extra_widgets=None,
        date_filter_field: str | None = None,
        on_filter=None,
        reset_callback=None,
        parent=None,
        settings_name: str | None = None,
    ):
        super().__init__(parent)
        extra_widgets = extra_widgets or []
        self._settings_name = settings_name

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Поиск
        self._search = QLineEdit()
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(search_callback)
        self._search.setPlaceholderText(search_placeholder)

        self._date_filter_field = date_filter_field
        if date_filter_field:
            self._date_from = QDateEdit()
            self._date_from.setCalendarPopup(True)
            self._date_from.setSpecialValueText("—")
            self._date_from.clear()
            self._date_to = QDateEdit()
            self._date_to.setCalendarPopup(True)
            self._date_to.setSpecialValueText("—")
            self._date_to.clear()
            if on_filter:
                self._date_from.dateChanged.connect(on_filter)
                self._date_to.dateChanged.connect(on_filter)

            layout.addWidget(QLabel("С:"))
            layout.addWidget(self._date_from)
            layout.addWidget(QLabel("По:"))
            layout.addWidget(self._date_to)

        layout.addWidget(self._search)

        # Чекбоксы
        self._cbx = None
        if checkbox_map:
            self._cbx = CheckboxFilters(checkbox_map, self)
            layout.addWidget(self._cbx)

        # Дополнительные виджеты
        for label, widget in extra_widgets:
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)

        # Кнопка экспорта
        self.export_all_checkbox = None
        if export_callback:
            export_btn = QPushButton("📤 Экспорт CSV")
            self.export_all_checkbox = QCheckBox("Экспортировать всё")
            export_btn.clicked.connect(
                lambda: export_callback(
                    all_rows=self.export_all_checkbox.isChecked()
                )
            )
            export_btn.setFixedHeight(30)
            layout.addWidget(export_btn)
            layout.addWidget(self.export_all_checkbox)

        # Кнопка сброса
        self.reset_btn = QPushButton("Сбросить")
        self.reset_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.reset_btn.setMinimumWidth(self.reset_btn.fontMetrics().horizontalAdvance("Сбросить") + 12)
        self.reset_btn.setFixedHeight(30)

        def on_reset():
            self.clear_all()
            if reset_callback:
                reset_callback()

        self.reset_btn.clicked.connect(on_reset)
        layout.addWidget(self.reset_btn)

        layout.addStretch()

        if self._settings_name:
            self._restore_saved_filters()
            self._connect_save_signals()

    def get_search_text(self) -> str:
        """Возвращает текст из поля поиска (без пробелов)."""
        return self._search.text().strip()

    def set_text(self, text: str) -> None:
        """Устанавливает текст в поле поиска."""
        self._search.setText(text)

    def focus_search(self) -> None:
        """Устанавливает фокус на поле поиска."""
        self._search.setFocus()

    def is_checked(self, label: str) -> bool:
        """Проверяет, установлен ли чекбокс с заданной меткой."""
        return self._cbx.is_checked(label) if self._cbx else False

    def get_date_filter(self) -> dict[str, date] | None:
        """
        Возвращает словарь {<имя_поля>: date} если дата указана, иначе None.
        Пример: {'due_date': datetime.date(2025, 5, 10)}
        """
        if self._date_filter_field:
            d1 = get_date_or_none(self._date_from)
            d2 = get_date_or_none(self._date_to)
            if d1 or d2:
                return {self._date_filter_field: (d1, d2)}
        return None

    def add_extra_widgets(self, widgets: list[tuple[str, QWidget]]):
        """
        Добавляет дополнительные виджеты в строку фильтров.

        Аргумент:
            widgets — список кортежей (метка, виджет), которые будут добавлены.
        """
        for label, widget in widgets:
            self.layout().addWidget(QLabel(label))
            self.layout().addWidget(widget)

    def get_all_filters(self) -> dict:
        """Возвращает словарь всех фильтров: текст, чекбоксы, даты."""
        return {
            "search": self.get_search_text(),
            "checkboxes": self._cbx.get_all_states() if self._cbx else {},
            "dates": self.get_date_filter() or {},
        }

    def clear_all(self):
        """Сбрасывает все фильтры: поиск, даты, чекбоксы, не излучая сигналов."""
        self._search.blockSignals(True)
        self._search.clear()
        self._search.blockSignals(False)

        if self._cbx:
            for box in self._cbx.checkboxes.values():
                box.blockSignals(True)
                box.setChecked(False)
                box.blockSignals(False)

        if hasattr(self, "_date_from"):
            self._date_from.blockSignals(True)
            self._date_from.clear()
            self._date_from.blockSignals(False)

        if hasattr(self, "_date_to"):
            self._date_to.blockSignals(True)
            self._date_to.clear()
            self._date_to.blockSignals(False)

        if self._settings_name:
            self._save_current_filters()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _restore_saved_filters(self):
        data = ui_settings.get_table_filters(self._settings_name)
        if not data:
            return
        search = data.get("search")
        if search:
            self.set_text(search)
        if self._cbx:
            self._cbx.set_bulk(data.get("checkboxes", {}))
        dates = data.get("dates", {})
        if self._date_filter_field and self._date_filter_field in dates:
            d1_str, d2_str = dates.get(self._date_filter_field, [None, None])
            d1 = date.fromisoformat(d1_str) if d1_str else None
            d2 = date.fromisoformat(d2_str) if d2_str else None
            if d1:
                self._date_from.setDate(QDate(d1.year, d1.month, d1.day))
            if d2:
                self._date_to.setDate(QDate(d2.year, d2.month, d2.day))

    def _collect_filters_for_save(self) -> dict:
        data = self.get_all_filters()
        dates = {}
        for field, rng in data.get("dates", {}).items():
            d1, d2 = rng
            dates[field] = [
                d1.isoformat() if isinstance(d1, date) else None,
                d2.isoformat() if isinstance(d2, date) else None,
            ]
        data["dates"] = dates
        return data

    def _save_current_filters(self):
        if not self._settings_name:
            return
        ui_settings.set_table_filters(self._settings_name, self._collect_filters_for_save())

    def _connect_save_signals(self):
        self._search.textChanged.connect(self._save_current_filters)
        if hasattr(self, "_date_from"):
            self._date_from.dateChanged.connect(self._save_current_filters)
        if hasattr(self, "_date_to"):
            self._date_to.dateChanged.connect(self._save_current_filters)
        if self._cbx:
            for cb in self._cbx.checkboxes.values():
                cb.stateChanged.connect(self._save_current_filters)

