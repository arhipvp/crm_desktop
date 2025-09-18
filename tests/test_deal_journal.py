from datetime import date

import pytest

from database.models import Client, Deal
from services import deal_journal


def test_parse_journal_splits_active_and_archive():
    text = (
        "[01.02.2024 10:00]: Новый контакт\n"
        "[31.01.2024 09:00] — Задача закрыта\n"
        "\n\n===ARCHIVE===\n\n"
        "[15.12.2023 08:30]: Старый комментарий\n"
    )

    active, archived = deal_journal.parse_journal(text)

    assert [entry.header for entry in active] == [
        "[01.02.2024 10:00]: Новый контакт",
        "[31.01.2024 09:00] — Задача закрыта",
    ]
    assert len(archived) == 1
    assert archived[0].header == "[15.12.2023 08:30]: Старый комментарий"

    rebuilt = deal_journal.dump_journal(active, archived)
    assert rebuilt == text


def test_entry_id_stable_after_dump():
    text = "[01.02.2024 10:00]: Привет мир\n"

    active, archived = deal_journal.parse_journal(text)
    assert len(active) == 1
    entry_id = active[0].entry_id

    rebuilt = deal_journal.dump_journal(active, archived)
    active2, archived2 = deal_journal.parse_journal(rebuilt)
    assert len(active2) == 1
    assert active2[0].entry_id == entry_id
    assert not archived and not archived2


@pytest.mark.usefixtures("in_memory_db")
def test_append_and_archive_operations_preserve_format(monkeypatch):
    client = Client.create(name="Тестовый клиент")
    deal = Deal.create(
        client=client,
        description="Тестовая сделка",
        start_date=date.today(),
        calculations="[01.01.2023 09:00]: Старый комментарий\n",
    )

    monkeypatch.setattr(deal_journal, "now_str", lambda: "02.02.2024 12:00")

    new_entry = deal_journal.append_entry(deal, "Новая заметка")

    assert new_entry.header.startswith("[02.02.2024 12:00]")
    assert deal.calculations.startswith("[02.02.2024 12:00]: Новая заметка")

    active, archived = deal_journal.load_entries(deal)
    assert len(active) == 2

    old_entry_id = next(e.entry_id for e in active if "Старый комментарий" in e.raw)

    archived_entry = deal_journal.archive_entry(deal, old_entry_id)
    assert archived_entry is not None

    active_after, archived_after = deal_journal.load_entries(deal)
    assert len(active_after) == 1
    assert archived_after and archived_after[0].entry_id == old_entry_id

    assert "===ARCHIVE===" in deal.calculations
    archive_section = deal.calculations.split("===ARCHIVE===", 1)[1]
    assert "Старый комментарий" in archive_section

    # round-trip compatibility with existing text
    rebuilt = deal_journal.dump_journal(*deal_journal.parse_journal(deal.calculations))
    assert rebuilt == deal.calculations
