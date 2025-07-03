import pytest
from services.ai_policy_service import _extract_json_from_answer


def test_extract_json_with_trailing_text():
    answer = '{"a": 1}\nSome text after'
    assert _extract_json_from_answer(answer) == {"a": 1}


def test_extract_json_multiple_objects():
    answer = '{"a":1}{"b":2}'
    assert _extract_json_from_answer(answer) == {"a": 1}


def test_extract_json_no_json_raises():
    with pytest.raises(ValueError):
        _extract_json_from_answer('no json here')
