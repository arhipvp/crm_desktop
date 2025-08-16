import os
import asyncio
from types import SimpleNamespace
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("TG_BOT_TOKEN", "test")

import telegram_bot.bot as bot


class DummyDownload:
    def __init__(self):
        self.path = None

    async def download_to_drive(self, path: str):
        self.path = path
        Path(path).write_bytes(b"data")


class DummyFile:
    def __init__(self, file_name: str | None, file_size: int):
        self.file_name = file_name
        self.file_size = file_size
        self.download = DummyDownload()

    def get_file(self):
        return self.download


class DummyMessage:
    def __init__(self, document=None, photo=None, reply_to_message=None):
        self.document = document
        self.photo = photo
        self.reply_to_message = reply_to_message
        self.chat_id = 123
        self.replies: list[str] = []

    async def reply_text(self, text: str):
        self.replies.append(text)


def _run(msg, tmp_path, monkeypatch):
    update = SimpleNamespace(message=msg)
    deal = SimpleNamespace(drive_folder_path=str(tmp_path))
    monkeypatch.setattr(bot.ts, "get_deal_by_id", lambda _id: deal)
    asyncio.run(bot.h_file(update, None))


def test_file_upload_success(tmp_path, monkeypatch):
    file = DummyFile("doc.pdf", 1024)
    reply = SimpleNamespace(text_html="Сделка #1")
    msg = DummyMessage(document=file, reply_to_message=reply)

    _run(msg, tmp_path, monkeypatch)

    assert file.download.path is not None
    assert any(tmp_path.iterdir())
    assert msg.replies == ["📂 Файл сохранён в папке сделки ✔️"]


def test_file_upload_too_large(tmp_path, monkeypatch):
    file = DummyFile("doc.pdf", bot.MAX_FILE_SIZE + 1)
    reply = SimpleNamespace(text_html="Сделка #1")
    msg = DummyMessage(document=file, reply_to_message=reply)

    _run(msg, tmp_path, monkeypatch)

    assert file.download.path is None
    assert msg.replies == ["⚠️ Файл слишком большой."]
    assert not any(tmp_path.iterdir())


def test_file_upload_bad_extension(tmp_path, monkeypatch):
    file = DummyFile("bad.exe", 1024)
    reply = SimpleNamespace(text_html="Сделка #1")
    msg = DummyMessage(document=file, reply_to_message=reply)

    _run(msg, tmp_path, monkeypatch)

    assert file.download.path is None
    assert msg.replies == ["⚠️ Недопустимый тип файла."]
    assert not any(tmp_path.iterdir())
