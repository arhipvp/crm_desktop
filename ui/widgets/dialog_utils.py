from PySide6.QtWidgets import QDialog, QVBoxLayout


def open_edit_dialog(form_widget):
    dlg = QDialog()
    dlg.setWindowTitle("Редактирование")
    layout = QVBoxLayout(dlg)
    layout.addWidget(form_widget)
    dlg.exec()
