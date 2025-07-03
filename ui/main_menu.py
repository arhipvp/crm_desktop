from PySide6.QtWidgets import QMenuBar, QMessageBox, QFileDialog
from PySide6.QtGui import QAction, QKeySequence
import subprocess
import sys
from pathlib import Path


class MainMenu(QMenuBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.refresh_callback = None  # 🔄 для кнопки "Обновить"

        # 🔸 Файл
        file_menu = self.addMenu("Файл")

        export_action = QAction("📤 Экспорт в CSV...", self)
        export_action.setShortcut(QKeySequence("Ctrl+E"))
        export_action.triggered.connect(self.export_to_csv)
        file_menu.addAction(export_action)

        backup_action = QAction("💾 Резервное копирование", self)
        backup_action.setShortcut(QKeySequence("Ctrl+B"))
        backup_action.triggered.connect(self.run_backup)
        file_menu.addAction(backup_action)

        # 🔄 Обновить
        refresh_action = QAction("🔄 Обновить", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.on_refresh_triggered)
        file_menu.addAction(refresh_action)

        import_policy_action = QAction("📥 Импорт полиса из JSON…", self)
        import_policy_action.triggered.connect(self.open_import_policy_json)
        file_menu.addAction(import_policy_action)

        executor_action = QAction("👥 Исполнители…", self)
        executor_action.triggered.connect(self.open_executors)
        file_menu.addAction(executor_action)

        settings_action = QAction("Настройки…", self)
        settings_action.triggered.connect(self.open_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        exit_action = QAction("Выход", self)
        exit_action.setShortcut(QKeySequence("Ctrl+Q"))
        exit_action.triggered.connect(self.close_app)
        file_menu.addAction(exit_action)

        # 🔸 Справка
        help_menu = self.addMenu("Справка")

        about_action = QAction("ℹ️ О программе", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

        docs_action = QAction("📚 Документация", self)
        docs_action.triggered.connect(self.open_docs)
        help_menu.addAction(docs_action)

        consultant_action = QAction("🤖 AI-консультант…", self)
        consultant_action.triggered.connect(self.open_ai_consultant)
        help_menu.addAction(consultant_action)

    def export_to_csv(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Сохранить как CSV", "", "CSV Files (*.csv)"
        )
        if file_path:
            QMessageBox.information(self, "Экспорт", f"Сюда будет экспорт: {file_path}")
            # 🔧 Здесь ты можешь вызвать свою функцию экспорта

    def close_app(self):
        self.parent().close()

    def show_about(self):
        QMessageBox.about(
            self,
            "О программе",
            "CRM-десктоп\nВерсия 1.0\n\nРазработано специально для учёта клиентов, сделок и полисов.\nПодробнее смотрите в документации.",
        )

    def register_refresh_callback(self, func):
        """Позволяет зарегистрировать обработчик обновления."""
        self.refresh_callback = func

    def on_refresh_triggered(self):
        if self.refresh_callback:
            self.refresh_callback()

    def open_import_policy_json(self):
        # Пробрасываем наверх (в MainWindow)
        mw = self.parent()
        if mw and hasattr(mw, "open_import_policy_json"):
            mw.open_import_policy_json()

    def open_executors(self):
        mw = self.parent()
        if mw and hasattr(mw, "open_executors"):
            mw.open_executors()

    def open_settings(self):
        mw = self.parent()
        if mw and hasattr(mw, "open_settings"):
            mw.open_settings()
        else:
            from ui.forms.settings_dialog import SettingsDialog

            dlg = SettingsDialog(self)
            dlg.exec()

    def open_ai_consultant(self):
        mw = self.parent()
        if mw and hasattr(mw, "open_ai_consultant"):
            mw.open_ai_consultant()
        else:
            from ui.forms.ai_consultant_dialog import AiConsultantDialog

            dlg = AiConsultantDialog(self)
            dlg.exec()

    def open_docs(self):
        import webbrowser

        webbrowser.open_new_tab("https://example.com/docs")

    def run_backup(self):
        """Запуск скрипта резервного копирования."""
        script = Path(__file__).resolve().parent.parent / "backup.py"
        try:
            subprocess.run([sys.executable, str(script)], check=True)
            QMessageBox.information(self, "Бэкап", "Резервная копия создана.")
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось выполнить бэкап:\n{exc}",
            )
