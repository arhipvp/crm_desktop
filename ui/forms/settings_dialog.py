from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QFileDialog,
)

from ui import settings as ui_settings


class SettingsDialog(QDialog):
    """Диалог редактирования основных настроек приложения."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        # --- Google Drive local path ---
        self.drive_path = QLineEdit()
        browse = QPushButton("...")
        browse.clicked.connect(self.choose_drive_path)
        row = QHBoxLayout()
        row.addWidget(self.drive_path)
        row.addWidget(browse)
        form.addRow("Локальный Google Drive:", row)

        # --- credentials file ---
        self.credentials_path = QLineEdit()
        form.addRow("Файл учётных данных:", self.credentials_path)

        # --- root folder id ---
        self.root_folder_id = QLineEdit()
        form.addRow("ID корневой папки:", self.root_folder_id)

        btns = QHBoxLayout()
        save = QPushButton("Сохранить")
        cancel = QPushButton("Отмена")
        save.clicked.connect(self.save)
        cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(save)
        btns.addWidget(cancel)
        layout.addLayout(btns)

        self.load()

    # --------------------------------------------------------------
    def load(self) -> None:
        st = ui_settings.get_app_settings()
        self.drive_path.setText(st.get("google_drive_local_root", ""))
        self.credentials_path.setText(st.get("google_credentials", ""))
        self.root_folder_id.setText(st.get("google_root_folder_id", ""))

    # --------------------------------------------------------------
    def save(self) -> None:
        data = {
            "google_drive_local_root": self.drive_path.text().strip(),
            "google_credentials": self.credentials_path.text().strip(),
            "google_root_folder_id": self.root_folder_id.text().strip(),
        }
        ui_settings.set_app_settings(data)
        self.accept()

    # --------------------------------------------------------------
    def choose_drive_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Выберите каталог")
        if path:
            self.drive_path.setText(path)
