import base64
import logging
from pathlib import Path
from typing import Iterable, Sequence

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QLineEdit,
    QProgressDialog,
)

from services.ai_document_service import (
    summarize_document_files,
    summarize_documents_interactive,
)
from services.policies.ai_policy_service import _read_text
from ui import settings as ui_settings


logger = logging.getLogger(__name__)


class _InitialWorker(QThread):
    progress = Signal(str, str)
    finished = Signal(str, str, str, str)
    failed = Signal(str)

    def __init__(self, files: Sequence[Path]):
        super().__init__()
        self._files = list(files)

    def run(self):
        try:
            if self.isInterruptionRequested():
                return

            label = ", ".join(path.name for path in self._files) or "documents"
            combined_parts: list[str] = []
            for path in self._files:
                if self.isInterruptionRequested():
                    return
                self.progress.emit("assistant", f"Читаю {path.name}…")
                try:
                    text = _read_text(str(path))
                except Exception:
                    logger.exception("Не удалось прочитать файл %s", path)
                    text = ""
                part = f"### {path.name}\n{text}".strip()
                if part:
                    combined_parts.append(part)

            combined_text = "\n\n".join(combined_parts)
            self.progress.emit("assistant", "Отправляю документы на суммаризацию…")
            note, transcript = summarize_document_files([str(p) for p in self._files])
            self.finished.emit(note or "", transcript or "", combined_text, label)
        except Exception as exc:  # pragma: no cover - сеть/файлы
            self.failed.emit(str(exc))


class _FollowupWorker(QThread):
    progress = Signal(str, str)
    finished = Signal(str, str)
    failed = Signal(str)

    def __init__(self, text: str, *, label: str):
        super().__init__()
        self._text = text
        self._label = label or "documents"

    def run(self):
        try:
            def cb(role: str, part: str) -> None:
                if self.isInterruptionRequested():
                    raise InterruptedError("Операция отменена")
                self.progress.emit(role, part)

            cancel_cb = self.isInterruptionRequested

            note, transcript = summarize_documents_interactive(
                self._text,
                progress_cb=cb,
                cancel_cb=cancel_cb,
                label=self._label,
            )
            self.finished.emit(note or "", transcript or "")
        except InterruptedError:
            logger.info("Суммаризация документов отменена пользователем")
        except Exception as exc:  # pragma: no cover - сеть/файлы
            self.failed.emit(str(exc))


