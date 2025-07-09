from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
    QLineEdit,
)
from PySide6.QtCore import QThread, Signal
import json

from services.ai_policy_service import (
    recognize_policy_interactive,
    AiPolicyError,
    _get_prompt,
)
from ui.forms.import_policy_json_form import ImportPolicyJsonForm


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


class AiPolicyTextDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        forced_client=None,
        forced_deal=None,
        file_path: str | None = None,
    ):
        super().__init__(parent)
        self.forced_client = forced_client
        self.forced_deal = forced_deal
        self.file_path = file_path
        self.setWindowTitle("Распознавание полиса из текста")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        self.setAcceptDrops(True)

        self.file_edit = QLineEdit(self)
        self.file_edit.setPlaceholderText("Перетащите файл полиса сюда")
        self.file_edit.setReadOnly(True)
        if self.file_path:
            self.file_edit.setText(self.file_path)
        layout.addWidget(self.file_edit)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlaceholderText("Вставьте текст полиса...")
        layout.addWidget(self.text_edit)

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

        self._messages = []
        self._worker = None

    # ------------------------------------------------------------------
    def _append(self, role: str, text: str):
        if role == "assistant":
            cursor = self.conv_edit.textCursor()
            cursor.movePosition(cursor.End)
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
    def dragEnterEvent(self, event):  # noqa: D401 - Qt override
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: D401 - Qt override
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        if urls:
            self.file_path = urls[0].toLocalFile()
            self.file_edit.setText(self.file_path)
            event.acceptProposedAction()

    # ------------------------------------------------------------------
    def on_process(self):
        if self._worker:
            # отправка дополнительного сообщения
            text = self.input_edit.text().strip()
            if not text:
                return
            self.input_edit.clear()
            self._messages.append({"role": "user", "content": text})
            self._append("user", text)
            self.process_btn.setEnabled(False)
            self._start_worker()
            return

        if self.file_path:
            from services.ai_policy_service import _read_text

            text = _read_text(self.file_path)
        else:
            text = self.text_edit.toPlainText().strip()
            if not text:
                QMessageBox.warning(
                    self, "Ошибка", "Вставьте текст полиса или выберите файл."
                )
                return

        self.conv_edit.clear()
        self._messages = [
            {"role": "system", "content": _get_prompt()},
            {"role": "user", "content": text},
        ]
        for m in self._messages:
            self._append(m["role"], m["content"])

        self.process_btn.setEnabled(False)
        self._start_worker()

    # ------------------------------------------------------------------
    def _on_finished(self, data, messages, transcript):
        self._worker = None
        self._messages = messages
        self.process_btn.setEnabled(True)
        self.input_edit.setVisible(False)
        self.process_btn.setText("Распознать")

        msg = QMessageBox(self)
        msg.setWindowTitle("Диалог с ИИ")
        msg.setText("Распознавание выполнено. Полный диалог см. в деталях.")
        msg.setDetailedText(transcript)
        msg.exec()

        json_text = json.dumps(data, ensure_ascii=False, indent=2)
        form = ImportPolicyJsonForm(
            parent=self,
            forced_client=self.forced_client,
            forced_deal=self.forced_deal,
            json_text=json_text,
        )
        if form.exec():
            policy = getattr(form, "imported_policy", None)
            if policy and self.file_path:
                from services.folder_utils import move_file_to_folder, open_folder

                dest = policy.drive_folder_link or policy.drive_folder_path
                if dest:
                    move_file_to_folder(self.file_path, dest)
                    open_folder(dest, parent=self)
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
