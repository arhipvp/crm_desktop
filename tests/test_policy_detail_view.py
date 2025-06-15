import os
from datetime import date

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from services.client_service import add_client
from database.models import Policy
from ui.views.policy_detail_view import PolicyDetailView


def test_policy_detail_no_drive_path(qtbot):
    client = add_client(name="A")
    policy = Policy.create(
        client=client,
        policy_number="TST",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
    )
    dlg = PolicyDetailView(policy)
    qtbot.addWidget(dlg)
    assert dlg.instance == policy
