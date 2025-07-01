import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path(os.path.expanduser("~")) / ".crm_desktop" / "ui_settings.json"


def _load_data() -> dict:
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:  # pragma: no cover - logging only
            logger.exception("Failed to load settings: %s", e)
    return {}


def _save_data(data: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:  # pragma: no cover - logging only
        logger.exception("Failed to save settings: %s", e)


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
