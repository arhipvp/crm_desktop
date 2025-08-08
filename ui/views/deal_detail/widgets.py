import re
from PySide6.QtCore import Qt
from PySide6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PySide6.QtWidgets import QWidget, QToolButton, QVBoxLayout, QSizePolicy, QFormLayout, QHBoxLayout


class _CalcHighlighter(QSyntaxHighlighter):
    """Highlight timestamps at the beginning of each line."""

    _regex = re.compile(r"^\[\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\]")

    def highlightBlock(self, text: str) -> None:  # noqa: D401 - Qt override
        m = self._regex.match(text)
        if m:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor("blue"))
            fmt.setFontWeight(QFont.Bold)
            self.setFormat(m.start(), m.end() - m.start(), fmt)


def _with_day_separators(text: str | None) -> str:
    """Insert horizontal separators between different days in the journal."""
    if not text:
        return "\u2014"  # em dash as empty placeholder

    lines = text.splitlines()
    result: list[str] = []
    prev_date = None
    date_rx = re.compile(r"\[(\d{2}\.\d{2}\.\d{4})")

    for line in lines:
        m = date_rx.match(line)
        if m:
            cur_date = m.group(1)
            if prev_date and cur_date != prev_date:
                result.append("-" * 40)
            prev_date = cur_date
        result.append(line)

    return "\n".join(result)


class CollapsibleWidget(QWidget):
    """Простая collapsible-панель с кнопкой раскрытия."""

    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.toggle = QToolButton(text=title, checkable=True, checked=True)
        self.toggle.setStyleSheet("QToolButton { border: none; }")
        self.toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(Qt.DownArrow)
        self.toggle.clicked.connect(self._on_toggled)

        self.content = QWidget()
        self.content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle)
        layout.addWidget(self.content)

    def setContentLayout(self, layout: QVBoxLayout | QFormLayout | QHBoxLayout) -> None:
        self.content.setLayout(layout)

    def _on_toggled(self, checked: bool) -> None:
        self.content.setVisible(checked)
        self.toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
