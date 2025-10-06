import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from ui.forms.ai_document_files_dialog import AiDocumentFilesDialog


@pytest.mark.usefixtures("qapp")
def test_ai_document_files_dialog_fills_note(tmp_path, monkeypatch):
    file_path = tmp_path / "doc.txt"
    file_path.write_text("hello")

    note_text = "Краткий итог"
    transcript_text = "assistant: ответ"

    monkeypatch.setattr(
        "services.ai_document_service.summarize_document_files",
        lambda paths: (note_text, transcript_text),
    )
    monkeypatch.setattr(
        "services.ai_document_service.summarize_documents_interactive",
        lambda text, **kwargs: (note_text, transcript_text),
    )
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: 0)
    monkeypatch.setattr(QMessageBox, "warning", lambda *a, **k: 0)
    monkeypatch.setattr(QMessageBox, "exec", lambda self: QMessageBox.Accepted)

    class DummyWorker(QObject):
        progress = Signal(str, str)
        finished = Signal(str, str, str, str)
        failed = Signal(str)

        def __init__(self, files):  # noqa: D401 - тестовая заглушка
            super().__init__()
            self._running = False
            self.files = list(files)

        def start(self):
            self._running = True
            self.progress.emit("assistant", "stub")
            self.finished.emit(note_text, transcript_text, "### doc\nhello", "doc.txt")
            self._running = False

        def isRunning(self):
            return self._running

        def requestInterruption(self):
            self._running = False

        def quit(self):
            self._running = False

        def wait(self, *_):
            return True

        def terminate(self):
            self._running = False

        def deleteLater(self):
            pass

    monkeypatch.setattr(AiDocumentFilesDialog, "INITIAL_WORKER_CLS", DummyWorker)

    dialog = AiDocumentFilesDialog(initial_files=[file_path])
    try:
        dialog.on_process()
        assert dialog.note_edit.toPlainText() == note_text
        assert dialog.get_note() == note_text
    finally:
        dialog.deleteLater()
