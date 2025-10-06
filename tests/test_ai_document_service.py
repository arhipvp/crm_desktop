from types import SimpleNamespace

import openai

from config import Settings
from services import ai_document_service


def _dummy_client(captured):
    def create(**kwargs):
        captured["messages"] = kwargs["messages"]
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Готово"))]
        )

    return SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )


def test_summarize_document_files_combines_text(tmp_path, monkeypatch):
    path1 = tmp_path / "first.txt"
    path2 = tmp_path / "second.txt"
    path1.write_text("Первый документ")
    path2.write_text("Второй документ")

    captured: dict = {}
    monkeypatch.setattr(openai, "OpenAI", lambda *a, **kw: _dummy_client(captured))
    monkeypatch.setattr(
        ai_document_service,
        "settings",
        Settings(openai_api_key="key", openai_model="gpt-4o"),
    )

    note, transcript = ai_document_service.summarize_document_files(
        [str(path1), str(path2)]
    )

    assert note == "Готово"
    user_message = next(m for m in captured["messages"] if m["role"] == "user")
    assert path1.name in user_message["content"]
    assert "Первый документ" in user_message["content"]
    assert path2.name in user_message["content"]
    assert "Второй документ" in user_message["content"]
    assert transcript.endswith("assistant: Готово")


def test_summarize_documents_interactive_empty(monkeypatch):
    called = False

    def fake_openai(*args, **kwargs):  # pragma: no cover - безопасность
        nonlocal called
        called = True
        return _dummy_client({})

    monkeypatch.setattr(openai, "OpenAI", fake_openai)
    monkeypatch.setattr(
        ai_document_service,
        "settings",
        Settings(openai_api_key="key", openai_model="gpt-4o"),
    )

    note, transcript = ai_document_service.summarize_documents_interactive("   ")

    assert note == ""
    assert transcript == ""
    assert called is False

