import logging
import sys
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from config import get_settings
from database.init import init_from_env
from services import executor_service as es
from ui.main_window import MainWindow
from utils.logging_config import setup_logging

# ───── Инициализация базы данных и логирования ─────
settings = get_settings()
if not settings.database_url:
    raise RuntimeError("DATABASE_URL не задан в .env")
init_from_env(settings.database_url)
setup_logging(settings)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # ───── Проверка и подготовка окружения ─────
    es.ensure_executors_from_env(settings)

    # ───── GUI ─────
    app = QApplication(sys.argv)

    try:
        base_dir = Path(__file__).resolve().parent
        fonts_dir = base_dir / "resources" / "fonts"
        QFontDatabase.addApplicationFont(str(fonts_dir / "Roboto-Regular.ttf"))
        app.setFont(QFont("Roboto", 10))

        style_path = base_dir / "resources" / "style.qss"
        with style_path.open("r", encoding="utf-8") as f:
            app.setStyleSheet(f.read())
    except OSError as e:
        logger.warning("Не удалось загрузить стиль: %s", e)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
