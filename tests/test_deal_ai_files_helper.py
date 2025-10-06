from types import SimpleNamespace
from pathlib import Path

from ui.views.deal_detail.actions import DealActionsMixin


def test_collect_selected_files_for_ai_filters_invalid(tmp_path):
    valid = tmp_path / "doc1.txt"
    valid.write_text("hello")
    empty = tmp_path / "empty.txt"
    empty.write_text("")
    folder = tmp_path / "folder"
    folder.mkdir()
    missing = tmp_path / "missing.txt"

    selection = [
        str(valid),
        str(empty),
        str(folder),
        str(missing),
        str(valid),
    ]

    class Dummy(DealActionsMixin):
        def __init__(self, files):
            self.files_panel = SimpleNamespace(selected_files=lambda: files)

    dummy = Dummy(selection)

    initial, skipped = dummy._collect_selected_files_for_ai()

    assert initial == [valid]
    reasons = {Path(path): reason for path, reason in skipped}
    assert reasons[empty] == "файл пустой"
    assert reasons[folder] == "нельзя обработать каталог"
    assert reasons[missing] == "файл не найден"
    assert reasons[valid] == "файл уже добавлен"
