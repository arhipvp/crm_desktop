from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QTextEdit,
    QLineEdit,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QTextCursor
from pathlib import Path
import json as _json

from services.policies.ai_policy_service import (
    recognize_policy_interactive,
    AiPolicyError,
    _read_text,
    _get_prompt,
)
from ui.forms.import_policy_json_form import ImportPolicyJsonForm
from ui.common.message_boxes import show_error


class _Worker(QThread):
    progress = Signal(str, str)
    finished = Signal(dict, list, str)
    failed = Signal(str, list, str)

    def __init__(self, messages):
        super().__init__()
        self._messages = messages

    def run(self):
        def cb(role, part):
            self.progress.emit(role, part)

        try:
            data, transcript, messages = recognize_policy_interactive(
                "", messages=self._messages, progress_cb=cb
            )
            self.finished.emit(data, messages, transcript)
        except AiPolicyError as exc:
            self.failed.emit(str(exc), exc.messages, exc.transcript)
        except Exception as exc:  # pragma: no cover - network errors
            self.failed.emit(str(exc), self._messages, "")


class AiPolicyFilesDialog(QDialog):
    """Диалог для распознавания полиса из одного или нескольких файлов."""

    def __init__(self, parent=None, *, forced_client=None, forced_deal=None):
        super().__init__(parent)
        self.forced_client = forced_client
        self.forced_deal = forced_deal

        self.setWindowTitle("Распознавание полисов")
        self.setMinimumWidth(400)
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)

        self.label = QLabel("Перетащите файлы полисов сюда")
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.list_widget = QListWidget(self)
        layout.addWidget(self.list_widget)

        self.conv_edit = QTextEdit(self)
        self.conv_edit.setReadOnly(True)
        self.conv_edit.setPlaceholderText("Диалог с ИИ...")
        self.conv_edit.setMinimumHeight(120)
        layout.addWidget(self.conv_edit)

        self.input_edit = QLineEdit(self)
        self.input_edit.setPlaceholderText("Сообщение для ИИ...")
        self.input_edit.setVisible(False)
        layout.addWidget(self.input_edit)

        btns = QHBoxLayout()
        self.process_btn = QPushButton("Распознать", self)
        self.process_btn.clicked.connect(self.on_process)
        cancel_btn = QPushButton("Отмена", self)
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.process_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

        self.files: list[Path] = []
        self._messages: list[dict] = []
        self._worker: _Worker | None = None

    # ------------------------------------------------------------------
    def _append(self, role: str, text: str):
        if role == "assistant":
            cursor = self.conv_edit.textCursor()
            cursor.movePosition(QTextCursor.End)
            cursor.insertText(text)
            self.conv_edit.setTextCursor(cursor)
        else:
            self.conv_edit.append(f"{role}: {text}")

    def _start_worker(self):
        self._worker = _Worker(self._messages)
        self._worker.progress.connect(self._append)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    # ------------------------------------------------------------------
    def _on_finished(self, data, messages, transcript):
        self._worker = None
        self._messages = messages
        self.process_btn.setEnabled(True)
        self.input_edit.setVisible(False)
        self.process_btn.setText("Распознать")

        msg = QMessageBox(self)
        msg.setWindowTitle("Диалог с ИИ")
        if len(self.files) == 1:
            name = self.files[0].name
            msg.setText(
                f"Распознавание файла {name} завершено. Полный диалог см. в деталях."
            )
        else:
            msg.setText(
                "Распознавание файлов завершено. Полный диалог см. в деталях."
            )
        msg.setDetailedText(transcript)
        msg.exec()

        json_text = _json.dumps(data, ensure_ascii=False, indent=2)
        dlg = ImportPolicyJsonForm(
            parent=self,
            forced_client=self.forced_client,
            forced_deal=self.forced_deal,
            json_text=json_text,
        )
        if dlg.exec():
            policy = getattr(dlg, "imported_policy", None)
            if policy and policy.drive_folder_link:
                from services.folder_utils import move_file_to_folder

                for src in self.files:
                    move_file_to_folder(str(src), policy.drive_folder_link)
            self.accept()
        else:
            self.process_btn.setEnabled(True)

    def _on_failed(self, error, messages, transcript):
        self._worker = None
        self._messages = messages
        self.process_btn.setEnabled(True)
        self.input_edit.setVisible(True)
        self.process_btn.setText("Отправить")
        if error:
            QMessageBox.warning(self, "Ошибка", error)

    # ------------------------------------------------------------------
    def dragEnterEvent(self, event):  # noqa: D401 - Qt override
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: D401 - Qt override
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        for url in urls:
            path = Path(url.toLocalFile())
            if path not in self.files:
                self.files.append(path)
                self.list_widget.addItem(str(path))
        if urls:
            event.acceptProposedAction()

    # ------------------------------------------------------------------
    def on_process(self):
        if self._worker:
            text = self.input_edit.text().strip()
            if not text:
                return
            self.input_edit.clear()
            self._messages.append({"role": "user", "content": text})
            self._append("user", text)
            self.process_btn.setEnabled(False)
            self._start_worker()
            return

        if not self.files:
            QMessageBox.warning(self, "Ошибка", "Добавьте файлы.")
            return

        text = "\n".join(_read_text(str(p)) for p in self.files)
        self.conv_edit.clear()
        self._messages = [
            {"role": "system", "content": _get_prompt()},
            {"role": "user", "content": text},
        ]
        for m in self._messages:
            self._append(m["role"], m["content"])

        self.process_btn.setEnabled(False)
        self._start_worker()

