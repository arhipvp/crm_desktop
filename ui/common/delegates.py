from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QStyledItemDelegate


class StatusDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option, index)

        model = index.model()
        row = index.row()
        if hasattr(model, "get_item"):
            obj = model.get_item(row)
        else:
            obj = None
        if not obj:
            return

        # Удалённое
        if getattr(obj, "is_deleted", False):
            option.palette.setColor(QPalette.Text, QColor("#AAAAAA"))
            font = option.font
            font.setStrikeOut(True)
            option.font = font
            return

        # Завершено
        if getattr(obj, "is_done", False):
            option.palette.setColor(QPalette.Text, QColor("#888888"))
            font = option.font
            font.setItalic(True)
            option.font = font
            return

        # Просрочено
        
        today = date.today()

        if hasattr(obj, "payment_date") and not getattr(obj, "actual_payment_date", None):
            if obj.payment_date and obj.payment_date < today:
                option.palette.setColor(QPalette.Text, QColor("red"))

        if hasattr(obj, "due_date") and not getattr(obj, "is_done", False):
            if obj.due_date and obj.due_date < today:
                option.palette.setColor(QPalette.Text, QColor("red"))
                
        if hasattr(obj, "reminder_date") and not getattr(obj, "is_done", False):
            if obj.reminder_date and obj.reminder_date < today:
                option.palette.setColor(QPalette.Text, QColor("red"))


__all__ = ["StatusDelegate"]