class AiDocumentFilesDialog(QDialog):
    """Диалог для суммаризации документов сделки."""

    SETTINGS_KEY = "ai_document_files_dialog"
    INITIAL_WORKER_CLS = _InitialWorker
    FOLLOWUP_WORKER_CLS = _FollowupWorker

    def __init__(
        self,
        parent=None,
        *,
        forced_deal=None,
        initial_files: Iterable[Path] | None = None,
        skipped_items: Sequence[tuple[Path, str]] | None = None,
    ):
        super().__init__(parent)
        self.forced_deal = forced_deal
        self.files: list[Path] = []
        self._skipped_items: list[tuple[Path, str]] = []
        self._current_worker: QThread | None = None
        self._progress_dialog: QProgressDialog | None = None
        self._base_text: str = ""
        self._label: str = "documents"
        self._last_transcript: str = ""
        self._followups: list[tuple[str, str]] = []
        self._has_initial_summary = False

        self.setWindowTitle("Итог по документам")
        self.setAcceptDrops(True)
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)

        if forced_deal is None:
            header = "Перетащите документы или добавьте их вручную"
        else:
            header = (
                f"Документы для сделки #{getattr(forced_deal, 'id', '')}: "
                "перетащите файлы или добавьте их вручную"
            )
        self.label = QLabel(header)
        self.label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.label)

        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QListWidget.ExtendedSelection)
        layout.addWidget(self.list_widget)

        self.skipped_label = QLabel(self)
        self.skipped_label.setWordWrap(True)
        self.skipped_label.setVisible(False)
        layout.addWidget(self.skipped_label)

        self.conv_edit = QTextEdit(self)
        self.conv_edit.setReadOnly(True)
        self.conv_edit.setPlaceholderText("Здесь будет показан протокол диалога с ИИ")
        self.conv_edit.setMinimumHeight(120)
        layout.addWidget(self.conv_edit)

        self.note_edit = QTextEdit(self)
        self.note_edit.setPlaceholderText("Итоговая заметка — вы можете отредактировать её перед сохранением")
        self.note_edit.setAcceptRichText(False)
        self.note_edit.setMinimumHeight(140)
        layout.addWidget(self.note_edit)

        self.input_edit = QLineEdit(self)
        self.input_edit.setPlaceholderText("Уточняющий вопрос…")
        self.input_edit.setVisible(False)
        self.input_edit.returnPressed.connect(self.on_process)
        self.input_edit.textChanged.connect(self._update_process_button_state)
        layout.addWidget(self.input_edit)

        btns = QHBoxLayout()
        self.show_transcript_btn = QPushButton("📜 Протокол", self)
        self.show_transcript_btn.setToolTip("Показать полный диалог с ассистентом")
        self.show_transcript_btn.clicked.connect(self._show_transcript)
        self.show_transcript_btn.setEnabled(False)
        btns.addWidget(self.show_transcript_btn)

        btns.addStretch()
        self.remove_btn = QPushButton("Удалить выбранные", self)
        self.remove_btn.clicked.connect(self.on_remove_selected)
        btns.addWidget(self.remove_btn)

        self.process_btn = QPushButton("Сформировать заметку", self)
        self.process_btn.clicked.connect(self.on_process)
        self.process_btn.setShortcut(QKeySequence("Ctrl+Return"))
        btns.addWidget(self.process_btn)

        cancel_btn = QPushButton("Отмена", self)
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(cancel_btn)

        layout.addLayout(btns)

        self._delete_shortcuts: list[QShortcut] = []
        for key in (Qt.Key_Delete, Qt.Key_Backspace):
            shortcut = QShortcut(QKeySequence(key), self.list_widget)
            shortcut.activated.connect(self.on_remove_selected)
            self._delete_shortcuts.append(shortcut)

        if initial_files:
            self._add_files(initial_files)

        if skipped_items:
            self._register_skipped_items(skipped_items)

        self._update_process_button_state()
        self._restore_geometry()

    # ------------------------------------------------------------------
    def _create_initial_worker(self) -> QThread:
        worker = self.INITIAL_WORKER_CLS(self.files)
        worker.progress.connect(self._append)
        worker.finished.connect(self._on_initial_finished)
        worker.failed.connect(self._on_initial_failed)
        return worker

    def _create_followup_worker(self, text: str) -> QThread:
        worker = self.FOLLOWUP_WORKER_CLS(text, label=self._label)
        worker.progress.connect(self._append)
        worker.finished.connect(self._on_followup_finished)
        worker.failed.connect(self._on_followup_failed)
        return worker

    def _start_worker(self, worker: QThread, *, show_progress: bool = False):
        self._cleanup_worker()
        self._current_worker = worker
        if show_progress:
            self._progress_dialog = QProgressDialog(
                "Подождите, суммаризация документов…",
                "Отмена",
                0,
                0,
                self,
            )
            self._progress_dialog.setWindowModality(Qt.WindowModal)
            self._progress_dialog.canceled.connect(self._cancel_worker)
            self._progress_dialog.show()
        worker.start()

    def _cancel_worker(self) -> None:
        worker = self._current_worker
        if not worker:
            return
        worker.requestInterruption()

    def _cleanup_worker(self, *, wait: bool = False) -> None:
        worker = self._current_worker
        if not worker:
            return

        if wait and worker.isRunning():
            worker.requestInterruption()
            worker.quit()
            if not worker.wait(5000):
                logger.warning("Не удалось корректно остановить поток суммаризации")
                worker.terminate()
                worker.wait(2000)

        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None

        if not worker.isRunning():
            worker.deleteLater()
            self._current_worker = None

    def _append(self, role: str, text: str) -> None:
        if not text:
            return
        cursor = self.conv_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        prefix = "" if role == "assistant" else f"{role}:\n"
        cursor.insertText(f"{prefix}{text}\n")
        self.conv_edit.setTextCursor(cursor)

    # ------------------------------------------------------------------
    def on_remove_selected(self) -> None:
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

    def _on_initial_finished(
        self,
        note: str,
        transcript: str,
        combined_text: str,
        label: str,
    ) -> None:
        self._cleanup_worker()
        self._has_initial_summary = True
        self._base_text = combined_text
        self._label = label or "documents"
        self._last_transcript = transcript
        self._followups.clear()

        self.note_edit.setPlainText(note)
        self.conv_edit.setPlainText(transcript or "Диалог не предоставлен")
        self.show_transcript_btn.setEnabled(bool(transcript))
        self.input_edit.setVisible(True)
        self.process_btn.setText("Уточнить")
        self._update_process_button_state()
        self._show_transcript()

    def _on_initial_failed(self, error: str) -> None:
        self._cleanup_worker()
        if error:
            QMessageBox.warning(self, "Ошибка", error)
        self._update_process_button_state()

    def _on_followup_finished(self, note: str, transcript: str) -> None:
        last_question = self._followups[-1][0] if self._followups else ""
        self._cleanup_worker()
        self.note_edit.setPlainText(note)
        self._last_transcript = transcript
        self.conv_edit.append("\n---\n" + transcript)
        if last_question:
            self._followups[-1] = (last_question, note)
        self.show_transcript_btn.setEnabled(bool(transcript))
        self._update_process_button_state()
        self._show_transcript()

    def _on_followup_failed(self, error: str) -> None:
        self._cleanup_worker()
        if error:
            QMessageBox.warning(self, "Ошибка", error)
        if self._followups:
            self._followups.pop()
        self._update_process_button_state()

    def _show_transcript(self) -> None:
        if not self._last_transcript:
            return
        msg = QMessageBox(self)
        msg.setWindowTitle("Диалог с ИИ")
        msg.setText("Полный протокол взаимодействия доступен в деталях")
        msg.setDetailedText(self._last_transcript)
        msg.exec()

    # ------------------------------------------------------------------
    def on_process(self) -> None:
        if self._current_worker and self._current_worker.isRunning():
            return

        if not self._has_initial_summary:
            if not self.files:
                QMessageBox.warning(self, "Нет файлов", "Добавьте документы для анализа")
                return
            worker = self._create_initial_worker()
            self._append("assistant", "Готовлю суммаризацию…")
            self.process_btn.setEnabled(False)
            self._start_worker(worker, show_progress=True)
            self._update_process_button_state()
            return

        question = self.input_edit.text().strip()
        if not question:
            return
        self.input_edit.clear()
        self._append("user", question)

        history_text = ""
        if self._followups:
            chunks = []
            for prev_q, prev_a in self._followups:
                if not prev_q and not prev_a:
                    continue
                chunk = f"Вопрос менеджера: {prev_q}\nОтвет ассистента: {prev_a}".strip()
                if chunk:
                    chunks.append(chunk)
            history_text = "\n\n".join(chunks)

        note_snapshot = self.note_edit.toPlainText().strip()
        pieces = [self._base_text]
        if note_snapshot:
            pieces.append("Текущая версия заметки:\n" + note_snapshot)
        if history_text:
            pieces.append("Предыдущие уточнения:\n" + history_text)
        pieces.append("Новый вопрос:\n" + question)
        context = "\n\n".join(part for part in pieces if part)

        worker = self._create_followup_worker(context)
        self._followups.append((question, ""))
        self.process_btn.setEnabled(False)
        self._start_worker(worker)
        self._update_process_button_state()

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
        rejected_items: list[tuple[Path, str]] = []

        for original in paths:
            try:
                resolved = Path(original).resolve(strict=True)
            except (FileNotFoundError, OSError):
                msg = "файл не найден"
                rejected.append(f"{original}: {msg}")
                rejected_items.append((Path(original), msg))
                continue

            try:
                if not resolved.is_file():
                    msg = "можно добавить только файлы"
                    rejected.append(f"{resolved}: {msg}")
                    rejected_items.append((resolved, msg))
                    continue
                size = resolved.stat().st_size
            except OSError:
                msg = "не удалось прочитать файл"
                rejected.append(f"{resolved}: {msg}")
                rejected_items.append((resolved, msg))
                continue

            if size == 0:
                msg = "файл пустой"
                rejected.append(f"{resolved}: {msg}")
                rejected_items.append((resolved, msg))
                continue

            if resolved in existing:
                msg = "файл уже добавлен"
                rejected.append(f"{resolved}: {msg}")
                rejected_items.append((resolved, msg))
                continue

            existing.add(resolved)
            self.files.append(resolved)
            self.list_widget.addItem(str(resolved))
            added = True

        if rejected:
            QMessageBox.information(self, "Файл не добавлен", "\n".join(rejected))
        if rejected_items:
            self._register_skipped_items(rejected_items)

        if added:
            self._update_process_button_state()

        return added

    def _register_skipped_items(self, items: Sequence[tuple[Path, str]]) -> None:
        if not items:
            return
        for path, reason in items:
            self._skipped_items.append((Path(path), reason))
        self._update_skipped_label()

    def _update_skipped_label(self) -> None:
        if not self._skipped_items:
            self.skipped_label.clear()
            self.skipped_label.setVisible(False)
            return
        lines = [f"{path}: {reason}" for path, reason in self._skipped_items]
        self.skipped_label.setText(
            "Не удалось использовать некоторые элементы:\n" + "\n".join(lines)
        )
        self.skipped_label.setVisible(True)

    def _update_process_button_state(self) -> None:
        enabled = True
        if self._current_worker and self._current_worker.isRunning():
            enabled = False
        elif not self._has_initial_summary:
            enabled = bool(self.files)
        elif self.input_edit.isVisible():
            enabled = bool(self.input_edit.text().strip()) or bool(self._current_worker)
        self.process_btn.setEnabled(enabled)

    # ------------------------------------------------------------------
    def get_note(self) -> str:
        return self.note_edit.toPlainText()

    def closeEvent(self, event):  # noqa: D401 - Qt override
        self._save_geometry()
        self._cleanup_worker(wait=True)
        super().closeEvent(event)

    def accept(self):  # noqa: D401 - Qt override
        if not self.note_edit.toPlainText().strip():
            QMessageBox.warning(self, "Нет заметки", "Сформируйте или введите текст заметки")
            return
        self._save_geometry()
        super().accept()

    def reject(self):  # noqa: D401 - Qt override
        self._save_geometry()
        self._cleanup_worker(wait=True)
        super().reject()

    def _restore_geometry(self) -> None:
        try:
            settings = ui_settings.get_window_settings(self.SETTINGS_KEY)
            geometry = settings.get("geometry")
            if geometry:
                restored = self.restoreGeometry(base64.b64decode(geometry))
                if not restored:
                    logger.warning(
                        "Не удалось применить сохранённую геометрию окна %s",
                        self.SETTINGS_KEY,
                    )
        except Exception:  # pragma: no cover - logging only
            logger.exception("Не удалось восстановить геометрию окна %s", self.SETTINGS_KEY)

    def _save_geometry(self) -> None:
        try:
            geometry_bytes = bytes(self.saveGeometry())
            geometry = base64.b64encode(geometry_bytes).decode("ascii")
            settings = ui_settings.get_window_settings(self.SETTINGS_KEY)
            settings["geometry"] = geometry
            ui_settings.set_window_settings(self.SETTINGS_KEY, settings)
        except Exception:  # pragma: no cover - logging only
            logger.exception("Не удалось сохранить геометрию окна %s", self.SETTINGS_KEY)
