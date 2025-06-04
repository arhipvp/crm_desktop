from PySide6.QtWidgets import QCheckBox, QWidget, QHBoxLayout


class CheckboxFilters(QWidget):
    def __init__(self, filters: dict, parent=None):
        """
        filters: словарь вида {"Показывать удалённые": callback_function}
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.checkboxes = {}

        for label, callback in filters.items():
            checkbox = QCheckBox(label)
            checkbox.setChecked(False)
            checkbox.stateChanged.connect(callback)
            layout.addWidget(checkbox)
            self.checkboxes[label] = checkbox

        layout.addStretch()

    def set_checked(self, label: str, value: bool):
        """Установить состояние чекбокса программно."""
        if label in self.checkboxes:
            self.checkboxes[label].setChecked(value)

    def is_checked(self, label: str) -> bool:
        """Получить состояние чекбокса."""
        box = self.checkboxes.get(label)
        return box.isChecked() if box else False

    
    def get_all_states(self) -> dict:
        """Вернёт словарь состояний всех чекбоксов."""
        return {label: box.isChecked() for label, box in self.checkboxes.items()}

    def toggle(self, label: str):
        """Переключить чекбокс."""
        if label in self.checkboxes:
            current = self.checkboxes[label].isChecked()
            self.checkboxes[label].setChecked(not current)

    def clear(self):
        """Снять все галочки."""
        for box in self.checkboxes.values():
            box.setChecked(False)

    def set_bulk(self, states: dict):
        """Установить несколько флагов сразу."""
        for label, value in states.items():
            if label in self.checkboxes:
                self.checkboxes[label].setChecked(value)
