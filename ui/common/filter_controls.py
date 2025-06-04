# ui/common/filter_controls.py

from datetime import date
from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (QDateEdit, QHBoxLayout, QLabel, QPushButton,
                               QWidget)

from ui.common.checkbox_filters import CheckboxFilters
from ui.common.date_utils import OptionalDateEdit, TypableDateEdit
from ui.common.search_box import SearchBox


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
    parent : QWidget, optional
        Родительский виджет.
    show_date_range : bool, optional
        Отображать ли фильтр диапазона дат «С/По», по умолчанию True.
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
        parent=None,
        *,
        show_date_range: bool = True,
    ):
        super().__init__(parent)
        extra_widgets = extra_widgets or []

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Поиск
        self._search = SearchBox(search_callback)
        self._search.search_input.setPlaceholderText(search_placeholder)

        if show_date_range:
            self._date_from = OptionalDateEdit()
            self._date_to = OptionalDateEdit()
            if on_filter:
                self._date_from.dateChanged.connect(on_filter)
                self._date_to.dateChanged.connect(on_filter)

            layout.addWidget(QLabel("С:"))
            layout.addWidget(self._date_from)
            layout.addWidget(QLabel("По:"))
            layout.addWidget(self._date_to)
        else:
            self._date_from = None
            self._date_to = None

        layout.addWidget(self._search)

        # Чекбоксы
        self._cbx = None
        if checkbox_map:
            self._cbx = CheckboxFilters(checkbox_map, self)
            layout.addWidget(self._cbx)

        # Дата-фильтр
        self._date_filter_field = date_filter_field
        if date_filter_field:
            self._date_edit = OptionalDateEdit()
            self._date_edit.setCalendarPopup(True)
            self._date_edit.setDisplayFormat("dd.MM.yyyy")
            self._date_edit.setDate(QDate.currentDate())
            if on_filter:
                self._date_edit.dateChanged.connect(on_filter)
            layout.addWidget(QLabel("Срок до:"))
            layout.addWidget(self._date_edit)

        # Дополнительные виджеты
        for label, widget in extra_widgets:
            layout.addWidget(QLabel(label))
            layout.addWidget(widget)

        # Кнопка экспорта
        if export_callback:
            export_btn = QPushButton("📤 Экспорт CSV", clicked=export_callback)
            export_btn.setFixedHeight(30)
            layout.addWidget(export_btn)

        layout.addStretch()

    def get_search_text(self) -> str:
        """Возвращает текст из поля поиска (без пробелов)."""
        return self._search.get_text().strip()

    def is_checked(self, label: str) -> bool:
        """Проверяет, установлен ли чекбокс с заданной меткой."""
        return self._cbx.is_checked(label) if self._cbx else False

    def get_date_filter(self) -> dict[str, date] | None:
        """
        Возвращает словарь {<имя_поля>: date} если дата указана, иначе None.
        Пример: {'due_date': datetime.date(2025, 5, 10)}
        """
        if self._date_filter_field and self._date_from and self._date_to:
            d1 = self._date_from.date_or_none()
            d2 = self._date_to.date_or_none()
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
        """Сбрасывает все фильтры: поиск, даты, чекбоксы."""
        self._search.clear()
        if self._cbx:
            self._cbx.clear()
        self._date_from.clear()
        self._date_to.clear()
        if hasattr(self, "_date_edit"):
            self._date_edit.clear()
