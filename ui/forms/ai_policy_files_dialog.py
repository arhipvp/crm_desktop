import json as _json
import logging
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from services.policies.ai_policy_service import (
    recognize_policy_interactive,
    AiPolicyError,
    _read_text,
    _get_prompt,
)
from ui.forms.import_policy_json_form import ImportPolicyJsonForm
from ui.common.message_boxes import show_error


logger = logging.getLogger(__name__)


class _Worker(QThread):
    progress = Signal(str, str)
    finished = Signal(dict, list, str)
    failed = Signal(str, list, str)

    def __init__(self, messages):
        super().__init__()
        self._messages = messages

    def run(self):
        def cb(role, part):
            if self.isInterruptionRequested():
                raise InterruptedError("Распознавание отменено пользователем")
            self.progress.emit(role, part)

        def cancel_cb():
            return self.isInterruptionRequested()

        try:
            if self.isInterruptionRequested():
                raise InterruptedError("Распознавание отменено пользователем")
            data, transcript, messages = recognize_policy_interactive(
                "",
                messages=self._messages,
                progress_cb=cb,
                cancel_cb=cancel_cb,
            )
            self.finished.emit(data, messages, transcript)
        except InterruptedError:
            logger.info("Распознавание полиса отменено пользователем")
        except AiPolicyError as exc:
            self.failed.emit(str(exc), exc.messages, exc.transcript)
        except Exception as exc:  # pragma: no cover - network errors
            self.failed.emit(str(exc), self._messages, "")


class AiPolicyFilesDialog(QDialog):
    """Диалог для распознавания полиса из одного или нескольких файлов."""

    def __init__(
        self,
        parent=None,
        *,
        forced_client=None,
        forced_deal=None,
        initial_files: Iterable[Path] | None = None,
    ):
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
        self.remove_btn = QPushButton("Удалить выбранные", self)
        self.remove_btn.clicked.connect(self.on_remove_selected)
        self.process_btn = QPushButton("Распознать", self)
        self.process_btn.clicked.connect(self.on_process)
        cancel_btn = QPushButton("Отмена", self)
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.remove_btn)
        btns.addWidget(self.process_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

        self.files: list[Path] = []
        self._messages: list[dict] = []
        self._worker: _Worker | None = None

        self._delete_shortcuts: list[QShortcut] = []
        for key in (Qt.Key_Delete, Qt.Key_Backspace):
            shortcut = QShortcut(QKeySequence(key), self.list_widget)
            shortcut.activated.connect(self.on_remove_selected)
            self._delete_shortcuts.append(shortcut)

        if initial_files:
            self._add_files(initial_files)

        self._update_process_button_state()

    # ------------------------------------------------------------------
    def _append(self, role: str, text: str):
        cursor = self.conv_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        if role == "assistant":
            cursor.insertText(text)
        else:
            cursor.insertText(f"{role}:\n{text}\n")
        self.conv_edit.setTextCursor(cursor)

    def _start_worker(self):
        if self._worker:
            if self._worker.isRunning():
                return
            self._cleanup_worker()

        self._worker = _Worker(self._messages)
        self._worker.progress.connect(self._append)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.start()

    def _cleanup_worker(self, *, wait: bool = False):
        if not self._worker:
            return

        worker = self._worker
        if wait and worker.isRunning():
            worker.requestInterruption()
            worker.quit()
            if not worker.wait(5000):
                logger.warning("Поток распознавания не завершился вовремя, завершаем принудительно")
                worker.terminate()
                if not worker.wait(2000):
                    logger.error("Не удалось завершить поток распознавания")

        if not worker.isRunning():
            worker.deleteLater()
            self._worker = None

    def on_remove_selected(self):
        selected_rows = sorted(
            {index.row() for index in self.list_widget.selectedIndexes()}, reverse=True
        )
        if not selected_rows:
            return

        for row in selected_rows:
            if 0 <= row < self.list_widget.count():
                self.list_widget.takeItem(row)
                if 0 <= row < len(self.files):
                    del self.files[row]

        self._update_process_button_state()

    # ------------------------------------------------------------------
    def _on_finished(self, data, messages, transcript):
        self._cleanup_worker()
        self._messages = messages
        self.process_btn.setEnabled(True)
        self.input_edit.setVisible(False)
        self.process_btn.setText("Распознать")
        self._update_process_button_state()

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
        self._cleanup_worker()
        self._messages = messages
        self.process_btn.setEnabled(True)
        self.input_edit.setVisible(True)
        self.process_btn.setText("Отправить")
        self._update_process_button_state()
        if error:
            QMessageBox.warning(self, "Ошибка", error)

    # ------------------------------------------------------------------
    def dragEnterEvent(self, event):  # noqa: D401 - Qt override
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: D401 - Qt override
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        added = False
        if urls:
            added = self._add_files(Path(url.toLocalFile()) for url in urls)
        if added:
            event.acceptProposedAction()
        self._update_process_button_state()

    def _add_files(self, paths: Iterable[Path]) -> bool:
        added = False
        existing = {p for p in self.files}
        rejected: list[str] = []

        for original in paths:
            try:
                resolved = Path(original).resolve(strict=True)
            except (FileNotFoundError, OSError):
                rejected.append(f"{original}: файл не найден")
                continue

            try:
                if not resolved.is_file():
                    rejected.append(f"{resolved}: можно добавить только файлы")
                    continue

                size = resolved.stat().st_size
            except OSError:
                rejected.append(f"{resolved}: не удалось прочитать файл")
                continue

            if size == 0:
                rejected.append(f"{resolved}: файл пустой")
                continue

            if resolved in existing:
                rejected.append(f"{resolved}: файл уже добавлен")
                continue

            existing.add(resolved)
            self.files.append(resolved)
            self.list_widget.addItem(str(resolved))
            added = True

        if rejected:
            QMessageBox.information(
                self,
                "Файл не добавлен",
                "\n".join(rejected),
            )

        return added

    def _update_process_button_state(self) -> None:
        if self._worker and self._worker.isRunning():
            self.process_btn.setEnabled(False)
            return

        if self.process_btn.text() == "Отправить":
            self.process_btn.setEnabled(True)
            return

        self.process_btn.setEnabled(bool(self.files))

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

        blocks = [
            f"===== {path.name} =====\n{_read_text(str(path))}"
            for path in self.files
        ]
        text = "\n\n".join(blocks)
        self.conv_edit.clear()
        self._messages = [
            {"role": "system", "content": _get_prompt()},
            {"role": "user", "content": text},
        ]
        for m in self._messages:
            self._append(m["role"], m["content"])

        self.process_btn.setEnabled(False)
        self._start_worker()

    def closeEvent(self, event):  # noqa: D401 - Qt override
        self._cleanup_worker(wait=True)
        super().closeEvent(event)

