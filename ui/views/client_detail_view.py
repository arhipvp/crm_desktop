from ui.base.base_detail_view import BaseDetailView
from database.models import Client

class ClientDetailView(BaseDetailView):
    def __init__(self, client: Client, parent=None):
        super().__init__(client, parent=parent)
