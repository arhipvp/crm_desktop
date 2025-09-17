"""Утилитарные тесты. Добавляйте новые тесты утилит сюда."""

import logging

from config import Settings
from utils.logging_config import PeeweeFilter, setup_logging


def _record(msg: str, sql: str | None = None) -> logging.LogRecord:
    record = logging.LogRecord("peewee", logging.DEBUG, "", 0, msg, None, None)
    if sql is not None:
        record.sql = sql
    return record


def test_filter_excludes_select_queries():
    filt = PeeweeFilter()

    record_msg = _record("SELECT * FROM table")
    record_sql = _record("ignored", sql="SELECT * FROM table")
    record_msg_ws = _record("   SELECT * FROM table")
    record_sql_ws = _record("ignored", sql="   SELECT * FROM table")

    assert not filt.filter(record_msg)
    assert not filt.filter(record_sql)
    assert not filt.filter(record_msg_ws)
    assert not filt.filter(record_sql_ws)


def test_filter_keeps_other_queries():
    filt = PeeweeFilter()

    for query in ["INSERT INTO t VALUES (1)", "UPDATE t SET a=1"]:
        assert filt.filter(_record(query))
        assert filt.filter(_record(f"   {query}"))
        assert filt.filter(_record("ignored", sql=query))
        assert filt.filter(_record("ignored", sql=f"   {query}"))


def test_setup_logging_restores_select_queries(tmp_path):
    settings_off = Settings(log_dir=str(tmp_path), log_level="INFO", detailed_logging=False)
    setup_logging(settings_off)

    peewee_logger = logging.getLogger("peewee")
    assert any(isinstance(filt, PeeweeFilter) for filt in peewee_logger.filters)

    class CollectHandler(logging.Handler):
        def __init__(self) -> None:
            super().__init__(level=logging.DEBUG)
            self.messages: list[str] = []

        def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - trivial
            self.messages.append(record.getMessage())

    collect_handler = CollectHandler()
    peewee_logger.addHandler(collect_handler)
    peewee_logger.setLevel(logging.DEBUG)

    try:
        peewee_logger.debug("SELECT 1")
        assert "SELECT 1" not in collect_handler.messages

        settings_on = Settings(log_dir=str(tmp_path), log_level="INFO", detailed_logging=True)
        setup_logging(settings_on)

        assert not any(isinstance(filt, PeeweeFilter) for filt in peewee_logger.filters)

        collect_handler.messages.clear()
        peewee_logger.debug("SELECT 1")
        assert "SELECT 1" in collect_handler.messages
    finally:
        peewee_logger.removeHandler(collect_handler)
