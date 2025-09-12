import openai
from types import SimpleNamespace

from services.policies import ai_policy_service
from services.policies.ai_policy_service import _chat
from config import Settings


def generate_streaming_chunks():
    def make_chunk(tool_calls):
        delta = SimpleNamespace(tool_calls=tool_calls)
        choice = SimpleNamespace(delta=delta)
        return SimpleNamespace(choices=[choice])

    return [
        make_chunk(None),
        make_chunk([]),
        make_chunk(
            [SimpleNamespace(function=SimpleNamespace(arguments='{"a'))]
        ),
        make_chunk(
            [SimpleNamespace(function=SimpleNamespace(arguments='1"}'))]
        ),
    ]


def fake_stream(**kwargs):
    return iter(generate_streaming_chunks())


class DummyCompletions:
    def create(self, **kwargs):
        return fake_stream()


class DummyChat:
    def __init__(self):
        self.completions = DummyCompletions()


class DummyClient:
    def __init__(self, *a, **kw):
        self.chat = DummyChat()


def test_chat_streaming_no_attribute_error(monkeypatch):
    monkeypatch.setattr(openai, "OpenAI", DummyClient)
    monkeypatch.setattr(
        ai_policy_service, "settings", Settings(openai_api_key="key")
    )

    parts = []

    def progress(role, text):
        parts.append(text)

    messages = []
    result = _chat(messages, progress_cb=progress)

    assert result == '{"a1"}'
    assert parts == ['{"a', '1"}']
