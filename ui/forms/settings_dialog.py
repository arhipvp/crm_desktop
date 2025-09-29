from __future__ import annotations

import base64

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QFileDialog,
    QCheckBox,
)

from ui import settings as ui_settings


SETTINGS_KEY = "settings_dialog"


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

        self.open_main_window_maximized = QCheckBox("Открывать главное окно на весь экран")
        layout.addWidget(self.open_main_window_maximized)

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
        self._restore_geometry()

    # --------------------------------------------------------------
    def load(self) -> None:
        st = ui_settings.get_app_settings()
        self.drive_path.setText(st.get("google_drive_local_root", ""))
        self.credentials_path.setText(st.get("google_credentials", ""))
        self.root_folder_id.setText(st.get("google_root_folder_id", ""))
        window_settings = ui_settings.get_window_settings("MainWindow")
        self.open_main_window_maximized.setChecked(
            bool(window_settings.get("open_maximized"))
        )

    # --------------------------------------------------------------
    def save(self) -> None:
        data = {
            "google_drive_local_root": self.drive_path.text().strip(),
            "google_credentials": self.credentials_path.text().strip(),
            "google_root_folder_id": self.root_folder_id.text().strip(),
        }
        ui_settings.set_app_settings(data)
        window_settings = ui_settings.get_window_settings("MainWindow")
        window_settings["open_maximized"] = self.open_main_window_maximized.isChecked()
        ui_settings.set_window_settings("MainWindow", window_settings)
        self.accept()

    # --------------------------------------------------------------
    def choose_drive_path(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Выберите каталог")
        if path:
            self.drive_path.setText(path)

    # --------------------------------------------------------------
    def _restore_geometry(self) -> None:
        window_settings = ui_settings.get_window_settings(SETTINGS_KEY)
        geometry = window_settings.get("geometry")
        if geometry:
            try:
                self.restoreGeometry(base64.b64decode(geometry))
            except (ValueError, TypeError):
                pass

    # --------------------------------------------------------------
    def _save_geometry(self) -> None:
        window_settings = ui_settings.get_window_settings(SETTINGS_KEY)
        window_settings["geometry"] = base64.b64encode(self.saveGeometry()).decode("ascii")
        ui_settings.set_window_settings(SETTINGS_KEY, window_settings)

    # --------------------------------------------------------------
    def accept(self) -> None:
        self._save_geometry()
        super().accept()

    # --------------------------------------------------------------
    def reject(self) -> None:
        self._save_geometry()
        super().reject()

    # --------------------------------------------------------------
    def closeEvent(self, event) -> None:
        self._save_geometry()
        super().closeEvent(event)
