import copy
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path.home() / ".crm_desktop" / "ui_settings.json"
_CACHE: dict | None = None


def _load_data() -> dict:
    global _CACHE
    if _CACHE is None:
        if SETTINGS_PATH.exists():
            try:
                _CACHE = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            except Exception as e:  # pragma: no cover - logging only
                logger.exception("Не удалось загрузить настройки: %s", e)
                _CACHE = {}
        else:
            _CACHE = {}
    return copy.deepcopy(_CACHE)


def _save_data(data: dict) -> None:
    global _CACHE
    _CACHE = copy.deepcopy(data)
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        SETTINGS_PATH.write_text(
            json.dumps(_CACHE, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:  # pragma: no cover - logging only
        logger.exception("Не удалось сохранить настройки: %s", e)


def get_table_settings(name: str) -> dict:
    data = _load_data()
    return data.get("tables", {}).get(name, {})


def set_table_settings(name: str, settings: dict) -> None:
    data = _load_data()
    tables = data.setdefault("tables", {})
    tables[name] = settings
    _save_data(data)


def get_table_filters(name: str) -> dict:
    """Возвращает сохранённые фильтры для таблицы."""
    data = _load_data()
    return data.get("table_filters", {}).get(name, {})


def set_table_filters(name: str, filters: dict) -> None:
    """Сохраняет фильтры таблицы."""
    data = _load_data()
    table_filters = data.setdefault("table_filters", {})
    table_filters[name] = filters
    _save_data(data)


def get_app_settings() -> dict:
    """Возвращает общие настройки приложения."""
    data = _load_data()
    return data.get("app", {})


def set_app_settings(settings: dict) -> None:
    """Сохраняет общие настройки приложения."""
    data = _load_data()
    data["app"] = settings
    _save_data(data)


def get_window_settings(name: str) -> dict:
    """Возвращает сохранённые настройки окна."""
    data = _load_data()
    return data.get("windows", {}).get(name, {})


def set_window_settings(name: str, settings: dict) -> None:
    """Сохраняет настройки окна."""
    data = _load_data()
    windows = data.setdefault("windows", {})
    windows[name] = settings
    _save_data(data)
