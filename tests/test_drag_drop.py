from datetime import date
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from services.client_service import add_client
from services.deal_service import add_deal
from ui.views.deal_detail_view import DealDetailView


class DummyDealView(DealDetailView):
    """Lightweight subclass avoiding heavy QDialog initialization."""

    def __init__(self, deal, folder):
        # Avoid calling QDialog.__init__
        self.instance = deal
        self._folder = folder

    def _ensure_local_folder(self):
        return str(self._folder)


def test_handle_dropped_files(tmp_path):
    client = add_client(name="C")
    deal = add_deal(client_id=client.id, start_date=date.today(), description="D")
    folder = tmp_path / "deal"
    folder.mkdir()

    dlg = DummyDealView(deal, folder)

    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("1")
    f2.write_text("2")

    dlg._handle_dropped_files([str(f1), str(f2)])

    assert not f1.exists()
    assert not f2.exists()
    assert (folder / "a.txt").read_text() == "1"
    assert (folder / "b.txt").read_text() == "2"
