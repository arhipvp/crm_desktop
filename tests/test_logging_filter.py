import logging

from utils.logging_config import PeeweeFilter


def _record(msg: str, sql: str | None = None) -> logging.LogRecord:
    record = logging.LogRecord("peewee", logging.DEBUG, "", 0, msg, None, None)
    if sql is not None:
        record.sql = sql
    return record


def test_filter_excludes_select_queries():
    filt = PeeweeFilter()

    record_msg = _record("SELECT * FROM table")
    record_sql = _record("ignored", sql="SELECT * FROM table")

    assert not filt.filter(record_msg)
    assert not filt.filter(record_sql)


def test_filter_keeps_other_queries():
    filt = PeeweeFilter()

    for query in ["INSERT INTO t VALUES (1)", "UPDATE t SET a=1"]:
        assert filt.filter(_record(query))
        assert filt.filter(_record("ignored", sql=query))

