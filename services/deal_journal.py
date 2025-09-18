from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from database.db import db
from database.models import Deal
from utils.time_utils import now_str

ARCHIVE_MARKER = "\n\n===ARCHIVE===\n\n"
_ENTRY_START_RE = re.compile(r"^\[\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}]", re.MULTILINE)


@dataclass(frozen=True)
class JournalEntry:
    entry_id: str
    raw: str
    header: str
    body: str


def parse_journal(text: str | None) -> tuple[list[JournalEntry], list[JournalEntry]]:
    if not text:
        return [], []

    active_text, archived_text = _split_sections(text)
    return _parse_section(active_text), _parse_section(archived_text)


def dump_journal(active: Sequence[JournalEntry], archived: Sequence[JournalEntry]) -> str:
    active_text = "".join(entry.raw for entry in active)
    archived_text = "".join(entry.raw for entry in archived)
    if archived:
        return f"{active_text}{ARCHIVE_MARKER}{archived_text}"
    return active_text


def load_entries(deal: Deal) -> tuple[list[JournalEntry], list[JournalEntry]]:
    return parse_journal(deal.calculations or "")


def append_entry(deal: Deal, body: str) -> JournalEntry:
    if not body:
        raise ValueError("Текст заметки не может быть пустым")

    text = body.strip("\n")
    if not _ENTRY_START_RE.match(text):
        timestamp = now_str()
        lines = text.splitlines()
        header = lines[0] if lines else ""
        remainder = "\n".join(lines[1:]) if len(lines) > 1 else ""
        text = f"[{timestamp}]: {header}".rstrip()
        if remainder:
            text = f"{text}\n{remainder}"
    if not text.endswith("\n"):
        text = f"{text}\n"

    active, archived = load_entries(deal)
    entry = _entry_from_raw(text)
    active.insert(0, entry)
    new_text = dump_journal(active, archived)

    with db.atomic():
        deal.calculations = new_text
        deal.save(only=[Deal.calculations])
    return entry


def archive_entry(deal: Deal, entry_id: str) -> JournalEntry | None:
    active, archived = load_entries(deal)
    for idx, entry in enumerate(active):
        if entry.entry_id == entry_id:
            archived_entry = active.pop(idx)
            archived.insert(0, archived_entry)
            new_text = dump_journal(active, archived)
            with db.atomic():
                deal.calculations = new_text
                deal.save(only=[Deal.calculations])
            return archived_entry
    return None


def format_for_display(text: str | None, *, active_only: bool = False) -> str:
    active, archived = parse_journal(text)
    entries: Iterable[JournalEntry]
    if active_only:
        entries = active
    else:
        entries = [*active, *_separator_entry(active, archived), *archived]
    rendered = "".join(entry.raw for entry in entries)
    return rendered.strip()


def _split_sections(text: str) -> tuple[str, str]:
    if ARCHIVE_MARKER in text:
        active_text, archived_text = text.split(ARCHIVE_MARKER, 1)
        return active_text, archived_text
    return text, ""


def _parse_section(section: str) -> list[JournalEntry]:
    if not section:
        return []

    matches = list(_ENTRY_START_RE.finditer(section))
    if not matches:
        return [_entry_from_raw(section)]

    entries: list[JournalEntry] = []
    prefix = section[: matches[0].start()]
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(section)
        raw = section[start:end]
        if idx == 0 and prefix:
            raw = f"{prefix}{raw}"
        entries.append(_entry_from_raw(raw))
    return entries


def _entry_from_raw(raw: str) -> JournalEntry:
    entry_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
    stripped = raw.rstrip("\n")
    lines = stripped.splitlines()
    header = lines[0] if lines else ""
    body = "\n".join(lines[1:]) if len(lines) > 1 else ""
    return JournalEntry(entry_id=entry_id, raw=raw, header=header, body=body)


def _separator_entry(active: Sequence[JournalEntry], archived: Sequence[JournalEntry]) -> list[JournalEntry]:
    if active and archived:
        raw = "\n\n--- Архив ---\n\n"
        entry_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:8]
        return [JournalEntry(entry_id=entry_id, raw=raw, header="--- Архив ---", body="")]
    return []
