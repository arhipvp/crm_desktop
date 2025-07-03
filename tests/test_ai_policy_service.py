import logging
import pytest
from types import SimpleNamespace

import services.ai_policy_service as ai


def test_extract_json_with_trailing_text():
    answer = '{"a": 1}\nSome text after'
    assert ai._extract_json_from_answer(answer) == {"a": 1}


def test_extract_json_multiple_objects():
    answer = '{"a":1}{"b":2}'
    assert ai._extract_json_from_answer(answer) == {"a": 1}


def test_extract_json_no_json_raises():
    with pytest.raises(ValueError):
        ai._extract_json_from_answer('no json here')


class DummyClient:
    def __init__(self, answers):
        self._answers = answers
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))
        self.calls = []
        self.i = 0

    def create(self, model=None, messages=None, temperature=None):
        self.calls.append(messages)
        answer = self._answers[self.i]
        self.i += 1
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=answer))])


def test_process_policy_files_with_ai_retry_success(monkeypatch, tmp_path):
    file_path = tmp_path / "p.txt"
    file_path.write_text("dummy")
    client = DummyClient(["oops", '{"a":1}'])
    monkeypatch.setattr(ai.openai, "OpenAI", lambda api_key=None, base_url=None: client)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    result = ai.process_policy_files_with_ai([str(file_path)])

    assert result == [{"a": 1}]
    assert len(client.calls) == 2


def test_process_policy_files_with_ai_retry_fail(monkeypatch, tmp_path):
    file_path = tmp_path / "p.txt"
    file_path.write_text("dummy")
    client = DummyClient(["bad1", "bad2", "bad3"])
    monkeypatch.setattr(ai.openai, "OpenAI", lambda api_key=None, base_url=None: client)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    with pytest.raises(ValueError) as exc:
        ai.process_policy_files_with_ai([str(file_path)])

    msg = str(exc.value)
    assert "bad1" in msg and "bad2" in msg and "bad3" in msg


def test_process_policy_files_logs_chat(monkeypatch, tmp_path, caplog):
    file_path = tmp_path / "p.txt"
    file_path.write_text("dummy")
    client = DummyClient(['{"a":1}'])
    monkeypatch.setattr(ai.openai, "OpenAI", lambda api_key=None, base_url=None: client)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    with caplog.at_level(logging.INFO):
        ai.process_policy_files_with_ai([str(file_path)])

    assert any("OpenAI conversation for" in r.message for r in caplog.records)
