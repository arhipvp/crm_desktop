import logging
import sys
from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from config import Settings, get_settings
from database.init import init_from_env
from services import executor_service as es
from core.app_context import get_app_context
from ui.main_window import MainWindow
from utils.logging_config import setup_logging

__all__ = ["main"]


def main(settings: Settings | None = None) -> int:
    """Запускает настольное приложение CRM."""

    settings = settings or get_settings()
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL не задан в .env")

    init_from_env(settings.database_url)
    setup_logging(settings)
    logger = logging.getLogger(__name__)

    # ───── Проверка и подготовка окружения ─────
    es.ensure_executors_from_env(settings)

    # ───── GUI ─────
    app = QApplication.instance() or QApplication(sys.argv)

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

    context = get_app_context()

    window = MainWindow(context=context)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
