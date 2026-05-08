from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pydiag.models import well_by_id
from pydiag.storage import load_wells_doc

APP_PATH = Path(__file__).resolve().parents[2] / "app.py"


def run_app_with_temp_data(
    data_paths: tuple[Path, Path],
    monkeypatch,
    *,
    configure_admin: bool = True,
) -> AppTest:
    graph_path, wells_path = data_paths
    monkeypatch.setenv("PYDIAG_GRAPH_PATH", str(graph_path))
    monkeypatch.setenv("PYDIAG_WELLS_PATH", str(wells_path))
    monkeypatch.delenv("PYDIAG_ALLOW_INSECURE_ADMIN", raising=False)
    if configure_admin:
        monkeypatch.setenv("PYDIAG_ADMIN_PASSWORD", "test-admin")
    else:
        monkeypatch.delenv("PYDIAG_ADMIN_PASSWORD", raising=False)

    app = AppTest.from_file(str(APP_PATH))
    app.run(timeout=30)
    assert not app.exception
    return app


def login_as_admin(app: AppTest) -> AppTest:
    app.text_input[0].set_value("test-admin").run(timeout=30)
    app.button[0].click().run(timeout=30)
    assert not app.exception
    return app


def click_button(app: AppTest, label: str) -> AppTest:
    for button in app.button:
        if button.label == label:
            button.click().run(timeout=30)
            assert not app.exception
            return app
    raise AssertionError(f"Button not found: {label}")


def test_streamlit_app_renders_default_workspace(data_paths, monkeypatch) -> None:
    app = run_app_with_temp_data(data_paths, monkeypatch)

    assert any("Карта планирования и бурения" in item.value for item in app.markdown)
    assert any("Узлы" in item.value and "18" in item.value for item in app.markdown)
    assert app.info[0].value == "Выберите узел, связь или фишку скважины на схеме."


def test_streamlit_app_requires_explicit_admin_password(data_paths, monkeypatch) -> None:
    app = run_app_with_temp_data(data_paths, monkeypatch, configure_admin=False)

    assert any("Админ-пароль не настроен" in item.value for item in app.warning)
    labels = {button.label for button in app.button}
    assert {"Войти", "Перечитать JSON"} <= labels
    assert "Продвинуть" not in labels


def test_streamlit_admin_login_reveals_management_panel(
    data_paths,
    monkeypatch,
) -> None:
    app = run_app_with_temp_data(data_paths, monkeypatch)

    login_as_admin(app)

    assert any(item.value == "Режим управления активен" for item in app.success)
    assert {button.label for button in app.button} >= {
        "Продвинуть",
        "Откатить",
        "Удалить скважину",
        "Создать",
    }


def test_streamlit_admin_can_move_well_without_touching_real_json(
    data_paths,
    monkeypatch,
) -> None:
    _, wells_path = data_paths
    app = run_app_with_temp_data(data_paths, monkeypatch)
    login_as_admin(app)

    click_button(app, "Продвинуть")

    saved = load_wells_doc(wells_path)
    well = well_by_id(saved)["well_1001"]
    assert saved.version == 2
    assert well.current_node_id == "dec_data_complete"
    assert well.history[-1].action == "move"


def test_streamlit_admin_can_create_well_in_temp_json(
    data_paths,
    monkeypatch,
) -> None:
    _, wells_path = data_paths
    app = run_app_with_temp_data(data_paths, monkeypatch)
    login_as_admin(app)

    app.text_input[0].set_value("well_ui")
    app.text_input[1].set_value("Скв. UI")
    app.text_input[2].set_value("Тестовый куст")
    app.text_input[3].set_value("БУ-ТЕСТ")
    click_button(app, "Создать")

    saved = load_wells_doc(wells_path)
    created = well_by_id(saved)["well_ui"]
    assert created.name == "Скв. UI"
    assert created.current_node_id == "input_geo_license"
    assert created.metadata == {"field": "Тестовый куст", "rig": "БУ-ТЕСТ"}


def test_streamlit_admin_handles_no_active_wells(data_paths, monkeypatch) -> None:
    _, wells_path = data_paths
    payload = json.loads(wells_path.read_text(encoding="utf-8"))
    for well in payload["wells"]:
        well["is_archived"] = True
    wells_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    app = run_app_with_temp_data(data_paths, monkeypatch)
    login_as_admin(app)

    assert any(item.value == "Активных скважин пока нет." for item in app.caption)
    assert "Продвинуть" not in {button.label for button in app.button}
