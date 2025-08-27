import logging
import os
import sys
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from config import get_settings
from database.init import init_from_env
from services import executor_service as es
from ui.main_window import MainWindow
from utils.logging_config import setup_logging

# ───── Инициализация базы данных и логирования ─────
settings = get_settings()
init_from_env(settings.database_url)
setup_logging(settings)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # ───── Проверка и подготовка окружения ─────
    es.ensure_executors_from_env(settings)

    DATABASE_URL = settings.database_url
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL не задан в .env")

    # ───── GUI ─────
    app = QApplication(sys.argv)

    try:
        fonts_dir = os.path.join(os.path.dirname(__file__), "resources", "fonts")
        QFontDatabase.addApplicationFont(os.path.join(fonts_dir, "Roboto-Regular.ttf"))
        app.setFont(QFont("Roboto", 10))

        style_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except OSError as e:
        logger.warning("Не удалось загрузить стиль: %s", e)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
