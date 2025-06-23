import logging

from PySide6.QtWidgets import QMessageBox

logger = logging.getLogger(__name__)


def confirm(text: str, title="Подтверждение") -> bool:
    return (
        QMessageBox.question(
            None,
            title,
            text,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        == QMessageBox.Yes
    )


def show_error(message: str, title="Ошибка"):
    logger.error("❌ UI ошибка: %s", message)
    QMessageBox.critical(None, title, message)


def show_info(message: str, title="Информация"):
    logger.info("ℹ️ UI: %s", message)
    QMessageBox.information(None, title, message)
