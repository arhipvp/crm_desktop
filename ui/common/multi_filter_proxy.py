from __future__ import annotations

"""Прокси‑модель с поддержкой фильтрации по нескольким колонкам."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
import math
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Sequence, Set, Tuple

from PySide6.QtCore import (
    QDate,
    QRegularExpression,
    Qt,
    QSortFilterProxyModel,
)


@dataclass(eq=True)
class ColumnFilterState:
    """Описывает выбранное пользователем состояние фильтра."""

    type: str
    value: Any
    display: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    def is_empty(self) -> bool:
        """Проверяет, содержит ли фильтр фактическое значение."""

        if self.type == "text":
            return not str(self.value or "").strip()
        if self.type == "bool":
            return self.value is None
        if self.type == "date_range":
            if not isinstance(self.value, Mapping):
                return True
            return not (self.value.get("from") or self.value.get("to"))
        if self.type == "number":
            return self.value is None or str(self.value) == ""
        if self.type == "choices":
            if self.value is None:
                return True
            if isinstance(self.value, (list, tuple, set, frozenset)):
                return len(self.value) == 0
            if isinstance(self.value, Mapping):
                return len(self.value) == 0
            return False
        return self.value is None

    def display_text(self) -> str:
        """Текст для отображения в заголовке таблицы."""

        if self.display:
            return self.display
        if self.type == "text":
            return str(self.value or "")
        if self.type == "bool":
            if self.value is True:
                return "Да"
            if self.value is False:
                return "Нет"
            return ""
        if self.type == "date_range" and isinstance(self.value, Mapping):
            start = self.value.get("from")
            end = self.value.get("to")
            parts: list[str] = []
            if start:
                parts.append(self._format_iso_date(start))
            if end:
                parts.append(self._format_iso_date(end))
            return " — ".join(parts)
        if self.type == "number":
            return "" if self.value is None else str(self.value)
        if self.type == "choices":
            values = self._choices_values()
            if not values:
                return ""
            labels = self._choices_labels(values)
            if len(labels) > 3:
                return f"Выбрано {len(labels)}"
            return ", ".join(labels)
        return "" if self.value is None else str(self.value)

    def backend_value(self) -> Optional[str | list[str]]:
        """Возвращает представление фильтра для передачи в сервисы."""

        if self.type == "text":
            value = str(self.value or "").strip()
            return value or None
        if self.type == "bool":
            if self.value is None:
                return None
            return "1" if bool(self.value) else "0"
        if self.type == "number":
            if self.value is None:
                return None
            return str(self.value)
        if self.type == "choices":
            raw_values = self._choices_values(raw=True)
            collected: list[str] = []
            for item in raw_values:
                text = self._choice_backend_text(item)
                if text:
                    collected.append(text)
            if not collected:
                return None
            is_multi = isinstance(self.value, (list, tuple, set, frozenset))
            if not is_multi:
                return collected[0]
            return collected
        # Для диапазонов и прочих сложных типов серверная фильтрация не поддерживается.
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Преобразует состояние фильтра к сериализуемому виду."""

        data: Dict[str, Any] = {"type": self.type}
        if self.type == "choices":
            if self.value is None:
                data["value"] = None
            else:
                values = []
                for item in self._choices_values(raw=True):
                    if isinstance(item, Mapping):
                        raw_text = self._stringify_choice_part(item.get("value"))
                        if raw_text is None:
                            display_text = self._stringify_choice_part(
                                item.get("display")
                            )
                            if display_text is not None:
                                values.append(display_text)
                                continue
                    values.append(item)
                data["value"] = list(values)
                container = self._choices_container(self.value)
                if container:
                    data["value_container"] = container
        else:
            data["value"] = self.value
        if self.display is not None:
            data["display"] = self.display
        if self.meta:
            data["meta"] = self.meta
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | None) -> Optional["ColumnFilterState"]:
        """Восстанавливает состояние фильтра из словаря."""

        if not isinstance(data, Mapping):
            return None
        type_ = data.get("type")
        if not type_:
            return None
        value_container = data.get("value_container")
        value = data.get("value")
        if type_ == "choices":
            value = cls._restore_choices_value(value, value_container)
        display = data.get("display")
        meta = data.get("meta")
        if meta is not None and not isinstance(meta, dict):
            meta = None
        return cls(str(type_), value, display if isinstance(display, str) else None, meta)

    @staticmethod
    def _format_iso_date(value: str) -> str:
        try:
            parsed = date.fromisoformat(value)
        except (TypeError, ValueError):
            return value
        return parsed.strftime("%d.%m.%Y")

    def _choices_values(self, raw: bool = False) -> list[Any]:
        values = self._flatten_choices(self.value)
        if raw:
            return values
        if not values:
            return values
        order = None
        if isinstance(self.meta, Mapping):
            order = self.meta.get("choices_order")
        if isinstance(order, list):
            remaining = list(values)
            ordered: list[Any] = []
            for item in order:
                try:
                    while True:
                        index = remaining.index(item)
                        ordered.append(remaining.pop(index))
                except ValueError:
                    continue
            ordered.extend(remaining)
            return ordered
        return values

    def _choices_labels(self, values: list[Any]) -> list[str]:
        if not isinstance(self.meta, Mapping):
            return [str(item) for item in values]
        display_values = self.meta.get("choices_display")
        if isinstance(display_values, list) and len(display_values) == len(values):
            return [str(item) for item in display_values]
        labels_map = self.meta.get("choices_labels")
        if isinstance(labels_map, Mapping):
            return [str(labels_map.get(item, item)) for item in values]
        return [str(item) for item in values]

    @staticmethod
    def _flatten_choices(value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return list(value)
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, (set, frozenset)):
            return list(value)
        return [value]

    @staticmethod
    def _choices_container(value: Any) -> Optional[str]:
        if isinstance(value, set):
            return "set"
        if isinstance(value, frozenset):
            return "frozenset"
        if isinstance(value, tuple):
            return "tuple"
        return None

    @staticmethod
    def _restore_choices_value(value: Any, container: Any) -> Any:
        if value is None:
            return None
        values = ColumnFilterState._flatten_choices(value)
        if not isinstance(container, str):
            return values
        if container == "set":
            return set(values)
        if container == "frozenset":
            return frozenset(values)
        if container == "tuple":
            return tuple(values)
        return values

    @staticmethod
    def _stringify_choice_part(raw: Any) -> Optional[str]:
        if raw is None:
            return None
        if isinstance(raw, str):
            text = raw.strip()
        else:
            text = str(raw).strip()
        return text or None

    def _choice_backend_text(self, item: Any) -> Optional[str]:
        if isinstance(item, Mapping):
            value_text = self._stringify_choice_part(item.get("value"))
            if value_text is not None:
                return value_text
            return self._stringify_choice_part(item.get("display"))
        return self._stringify_choice_part(item)


