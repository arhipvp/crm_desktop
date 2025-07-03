from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QMessageBox,
)

from services.ai_consultant_service import ask_consultant


class AiConsultantDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI-консультант")
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Вопрос:"))

        self.question_edit = QLineEdit(self)
        layout.addWidget(self.question_edit)

        self.answer_edit = QTextEdit(self)
        self.answer_edit.setReadOnly(True)
        layout.addWidget(self.answer_edit)

        btns = QHBoxLayout()
        self.ask_btn = QPushButton("Спросить", self)
        self.ask_btn.clicked.connect(self.on_ask)
        close_btn = QPushButton("Закрыть", self)
        close_btn.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.ask_btn)
        btns.addWidget(close_btn)
        layout.addLayout(btns)

    def on_ask(self):
        question = self.question_edit.text().strip()
        if not question:
            QMessageBox.warning(self, "Ошибка", "Введите вопрос.")
            return
        self.ask_btn.setEnabled(False)
        try:
            answer = ask_consultant(question)
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))
            self.ask_btn.setEnabled(True)
            return
        self.answer_edit.setPlainText(answer)
        self.ask_btn.setEnabled(True)
