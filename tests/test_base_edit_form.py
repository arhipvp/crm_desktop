import base64

import pytest

from ui.base.base_edit_form import BaseEditForm
from ui import settings as ui_settings


class DummyModel:
    pass


class DummyEditForm(BaseEditForm):
    dialog_target_size = None
    dialog_minimum_size = None

    def save_data(self):  # pragma: no cover - not used in this test
        return None


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_base_edit_form_saves_geometry(qapp):
    form = DummyEditForm(model_class=DummyModel)
    form.show()
    qapp.processEvents()

    form.resize(640, 480)
    qapp.processEvents()

    expected_geometry = base64.b64encode(bytes(form.saveGeometry())).decode("ascii")

    form.close()
    qapp.processEvents()

    settings = ui_settings.get_window_settings(form._settings_key)

    assert settings["geometry"] == expected_geometry


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_base_edit_form_saves_geometry_on_accept(qapp):
    form = DummyEditForm(model_class=DummyModel)
    form.show()
    qapp.processEvents()

    form.resize(660, 510)
    qapp.processEvents()

    expected_geometry = base64.b64encode(bytes(form.saveGeometry())).decode("ascii")

    form.accept()
    qapp.processEvents()

    settings = ui_settings.get_window_settings(form._settings_key)

    assert settings["geometry"] == expected_geometry


@pytest.mark.usefixtures("ui_settings_temp_path")
def test_base_edit_form_saves_geometry_on_reject(qapp):
    form = DummyEditForm(model_class=DummyModel)
    form.show()
    qapp.processEvents()

    form.resize(700, 520)
    qapp.processEvents()

    expected_geometry = base64.b64encode(bytes(form.saveGeometry())).decode("ascii")

    form.reject()
    qapp.processEvents()

    settings = ui_settings.get_window_settings(form._settings_key)

    assert settings["geometry"] == expected_geometry
