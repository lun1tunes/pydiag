from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pydiag.domain import well_by_id
from pydiag.infrastructure import load_wells_doc
from pydiag.infrastructure.flow_source_graph import (
    dump_structured_yaml_payload,
    load_structured_payload,
)

APP_PATH = Path(__file__).resolve().parents[2] / "app.py"
FIXTURE_SOURCE_PATH = APP_PATH.parent / "tests" / "fixtures" / "flow_source.yaml"


def run_app_with_temp_data(
    data_paths: tuple[Path, Path],
    monkeypatch,
    *,
    configure_admin: bool = True,
) -> AppTest:
    graph_path, wells_path = data_paths
    monkeypatch.setenv("PYDIAG_GRAPH_PATH", str(graph_path))
    monkeypatch.setenv("PYDIAG_SOURCE_GRAPH_PATH", str(FIXTURE_SOURCE_PATH))
    monkeypatch.setenv("PYDIAG_WELLS_PATH", str(wells_path))
    monkeypatch.setenv("PYDIAG_DISABLE_STREAMLIT_SECRETS", "1")
    monkeypatch.delenv("PYDIAG_ALLOW_INSECURE_ADMIN", raising=False)
    monkeypatch.delenv("PYDIAG_ADMIN_PASSWORD", raising=False)
    if configure_admin:
        monkeypatch.setenv(
            "PYDIAG_AUTH_USERS_JSON",
            json.dumps(
                {
                    "planner": {
                        "password": "test-admin",
                        "name": "Иван Планировщик",
                    }
                },
                ensure_ascii=False,
            ),
        )
    else:
        monkeypatch.delenv("PYDIAG_AUTH_USERS_JSON", raising=False)

    app = AppTest.from_file(str(APP_PATH))
    app.run(timeout=30)
    assert not app.exception
    return app


def login_as_admin(app: AppTest) -> AppTest:
    set_text_input(app, "Пользователь", "planner")
    set_text_input(app, "Пароль", "test-admin")
    app.button[0].click().run(timeout=30)
    assert not app.exception
    return app


def set_text_input(app: AppTest, label: str, value: str) -> AppTest:
    for item in app.text_input:
        if item.label == label:
            item.set_value(value).run(timeout=30)
            assert not app.exception
            return app
    raise AssertionError(f"Text input not found: {label}")


def click_button(app: AppTest, label: str) -> AppTest:
    for button in app.button:
        if button.label == label:
            button.click().run(timeout=30)
            assert not app.exception
            return app
    raise AssertionError(f"Button not found: {label}")


def test_streamlit_app_renders_default_workspace(data_paths, monkeypatch) -> None:
    app = run_app_with_temp_data(data_paths, monkeypatch)

    assert not any("Карта планирования и бурения" in item.value for item in app.markdown)
    assert not any(
        "Скважины привязаны к этапам процесса через current_node_id" in item.value
        for item in app.markdown
    )
    assert any("Легенда" in item.value for item in app.markdown)
    assert any("Типы блоков" in item.value for item in app.markdown)
    assert any("Цвета ответственных" in item.value for item in app.markdown)
    assert app.info[0].value == "Выберите узел, связь или фишку скважины на схеме."


def test_streamlit_app_requires_explicit_users(data_paths, monkeypatch) -> None:
    app = run_app_with_temp_data(data_paths, monkeypatch, configure_admin=False)

    assert any("Пользователи не настроены" in item.value for item in app.warning)
    labels = {button.label for button in app.button}
    assert {"Войти", "Перечитать данные"} <= labels
    assert "Продвинуть" not in labels


def test_streamlit_admin_login_reveals_management_panel(
    data_paths,
    monkeypatch,
) -> None:
    app = run_app_with_temp_data(data_paths, monkeypatch)

    login_as_admin(app)

    assert any("Пользователь: Иван Планировщик" in item.value for item in app.success)
    assert any(item.value == "Режим управления активен" for item in app.caption)
    assert {button.label for button in app.button} >= {
        "Продвинуть",
        "Откатить",
        "Удалить скважину",
        "Создать",
    }


def test_streamlit_admin_can_move_well_without_touching_real_wells_file(
    data_paths,
    monkeypatch,
) -> None:
    _, wells_path = data_paths
    initial_version = load_wells_doc(wells_path).version
    app = run_app_with_temp_data(data_paths, monkeypatch)
    login_as_admin(app)

    click_button(app, "Продвинуть")

    saved = load_wells_doc(wells_path)
    well = well_by_id(saved)["well_1001"]
    assert saved.version == initial_version + 1
    assert well.current_node_id == "dec_data_complete"
    assert well.history[-1].action == "move"


def test_streamlit_admin_can_create_well_in_temp_wells_file(
    data_paths,
    monkeypatch,
) -> None:
    _, wells_path = data_paths
    app = run_app_with_temp_data(data_paths, monkeypatch)
    login_as_admin(app)

    set_text_input(app, "ID", "well_ui")
    set_text_input(app, "Название", "Скв. UI")
    set_text_input(app, "Месторождение / куст", "Тестовый куст")
    set_text_input(app, "Буровая", "БУ-ТЕСТ")
    click_button(app, "Создать")

    saved = load_wells_doc(wells_path)
    created = well_by_id(saved)["well_ui"]
    assert created.name == "Скв. UI"
    assert created.current_node_id == "input_geo_license"
    assert created.metadata == {"field": "Тестовый куст", "rig": "БУ-ТЕСТ"}


def test_streamlit_admin_handles_no_active_wells(data_paths, monkeypatch) -> None:
    _, wells_path = data_paths
    payload = load_structured_payload(wells_path.read_bytes())
    for well in payload["wells"]:
        well["is_archived"] = True
    wells_path.write_text(dump_structured_yaml_payload(payload), encoding="utf-8")

    app = run_app_with_temp_data(data_paths, monkeypatch)
    login_as_admin(app)

    assert any(item.value == "Активных скважин пока нет." for item in app.caption)
    assert "Продвинуть" not in {button.label for button in app.button}
