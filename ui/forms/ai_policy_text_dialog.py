from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
)
import json

from services.ai_policy_service import process_policy_text_with_ai
from ui.forms.import_policy_json_form import ImportPolicyJsonForm


class AiPolicyTextDialog(QDialog):
    def __init__(self, parent=None, *, forced_client=None, forced_deal=None):
        super().__init__(parent)
        self.forced_client = forced_client
        self.forced_deal = forced_deal
        self.setWindowTitle("Распознавание полиса из текста")
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit(self)
        self.text_edit.setPlaceholderText("Вставьте текст полиса...")
        layout.addWidget(self.text_edit)

        btns = QHBoxLayout()
        self.process_btn = QPushButton("Распознать", self)
        self.process_btn.clicked.connect(self.on_process)
        cancel_btn = QPushButton("Отмена", self)
        cancel_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.process_btn)
        btns.addWidget(cancel_btn)
        layout.addLayout(btns)

    def on_process(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Ошибка", "Вставьте текст полиса.")
            return
        self.process_btn.setEnabled(False)
        try:
            data, conversation = process_policy_text_with_ai(text)
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            self.process_btn.setEnabled(True)
            return

        msg = QMessageBox(self)
        msg.setWindowTitle("Диалог с ИИ")
        msg.setText("Распознавание выполнено. Полный диалог см. в деталях.")
        msg.setDetailedText(conversation)
        msg.exec()

        json_text = json.dumps(data, ensure_ascii=False, indent=2)
        form = ImportPolicyJsonForm(
            parent=self,
            forced_client=self.forced_client,
            forced_deal=self.forced_deal,
            json_text=json_text,
        )
        if form.exec():
            self.accept()
        else:
            self.process_btn.setEnabled(True)
