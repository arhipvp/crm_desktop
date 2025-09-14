import datetime
import logging

logger = logging.getLogger(__name__)

from peewee import ForeignKeyField
from PySide6.QtCore import QAbstractTableModel, QDate, Qt

from ui.common.ru_headers import RU_HEADERS

HIDDEN_FIELDS = {"id", "is_deleted", "drive_folder_path", "link_to_drive", "deleted_at"}


class BaseTableModel(QAbstractTableModel):
    def __init__(self, objects: list, model_class, parent=None):
        super().__init__(parent)
        self.objects = objects
        self.model_class = model_class
        self.fields = [
            f
            for f in self.model_class._meta.sorted_fields
            if f.name not in HIDDEN_FIELDS
        ]

        self.headers = [f.name for f in self.fields]

    def rowCount(self, parent=None):
        return len(self.objects)

    def columnCount(self, parent=None):
        return len(self.fields)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None

        if orientation == Qt.Horizontal:
            if 0 <= section < len(self.fields):
                field = self.fields[section]
                return RU_HEADERS.get(field.name, field.name)
        return super().headerData(section, orientation, role)

    def get_item(self, row):
        return self.objects[row]

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        obj = self.objects[index.row()]
        field = self.fields[index.column()]
        try:
            value = getattr(obj, field.name)
        except Exception as e:
            logger.warning(
                "⚠️ Ошибка при доступе к %s у объекта %s: %s", field.name, obj, e
            )
            value = None

        # ─── роль сортировки ───────────────────────────
        if role == Qt.UserRole:
            if isinstance(value, datetime.date):
                return QDate(value.year, value.month, value.day)
            return value

        # ─── текст в ячейке ────────────────────────────
        if role == Qt.DisplayRole:
            if isinstance(field, ForeignKeyField):
                return str(value) if value else "—"

            if isinstance(value, (datetime.date, datetime.datetime)):
                return self.format_date(value)

            if isinstance(value, (int, float)) and field.name in {
                "amount",
                "sum",
                "price",
            }:
                return self.format_money(value)

            if isinstance(value, str) and len(value) > 40:
                return self.shorten_text(value)

            return "—" if value is None else str(value)

        # ─── подсказка при наведении ───────────────────
        if role == Qt.ToolTipRole and isinstance(value, str) and len(value) > 40:
            return value

        # ─── выравнивание ──────────────────────────────
        if role == Qt.TextAlignmentRole:
            if isinstance(value, (int, float)):
                return Qt.AlignRight | Qt.AlignVCenter

        return None

    def format_money(self, value):
        return f"{value:,.2f} ₽".replace(",", " ").replace(".00", ",00")

    def format_date(self, value):
        return value.strftime("%d.%m.%Y")

    def shorten_text(self, text, limit=40):
        return text if len(text) <= limit else text[:limit] + "…"

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def setData(self, index, value, role=Qt.EditRole):
        if not index.isValid() or role != Qt.EditRole:
            return False

        obj = self.objects[index.row()]
        field = self.fields[index.column()]
        setattr(obj, field.name, value)

        try:
            obj.save()
            self.dataChanged.emit(index, index, [Qt.DisplayRole])
            return True
        except Exception as e:
            logger.error(
                "❌ Ошибка сохранения %s.%s: %s", type(obj).__name__, field.name, e
            )
            return False
