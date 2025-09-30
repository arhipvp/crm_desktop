from __future__ import annotations

import pytest

from config import Settings
from infrastructure.drive_gateway import DriveGateway


class _FakeExecute:
    def __init__(self, response):
        self._response = response

    def execute(self):
        return self._response


class _FakeFilesResource:
    def __init__(self, list_response, create_response=None):
        self.list_calls: list[dict] = []
        self.create_calls: list[dict] = []
        self._list_response = list_response
        self._create_response = create_response or {"id": "folder123"}

    def list(self, **kwargs):
        self.list_calls.append(kwargs)
        return _FakeExecute(self._list_response)

    def create(self, **kwargs):
        self.create_calls.append(kwargs)
        return _FakeExecute(self._create_response)


class _FakeService:
    def __init__(self, files_resource):
        self._files_resource = files_resource

    def files(self):
        return self._files_resource


@pytest.fixture
def drive_settings():
    return Settings(drive_root_folder_id="parent")


def test_create_drive_folder_escapes_apostrophes(monkeypatch, drive_settings):
    files_resource = _FakeFilesResource({"files": []})
    service = _FakeService(files_resource)
    gateway = DriveGateway(drive_settings)
    monkeypatch.setattr(gateway, "_get_service", lambda: service)

    url = gateway.create_drive_folder("O'Brien")

    assert files_resource.list_calls, "Запрос к Google Drive не был выполнен"
    query = files_resource.list_calls[-1]["q"]
    assert "O\\'Brien" in query
    assert files_resource.create_calls[-1]["body"]["name"] == "O'Brien"
    assert url.endswith("folder123")


def test_find_drive_folder_escapes_apostrophes(monkeypatch, drive_settings):
    files_resource = _FakeFilesResource(
        {"files": [{"webViewLink": "https://drive.google.com/example"}]}
    )
    service = _FakeService(files_resource)
    gateway = DriveGateway(drive_settings)
    monkeypatch.setattr(gateway, "_get_service", lambda: service)

    result = gateway.find_drive_folder("O'Brien")

    assert result == "https://drive.google.com/example"
    assert files_resource.list_calls, "Запрос к Google Drive не был выполнен"
    query = files_resource.list_calls[-1]["q"]
    assert "O\\'Brien" in query
