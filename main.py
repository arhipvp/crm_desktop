import os
import sys
import logging

from PySide6.QtWidgets import QApplication

from database.init import init_from_env

init_from_env()

from pathlib import Path

from dotenv import load_dotenv

from ui.main_window import MainWindow
from utils.logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # ───── инициализация переменных ─────
    dotenv_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(dotenv_path=dotenv_path)

    DATABASE_URL = os.getenv("DATABASE_URL")
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
