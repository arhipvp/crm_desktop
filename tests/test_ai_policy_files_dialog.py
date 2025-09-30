from types import SimpleNamespace

from PySide6.QtWidgets import QDialog, QMessageBox

from ui.forms.ai_policy_files_dialog import AiPolicyFilesDialog


def test_moves_files_to_local_folder_when_only_path_set(tmp_path, qapp, monkeypatch):
    dialog = AiPolicyFilesDialog()
    try:
        dialog.files = [tmp_path / "file1.pdf", tmp_path / "file2.pdf"]

        monkeypatch.setattr(QMessageBox, "exec", lambda self: None)

        dest_path = tmp_path / "dest"
        moved: list[tuple[str, str]] = []

        def fake_move(src: str, dest: str) -> None:
            moved.append((src, dest))

        monkeypatch.setattr(
            "services.folder_utils.move_file_to_folder", fake_move
        )

        class DummyImportPolicyJsonForm:
            def __init__(self, *args, **kwargs):
                self.imported_policy = SimpleNamespace(
                    drive_folder_link="",
                    drive_folder_path=str(dest_path),
                )

            def exec(self):
                return True

        monkeypatch.setattr(
            "ui.forms.ai_policy_files_dialog.ImportPolicyJsonForm",
            DummyImportPolicyJsonForm,
        )

        dialog._on_finished({}, [], "")

        assert dialog.result() == QDialog.Accepted
        expected = [(str(path), str(dest_path)) for path in dialog.files]
        assert moved == expected
    finally:
        dialog.deleteLater()
