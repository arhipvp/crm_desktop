import datetime
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from database.models import Policy
from ui.forms.policy_merge_dialog import PolicyMergeDialog


def _create_app():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _find_row(dlg: PolicyMergeDialog, field: str) -> int:
    for row in range(dlg.table.rowCount()):
        item = dlg.table.item(row, 0)
        if item and item.data(Qt.UserRole) == field:
            return row
    raise AssertionError(f"Row {field} not found")


def test_policy_merge_dialog_display_and_filter():
    _create_app()
    existing = Policy(
        policy_number="P1",
        insurance_company="Old",
        start_date=datetime.date(2024, 1, 1),
    )
    new_data = {
        "policy_number": "P1",
        "insurance_company": "New",
        "start_date": datetime.date(2024, 1, 1),
    }
    dlg = PolicyMergeDialog(existing, new_data)
    assert dlg.table.rowCount() == 3

    row_ins = _find_row(dlg, "insurance_company")
    row_num = _find_row(dlg, "policy_number")

    assert not dlg.table.isRowHidden(row_ins)
    assert not dlg.table.isRowHidden(row_num)

    color_changed = dlg.table.item(row_ins, 3).background().color()
    assert color_changed.isValid() and color_changed.name().lower() == "#fff0b3"

    color_unchanged = dlg.table.item(row_num, 3).background().color()
    assert not color_unchanged.isValid()

    dlg.show_only_changes_cb.setChecked(True)
    assert not dlg.table.isRowHidden(row_ins)
    assert dlg.table.isRowHidden(row_num)
