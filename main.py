import os
import sys
import logging

from PySide6.QtWidgets import QApplication

from database.init import init_from_env

init_from_env()


from ui.main_window import MainWindow
from utils.logging_config import setup_logging
from config import DATABASE_URL

setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # ───── проверка переменных ─────
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL не задан в .env")

    # ───── GUI ─────
    app = QApplication(sys.argv)

    try:
        style_path = os.path.join(os.path.dirname(__file__), "resources", "style.qss")
        with open(style_path, "r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except Exception as e:
        logger.info("Не удалось загрузить стиль: %s", e)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
