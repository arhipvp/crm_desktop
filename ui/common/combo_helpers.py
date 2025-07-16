from __future__ import annotations

from typing import Any, Callable

from peewee import Model
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QCompleter

from services.client_service import get_all_clients
from services.deal_service import get_all_deals, get_deals_by_client_id
from services.policy_service import get_all_policies


def populate_combo(
    combo: QComboBox,
    items: list,
    label_func: Callable[[Any], str] = str,
    id_attr: str = "id",
    placeholder: str | None = None,
) -> None:
    """Заполняет существующий QComboBox элементами *items*.

    :param combo: уже созданный QComboBox.
    :param items: iterable моделей/значений.
    :param label_func: функция, превращающая элемент в отображаемую строку.
    :param id_attr: атрибут объекта, который кладётся в userData.
    :param placeholder: необязательный элемент‑заглушка (первым).
    """
    combo.clear()
    if placeholder:
        combo.addItem(placeholder, None)
    for obj in items:
        combo.addItem(label_func(obj), getattr(obj, id_attr, obj))


def setup_completer(combo: QComboBox) -> None:
    """Делает выпадающий список ищущим по подстроке (case‑insensitive)."""
    if not combo.isEditable():
        combo.setEditable(True)

    completer = QCompleter(combo.model(), combo)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    completer.setFilterMode(Qt.MatchContains)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    combo.setCompleter(completer)


def create_entity_combobox(
    items: list,
    label_func: Callable[[Any], str] = str,
    id_attr: str = "id",
    placeholder: str | None = None,
    dialog_threshold: int = 300,
) -> QComboBox:
    """Универсальный фабричный метод для QComboBox.

    * Заполняет список элементов.
    * При длинных выборках (> *dialog_threshold*) открывает SearchDialog.
    * Включает автодополнение по подстроке.
    """
    combo = QComboBox()
    populate_combo(combo, items, label_func, id_attr, placeholder)

    if len(items) > dialog_threshold:
        # При большом количестве записей удобнее отдельный диалог поиска
        from .search_dialog import (
            SearchDialog,
        )  # локальный импорт, чтобы избежать циклов

        combo.setEditable(True)
        combo.view().hide()  # подавляем стандартный дроп‑даун

        def open_search():
            search_items = [label_func(it) for it in items]
            if placeholder:
                search_items.insert(0, placeholder)

            dlg = SearchDialog(search_items, combo)
            if dlg.exec():
                text = dlg.selected_index
                idx = combo.findText(text, Qt.MatchExactly)
                if idx >= 0:
                    combo.setCurrentIndex(idx)

        combo.mousePressEvent = lambda e: open_search()  # type: ignore  # noqa: E731
        if combo.lineEdit():
            combo.lineEdit().setPlaceholderText("Кликните для поиска…")

    setup_completer(combo)
    return combo


# --- Фабрики для конкретных сущностей -----------------------------------------------------------


def create_client_combobox() -> QComboBox:
    clients = list(get_all_clients())
    return create_entity_combobox(
        items=clients,
        label_func=lambda c: c.name,
        id_attr="id",
        placeholder="— Клиент —",
    )


def create_deal_combobox(client_id: int | None = None) -> QComboBox:
    """Комбобокс сделок с необязательной фильтрацией по клиенту."""
    deals = (
        list(get_deals_by_client_id(client_id))
        if client_id is not None
        else list(get_all_deals())
    )
    return create_entity_combobox(
        items=deals,
        label_func=lambda d: f"{d.client.name} - {d.description} ",
        id_attr="id",
        placeholder="— Сделка —",
    )


def create_policy_combobox() -> QComboBox:
    policies = list(get_all_policies())
    return create_entity_combobox(
        items=policies,
        label_func=lambda p: f"{p.policy_number} - {p.client.name}",
        id_attr="id",
        placeholder="— Полис —",
    )


def create_fk_combobox(
    model_cls: type[Model],
    label_func: Callable[[Any], str] = str,
    id_attr: str = "id",
    placeholder: str | None = None,
) -> QComboBox:
    """Универсальный комбобокс для ForeignKey‑полей."""
    items = list(model_cls.select())
    return create_entity_combobox(
        items=items,
        label_func=label_func,
        id_attr=id_attr,
        placeholder=placeholder,
    )


def create_policy_combobox_for_deal(deal_id) -> QComboBox:
    from services.policy_service import get_policies_by_deal_id

    policies = list(get_policies_by_deal_id(deal_id))
    return create_entity_combobox(
        items=policies,
        label_func=lambda p: f"#{p.id} {p.policy_number}",
        id_attr="id",
        placeholder="— Полис —",
    )


# --- Комбобокс для произвольного списка строк ---------------------------------------------------


def create_editable_combo(options: list[str]) -> QComboBox:
    """Возвращает редактируемый QComboBox со списком уникальных опций."""
    combo = QComboBox()
    combo.setEditable(True)
    combo.addItem("—", None)

    cleaned_options = sorted({o.strip() for o in options if o and o.strip()})
    for option in cleaned_options:
        combo.addItem(option, userData=option)

    combo.setInsertPolicy(QComboBox.InsertAtTop)
    combo.setDuplicatesEnabled(False)
    combo.setPlaceholderText("— выберите или введите —")

    setup_completer(combo)
    return combo


def get_selected_item(combo: QComboBox) -> Any:
    """Вернуть объект, связанный с текущим выбранным элементом."""
    return combo.currentData()


def set_selected_by_id(combo: QComboBox, value_id: Any) -> None:
    """Установить текущий элемент по userData (например, id модели)."""
    for index in range(combo.count()):
        if combo.itemData(index) == value_id:
            combo.setCurrentIndex(index)
            break
