from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
)
from PySide6.QtCore import Qt
import os
import json as _json

from services.ai_policy_service import process_policy_bundle_with_ai
from ui.forms.import_policy_json_form import ImportPolicyJsonForm
from ui.common.message_boxes import show_error


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

        btns = QHBoxLayout()
        self.process_btn = QPushButton("Распознать", self)
        self.process_btn.clicked.connect(self.on_process)
        cancel_btn = QPushButton("Отмена", self)
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.process_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

        self.files: list[str] = []

    # ------------------------------------------------------------------
    def dragEnterEvent(self, event):  # noqa: D401 - Qt override
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):  # noqa: D401 - Qt override
        urls = [u for u in event.mimeData().urls() if u.isLocalFile()]
        for url in urls:
            path = url.toLocalFile()
            if path not in self.files:
                self.files.append(path)
                self.list_widget.addItem(path)
        if urls:
            event.acceptProposedAction()

    # ------------------------------------------------------------------
    def on_process(self):
        if not self.files:
            QMessageBox.warning(self, "Ошибка", "Добавьте файлы.")
            return
        try:
            data, conv = process_policy_bundle_with_ai(self.files)
        except Exception as e:  # pragma: no cover - network errors
            show_error(str(e))
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Диалог с ИИ")
        if len(self.files) == 1:
            name = os.path.basename(self.files[0])
            msg.setText(
                f"Распознавание файла {name} завершено. Полный диалог см. в деталях."
            )
        else:
            msg.setText(
                "Распознавание файлов завершено. Полный диалог см. в деталях."
            )
        msg.setDetailedText(conv)
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
                    move_file_to_folder(src, policy.drive_folder_link)
        self.accept()
