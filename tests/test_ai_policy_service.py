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

    result, convs = ai.process_policy_files_with_ai([str(file_path)])

    assert result == [{"a": 1}]
    assert len(convs) == 1
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
        _, convs = ai.process_policy_files_with_ai([str(file_path)])

    assert any("OpenAI conversation for" in r.message for r in caplog.records)
    assert len(convs) == 1


def test_process_policy_text_with_ai_retry_success(monkeypatch):
    client = DummyClient(["oops", '{"a":1}'])
    monkeypatch.setattr(ai.openai, "OpenAI", lambda api_key=None, base_url=None: client)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    result, conv = ai.process_policy_text_with_ai("dummy")

    assert result == {"a": 1}
    assert conv
    assert len(client.calls) == 2


def test_process_policy_text_with_ai_retry_fail(monkeypatch):
    client = DummyClient(["bad1", "bad2", "bad3"])
    monkeypatch.setattr(ai.openai, "OpenAI", lambda api_key=None, base_url=None: client)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    with pytest.raises(ValueError) as exc:
        ai.process_policy_text_with_ai("dummy")

    msg = str(exc.value)
    assert "bad1" in msg and "bad2" in msg and "bad3" in msg


def test_process_policy_text_logs_chat(monkeypatch, caplog):
    client = DummyClient(['{"a":1}'])
    monkeypatch.setattr(ai.openai, "OpenAI", lambda api_key=None, base_url=None: client)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    with caplog.at_level(logging.INFO):
        _, conv = ai.process_policy_text_with_ai("dummy")

    assert any("OpenAI conversation for" in r.message for r in caplog.records)
    assert conv


def test_process_policy_bundle_with_ai_combines(monkeypatch, tmp_path):
    file1 = tmp_path / "a.txt"
    file2 = tmp_path / "b.txt"
    file1.write_text("foo")
    file2.write_text("bar")
    client = DummyClient(['{"x":1}'])
    monkeypatch.setattr(ai.openai, "OpenAI", lambda api_key=None, base_url=None: client)
    monkeypatch.setenv("OPENAI_API_KEY", "x")

    result, conv = ai.process_policy_bundle_with_ai([str(file1), str(file2)])

    assert result == {"x": 1}
    assert conv
    assert len(client.calls) == 1
    sent = client.calls[0][1]["content"]
    assert "foo" in sent and "bar" in sent