_IDENTIFIER_KEYS: Tuple[str, ...] = ("id", "pk", "value", "key", "code", "uuid")


def _freeze_choice_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(
            sorted((key, _freeze_choice_value(inner)) for key, inner in value.items())
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_choice_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        return tuple(sorted(_freeze_choice_value(item) for item in value))
    return value


def _string_tokens(value: Any) -> Set[str]:
    if value is None:
        return {"", "—", "None", "none", "null"}
    text = str(value)
    tokens = {text}
    lowered = text.casefold()
    tokens.add(lowered)
    return tokens


def _iter_choice_values(value: Any) -> Iterable[Any]:
    if value is None:
        return [None]
    if isinstance(value, (list, tuple, set, frozenset)):
        return list(value)
    return [value]


def _extract_identifiers(value: Any) -> Iterable[Any]:
    if isinstance(value, Mapping):
        for key in _IDENTIFIER_KEYS:
            if key in value:
                yield value[key]
        return
    for key in _IDENTIFIER_KEYS:
        if hasattr(value, key):
            yield getattr(value, key)


def _register_choice_value(
    value: Any,
    *,
    selected_exact: Set[Any],
    selected_strings: Set[str],
) -> None:
    normalized = _freeze_choice_value(value)
    try:
        selected_exact.add(normalized)
    except TypeError:
        pass
    selected_strings.update(_string_tokens(value))
    for identifier in _extract_identifiers(value):
        normalized_identifier = _freeze_choice_value(identifier)
        try:
            selected_exact.add(normalized_identifier)
        except TypeError:
            pass
        selected_strings.update(_string_tokens(identifier))


def create_choices_matcher(
    state: ColumnFilterState,
) -> Optional[Callable[[Any, Any], bool]]:
    values = state._choices_values()
    if not values:
        return None

    selected_exact: Set[Any] = set()
    selected_strings: Set[str] = set()

    for item in values:
        _register_choice_value(
            item, selected_exact=selected_exact, selected_strings=selected_strings
        )

    if isinstance(state.meta, Mapping):
        display_values = state.meta.get("choices_display")
        if isinstance(display_values, Sequence):
            for display in display_values:
                selected_strings.update(_string_tokens(display))
        labels_map = state.meta.get("choices_labels")
        if isinstance(labels_map, Mapping):
            for display in labels_map.values():
                selected_strings.update(_string_tokens(display))

    def matches_single(value: Any) -> bool:
        normalized = _freeze_choice_value(value)
        try:
            if normalized in selected_exact:
                return True
        except TypeError:
            pass
        for identifier in _extract_identifiers(value):
            normalized_identifier = _freeze_choice_value(identifier)
            try:
                if normalized_identifier in selected_exact:
                    return True
            except TypeError:
                pass
            if _string_tokens(identifier) & selected_strings:
                return True
        if _string_tokens(value) & selected_strings:
            return True
        return False

    def matcher(raw: Any, display: Any) -> bool:
        for candidate in _iter_choice_values(raw):
            if matches_single(candidate):
                return True
        for candidate in _iter_choice_values(display):
            if matches_single(candidate):
                return True
        return False

    return matcher


class MultiFilterProxyModel(QSortFilterProxyModel):
    """Расширенная `QSortFilterProxyModel` с несколькими фильтрами.

    Позволяет задавать отдельный фильтр для каждой колонки.
    Поддерживаются текстовые значения, булевы поля, числовые значения и диапазоны дат.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._filters: Dict[int, Callable[[Any, Any], bool]] = {}
        self._filter_strings: Dict[int, str] = {}
        self._filter_states: Dict[int, ColumnFilterState] = {}

    def set_filter(
        self,
        column: int,
        state: ColumnFilterState | Mapping[str, Any] | str | None,
    ) -> None:
        """Устанавливает фильтр для указанной колонки.

        ``state`` может быть строкой, словарём (для восстановления из настроек)
        или экземпляром :class:`ColumnFilterState`.
        Пустое значение удаляет фильтр.
        """

        previous_state = self._filter_states.get(column)
        normalized = self._normalize_state(state)
        if normalized is None or normalized.is_empty():
            self._filters.pop(column, None)
            self._filter_states.pop(column, None)
            self._filter_strings.pop(column, None)
        else:
            matcher = self._create_matcher(normalized)
            if matcher is None:
                self._filters.pop(column, None)
                self._filter_states.pop(column, None)
                self._filter_strings.pop(column, None)
            else:
                self._filters[column] = matcher
                self._filter_states[column] = normalized
                display_text = normalized.display_text()
                if display_text:
                    self._filter_strings[column] = display_text
                else:
                    self._filter_strings.pop(column, None)
        if previous_state != self._filter_states.get(column):
            self.headerDataChanged.emit(Qt.Horizontal, column, column)
        self.invalidateFilter()

    # ------------------------------------------------------------------
    # QSortFilterProxyModel interface
    # ------------------------------------------------------------------
    def filterAcceptsRow(self, source_row: int, source_parent) -> bool:  # type: ignore[override]
        model = self.sourceModel()
        if not model:
            return True
        for column, matcher in self._filters.items():
            index = model.index(source_row, column, source_parent)
            raw_value = model.data(index, Qt.UserRole)
            display_role = self.filterRole()
            display_value = model.data(index, display_role)
            if display_value is None and display_role != Qt.DisplayRole:
                display_value = model.data(index, Qt.DisplayRole)
            if not matcher(raw_value, display_value):
                return False
        return True

    def headerData(self, section, orientation, role=Qt.DisplayRole):  # type: ignore[override]
        value = super().headerData(section, orientation, role)
        if orientation != Qt.Horizontal:
            return value
        if role == Qt.DisplayRole and section in self._filter_strings:
            base = "" if value is None else str(value)
            if base:
                return f"{base} ⏷"
            return "⏷"
        if role == Qt.ToolTipRole and section in self._filter_strings:
            base = value
            if not base:
                base = super().headerData(section, orientation, Qt.DisplayRole)
            filter_text = self._filter_strings.get(section, "")
            if base:
                return f"{base}\nФильтр: {filter_text}"
            return f"Фильтр: {filter_text}"
        return value

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _normalize_state(
        self,
        state: ColumnFilterState | Mapping[str, Any] | str | None,
    ) -> Optional[ColumnFilterState]:
        if state is None:
            return None
        if isinstance(state, ColumnFilterState):
            return state
        if isinstance(state, str):
            text = state.strip()
            if not text:
                return None
            return ColumnFilterState("text", text)
        normalized = ColumnFilterState.from_dict(state)
        if normalized is not None:
            return normalized
        type_value = state.get("type") if isinstance(state, Mapping) else None
        if type_value == "choices" and isinstance(state, Mapping):
            raw_display = state.get("display")
            display = raw_display if isinstance(raw_display, str) else None
            raw_meta = state.get("meta")
            meta = raw_meta if isinstance(raw_meta, dict) else None
            value = ColumnFilterState._restore_choices_value(
                state.get("value"),
                state.get("value_container"),
            )
            return ColumnFilterState("choices", value, display, meta)
        return None

    def _create_matcher(
        self, state: ColumnFilterState
    ) -> Optional[Callable[[Any, Any], bool]]:
        if state.type == "text":
            text = str(state.value or "").strip()
            if not text:
                return None
            options = (
                QRegularExpression.CaseInsensitiveOption
                if self.filterCaseSensitivity() == Qt.CaseInsensitive
                else QRegularExpression.NoPatternOption
            )
            esc = QRegularExpression.escape(text)
            pattern = f".*{esc}.*"
            regex = QRegularExpression(pattern, options)
            return lambda _raw, display: regex.match(
                "" if display is None else str(display)
            ).hasMatch()

        if state.type == "bool":
            desired = state.value
            if desired is None:
                return None
            bool_value = bool(desired)

            def matcher(raw: Any, _display: Any) -> bool:
                if raw is None:
                    return False
                if isinstance(raw, bool):
                    return raw is bool_value
                if isinstance(raw, (int, float)):
                    return bool(raw) is bool_value
                if isinstance(raw, str):
                    lowered = raw.lower()
                    if lowered in {"true", "1", "yes", "да"}:
                        return bool_value is True
                    if lowered in {"false", "0", "no", "нет"}:
                        return bool_value is False
                return False

            return matcher

        if state.type == "date_range" and isinstance(state.value, Mapping):
            start = self._parse_iso_date(state.value.get("from"))
            end = self._parse_iso_date(state.value.get("to"))
            if start is None and end is None:
                return None

            def matcher(raw: Any, _display: Any) -> bool:
                current = self._coerce_to_date(raw)
                if current is None:
                    return False
                if start and current < start:
                    return False
                if end and current > end:
                    return False
                return True

            return matcher

        if state.type == "number":
            meta = state.meta or {}
            value_type = meta.get("value_type")
            target = self._to_number(state.value, value_type)
            if target is None:
                return None

            def matcher(raw: Any, _display: Any) -> bool:
                current = self._to_number(raw, value_type)
                if current is None:
                    return False
                if value_type == "int":
                    return int(current) == int(target)
                return math.isclose(float(current), float(target), rel_tol=1e-9, abs_tol=1e-9)

            return matcher

        if state.type == "choices":
            return create_choices_matcher(state)

        # Для неизвестных типов используем текстовое сравнение
        text = str(state.value or "").strip()
        if not text:
            return None
        options = (
            QRegularExpression.CaseInsensitiveOption
            if self.filterCaseSensitivity() == Qt.CaseInsensitive
            else QRegularExpression.NoPatternOption
        )
        esc = QRegularExpression.escape(text)
        pattern = f".*{esc}.*"
        regex = QRegularExpression(pattern, options)
        return lambda _raw, display: regex.match(
            "" if display is None else str(display)
        ).hasMatch()

    @staticmethod
    def _parse_iso_date(value: Any) -> Optional[date]:
        if value in (None, ""):
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, QDate):
            return value.toPython()
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _coerce_to_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, QDate):
            return value.toPython()
        if isinstance(value, str):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _to_number(value: Any, value_type: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        if value_type == "int":
            try:
                return float(int(value))
            except (TypeError, ValueError):
                return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

