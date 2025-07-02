import os
from services.folder_utils import create_deal_folder, rename_deal_folder, sanitize_name


def test_create_deal_folder_local(tmp_path, monkeypatch):
    root = tmp_path / 'drive'
    monkeypatch.setenv('GOOGLE_DRIVE_LOCAL_ROOT', str(root))
    monkeypatch.setattr('services.folder_utils.GOOGLE_DRIVE_LOCAL_ROOT', str(root))

    path, link = create_deal_folder('Client', 'My Deal', client_drive_link=None)

    assert link is None
    assert os.path.isdir(path)
    expected = root / sanitize_name('Client') / sanitize_name('Сделка - My Deal')
    assert path == str(expected)


def test_create_deal_folder_existing(tmp_path, monkeypatch):
    root = tmp_path / 'drive'
    monkeypatch.setenv('GOOGLE_DRIVE_LOCAL_ROOT', str(root))
    monkeypatch.setattr('services.folder_utils.GOOGLE_DRIVE_LOCAL_ROOT', str(root))

    existing = root / sanitize_name('Client') / sanitize_name('Сделка - My Deal')
    existing.mkdir(parents=True)

    path, link = create_deal_folder('Client', 'My Deal', client_drive_link=None)

    assert path == str(existing)
    assert link is None
    assert os.path.isdir(path)


def test_rename_deal_folder_local(tmp_path, monkeypatch):
    root = tmp_path / 'drive'
    monkeypatch.setenv('GOOGLE_DRIVE_LOCAL_ROOT', str(root))
    monkeypatch.setattr('services.folder_utils.GOOGLE_DRIVE_LOCAL_ROOT', str(root))

    old_client = 'Old'
    new_client = 'New'
    old_desc = 'Old Deal'
    new_desc = 'New Deal'

    old_path = root / sanitize_name(old_client) / sanitize_name(f'Сделка - {old_desc}')
    old_path.mkdir(parents=True)

    new_path, link = rename_deal_folder(old_client, old_desc, new_client, new_desc, None)

    expected = root / sanitize_name(new_client) / sanitize_name(f'Сделка - {new_desc}')
    assert new_path == str(expected)
    assert os.path.isdir(new_path)
    assert link is None


def test_rename_deal_folder_missing(tmp_path, monkeypatch):
    root = tmp_path / 'drive'
    monkeypatch.setenv('GOOGLE_DRIVE_LOCAL_ROOT', str(root))
    monkeypatch.setattr('services.folder_utils.GOOGLE_DRIVE_LOCAL_ROOT', str(root))

    new_path, link = rename_deal_folder('Old', 'Old Deal', 'New', 'New Deal', None)

    expected = root / sanitize_name('New') / sanitize_name('Сделка - New Deal')
    assert new_path == str(expected)
    assert os.path.isdir(new_path)
    assert link is None
