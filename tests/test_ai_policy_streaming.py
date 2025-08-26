import openai
from services.ai_policy_service import _chat


class DummyFunc:
    def __init__(self, arguments=None):
        self.arguments = arguments


class DummyCall:
    def __init__(self, func=None):
        self.function = func


class DummyDelta:
    def __init__(self, tool_calls=None):
        self.tool_calls = tool_calls


class DummyChoice:
    def __init__(self, delta=None):
        self.delta = delta


class DummyChunk:
    def __init__(self, delta=None):
        self.choices = [DummyChoice(delta)]


def fake_stream(**kwargs):
    return iter(
        [
            DummyChunk(DummyDelta(None)),
            DummyChunk(DummyDelta([])),
            DummyChunk(DummyDelta([DummyCall(DummyFunc('{"a'))])),
            DummyChunk(DummyDelta([DummyCall(DummyFunc('1"}'))])),
        ]
    )


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
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    monkeypatch.setattr(openai, "OpenAI", DummyClient)

    parts = []

    def progress(role, text):
        parts.append(text)

    messages = []
    result = _chat(messages, progress_cb=progress)

    assert result == '{"a1"}'
    assert parts == ['{"a', '1"}']
