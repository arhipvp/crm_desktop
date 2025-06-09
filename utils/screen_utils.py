from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSize


def get_scaled_size(base_width: int, base_height: int, ratio: float = 0.9) -> QSize:
    """Return window size adjusted to the available screen."""
    screen = QApplication.primaryScreen()
    if not screen:
        return QSize(base_width, base_height)
    geom = screen.availableGeometry()
    width = min(base_width, int(geom.width() * ratio))
    height = min(base_height, int(geom.height() * ratio))
    return QSize(width, height)
