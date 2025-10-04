from __future__ import annotations

from dataclasses import dataclass

import pytest

from ui.common.multi_filter_proxy import ColumnFilterState, create_choices_matcher


@dataclass
class _Item:
    id: int
    name: str


def _call_matcher(state: ColumnFilterState, raw, display):
    matcher = create_choices_matcher(state)
    assert matcher is not None
    return matcher(raw, display)


def test_choices_matcher_matches_identifiers():
    state = ColumnFilterState("choices", [42])
    item = _Item(id=42, name="Alpha")
    other = _Item(id=7, name="Beta")

    assert _call_matcher(state, item, None)
    assert not _call_matcher(state, other, None)


def test_choices_matcher_handles_mapping_values():
    state = ColumnFilterState("choices", [{"id": 5, "name": "Alpha"}])
    same_id = {"id": 5, "name": "Beta"}
    different_id = {"id": 6, "name": "Alpha"}

    assert _call_matcher(state, same_id, None)
    assert not _call_matcher(state, different_id, None)


@pytest.mark.parametrize(
    "display_value",
    ["—", "пусто", "ПУСТО"],
)
def test_choices_matcher_accepts_none_and_labels(display_value: str):
    state = ColumnFilterState(
        "choices",
        [None],
        meta={"choices_labels": {None: "Пусто"}},
    )

    assert _call_matcher(state, None, None)
    assert _call_matcher(state, "", display_value)
    assert not _call_matcher(state, "something", "другое")
