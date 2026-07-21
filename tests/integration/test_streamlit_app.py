from __future__ import annotations

import json
from pathlib import Path

from streamlit.testing.v1 import AppTest

from pydiag.domain import well_by_id
from pydiag.infrastructure import load_wells_doc, materialize_flow_graph_from_source
from pydiag.infrastructure.flow_source_graph import (
    dump_structured_yaml_payload,
    load_structured_payload,
)

APP_PATH = Path(__file__).resolve().parents[2] / "app.py"
FIXTURE_SOURCE_PATH = APP_PATH.parent / "tests" / "fixtures" / "flow_source.yaml"
FIXTURE_WELLS_PATH = APP_PATH.parent / "tests" / "fixtures" / "wells.yaml"


def run_app_with_temp_data(
    data_paths: tuple[Path, Path],
    monkeypatch,
    *,
    configure_admin: bool = True,
    source_path: Path | None = None,
) -> AppTest:
    graph_path, wells_path = data_paths
    monkeypatch.setenv("PYDIAG_GRAPH_PATH", str(graph_path))
    monkeypatch.setenv("PYDIAG_SOURCE_GRAPH_PATH", str(source_path or FIXTURE_SOURCE_PATH))
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


def set_number_input(app: AppTest, label: str, value: float | int) -> AppTest:
    for item in app.number_input:
        if item.label == label:
            item.set_value(value).run(timeout=30)
            assert not app.exception
            return app
    raise AssertionError(f"Number input not found: {label}")


def click_button(app: AppTest, label: str) -> AppTest:
    for button in app.button:
        if button.label == label:
            button.click().run(timeout=30)
            assert not app.exception
            return app
    raise AssertionError(f"Button not found: {label}")


def set_selectbox(app: AppTest, label: str, value: str) -> AppTest:
    for item in app.selectbox:
        if item.label == label:
            item.set_value(value).run(timeout=30)
            assert not app.exception
            return app
    raise AssertionError(f"Selectbox not found: {label}")


def set_toggle(app: AppTest, label: str, value: bool) -> AppTest:
    for item in app.toggle:
        if item.label == label:
            item.set_value(value).run(timeout=30)
            assert not app.exception
            return app
    raise AssertionError(f"Toggle not found: {label}")


def set_checkbox(app: AppTest, label: str, value: bool) -> AppTest:
    for item in app.checkbox:
        if item.label == label:
            item.set_value(value).run(timeout=30)
            assert not app.exception
            return app
    raise AssertionError(f"Checkbox not found: {label}")


def prepare_temp_workspace(tmp_path: Path) -> tuple[Path, Path, Path]:
    graph_path = tmp_path / "flow_graph.json"
    wells_path = tmp_path / "wells.yaml"
    source_dir = tmp_path / "flow_sources"
    source_dir.mkdir()
    source_path = source_dir / "flow_source.yaml"
    source_path.write_bytes(FIXTURE_SOURCE_PATH.read_bytes())
    wells_path.write_bytes(FIXTURE_WELLS_PATH.read_bytes())
    materialize_flow_graph_from_source(source_path=source_path, target_path=graph_path)
    return graph_path, wells_path, source_path


def test_streamlit_app_renders_default_workspace(data_paths, monkeypatch) -> None:
    app = run_app_with_temp_data(data_paths, monkeypatch)

    assert not any(
        "Схема планирования и строительства скважин" in item.value for item in app.markdown
    )
    assert not any(
        "Скважины привязаны к этапам процесса через current_node_id" in item.value
        for item in app.markdown
    )
    assert any("Типы блоков" in item.value for item in app.markdown)
    assert not any("Цвета ответственных" in item.value for item in app.markdown)
    assert not app.info


def test_streamlit_app_requires_explicit_users(data_paths, monkeypatch) -> None:
    app = run_app_with_temp_data(data_paths, monkeypatch, configure_admin=False)

    assert any("Пользователи не настроены" in item.value for item in app.warning)
    labels = {button.label for button in app.button}
    assert {"Войти", "Обновить данные"} <= labels
    assert "Продвинуть" not in labels


def test_streamlit_admin_login_reveals_management_panel(
    data_paths,
    monkeypatch,
) -> None:
    app = run_app_with_temp_data(data_paths, monkeypatch)

    login_as_admin(app)

    assert any("Пользователь: Иван Планировщик" in item.value for item in app.success)
    assert any(item.value == "Права: Админ" for item in app.caption)
    assert not any(item.value == "Режим управления активен" for item in app.caption)
    assert not any(str(item.value).startswith("Логин:") for item in app.caption)
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


def test_streamlit_admin_can_create_well_with_empty_optional_metadata(
    data_paths,
    monkeypatch,
) -> None:
    _, wells_path = data_paths
    app = run_app_with_temp_data(data_paths, monkeypatch)
    login_as_admin(app)

    set_text_input(app, "ID", "well_ui_bare")
    set_text_input(app, "Название", "Скв. Bare")
    click_button(app, "Создать")

    assert not app.exception
    assert not [item.value for item in app.error]
    saved = load_wells_doc(wells_path)
    created = well_by_id(saved)["well_ui_bare"]
    assert created.name == "Скв. Bare"
    assert created.metadata == {}
    # Empty metadata must round-trip through YAML as {}, not null.
    assert "metadata: {}" in wells_path.read_text(encoding="utf-8")


def test_streamlit_admin_handles_no_active_wells(data_paths, monkeypatch) -> None:
    _, wells_path = data_paths
    payload = load_structured_payload(wells_path.read_bytes())
    for well in payload["wells"]:
        well["is_archived"] = True
    wells_path.write_text(dump_structured_yaml_payload(payload), encoding="utf-8")

    app = run_app_with_temp_data(data_paths, monkeypatch)
    login_as_admin(app)

    captions = {item.value for item in app.caption}
    assert (
        "Активных скважин пока нет" in captions
        or "Активных скважин нет" in captions
    )
    assert "Продвинуть" not in {button.label for button in app.button}


def test_streamlit_app_switches_graph_versions_from_source_selector(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)
    version_path = source_path.parent / "flow_source.v0001.yaml"
    payload = load_structured_payload(FIXTURE_SOURCE_PATH.read_bytes())
    payload["nodes"]["proc_initial_review"]["title"] = "Архивная версия карточки"
    version_path.write_text(
        dump_structured_yaml_payload(payload),
        encoding="utf-8",
    )

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        configure_admin=False,
        source_path=source_path,
    )
    app.session_state["selected_id"] = "proc_initial_review"
    app.run(timeout=30)
    assert not app.exception

    set_selectbox(app, "Версия схемы", "flow_source.v0001.yaml")

    assert any("Архивная версия карточки" in item.value for item in app.markdown)


def test_streamlit_admin_can_edit_older_archived_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)
    older = source_path.parent / "flow_source.v0001.yaml"
    newer = source_path.parent / "flow_source.v0002.yaml"
    older.write_bytes(source_path.read_bytes())
    newer.write_bytes(source_path.read_bytes())

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    login_as_admin(app)

    set_selectbox(app, "Версия схемы", "flow_source.v0001.yaml")
    app.session_state["selected_id"] = "proc_initial_review"
    app.run(timeout=30)
    assert not app.exception

    texts = [
        getattr(item, "value", "")
        for item in [*app.caption, *app.markdown, *app.info, *app.warning]
        if getattr(item, "value", None)
    ]
    assert not any("только для просмотра" in text.lower() for text in texts)
    assert not any(
        "Правки доступны в «Текущая» или в новейшей версии" in text
        or "Правки доступны только в текущей схеме" in text
        for text in texts
    )

    set_text_input(app, "Заголовок", "Older archive editable")
    click_button(app, "Сохранить")

    saved = load_structured_payload(older.read_bytes())
    assert saved["nodes"]["proc_initial_review"]["title"] == "Older archive editable"
    # Newer archive and live must stay untouched.
    newer_saved = load_structured_payload(newer.read_bytes())
    assert newer_saved["nodes"]["proc_initial_review"]["title"] != "Older archive editable"
    live_saved = load_structured_payload(source_path.read_bytes())
    assert live_saved["nodes"]["proc_initial_review"]["title"] != "Older archive editable"


def test_streamlit_admin_can_edit_newest_archive_even_when_live_exists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)
    (source_path.parent / "flow_source.v0001.yaml").write_bytes(source_path.read_bytes())
    newest = source_path.parent / "flow_source.v0002.yaml"
    newest.write_bytes(source_path.read_bytes())

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    login_as_admin(app)

    set_selectbox(app, "Версия схемы", "flow_source.v0002.yaml")
    app.session_state["selected_id"] = "proc_initial_review"
    app.run(timeout=30)
    assert not app.exception

    texts = [
        getattr(item, "value", "")
        for item in [*app.caption, *app.markdown]
        if getattr(item, "value", None)
    ]
    assert not any("только для просмотра" in text.lower() for text in texts)

    set_text_input(app, "Заголовок", "Newest archive editable")
    click_button(app, "Сохранить")

    saved = load_structured_payload(newest.read_bytes())
    assert saved["nodes"]["proc_initial_review"]["title"] == "Newest archive editable"
    # Live file must stay untouched.
    live = load_structured_payload(source_path.read_bytes())
    assert live["nodes"]["proc_initial_review"]["title"] != "Newest archive editable"


def test_streamlit_admin_can_save_source_layout_to_flow_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    login_as_admin(app)

    set_toggle(app, "Редактировать положение", True)
    app.session_state["position_edit_positions"] = {"proc_initial_review": (733.5, 412.25)}
    app.run(timeout=30)
    assert not app.exception
    click_button(app, "Сохранить")

    saved = load_structured_payload(source_path.read_bytes())
    assert saved["layout"]["proc_initial_review"] == {
        "x": 733.5,
        "y": 412.25,
        "w": 300,
        "h": 116,
    }
    assert "custom_layout" not in saved or "proc_initial_review" not in saved.get(
        "custom_layout",
        {},
    )


def test_streamlit_admin_can_soft_delete_selected_flow_source_node(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    app.session_state["selected_id"] = "db_offset_wells"
    app.run(timeout=30)
    assert not app.exception
    login_as_admin(app)

    set_checkbox(app, "Подтвердить удаление карточки", True)
    click_button(app, "Удалить карточку")

    saved = load_structured_payload(source_path.read_bytes())
    assert saved["nodes"]["db_offset_wells"]["deleted"] is True
    assert "db_offset_wells" not in {node.id for node in app.session_state["graph_doc"].nodes}
    assert "e_offsets_review" not in {edge.id for edge in app.session_state["graph_doc"].edges}


def test_streamlit_admin_card_layout_fields_follow_position_edit_draft(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    app.session_state["selected_id"] = "proc_initial_review"
    app.run(timeout=30)
    assert not app.exception
    login_as_admin(app)

    assert "Применить положение" not in {button.label for button in app.button}
    assert not any(item.label == "Положение" for item in getattr(app, "expander", []))

    set_toggle(app, "Редактировать положение", True)
    positions = dict(app.session_state["position_edit_positions"])
    positions["proc_initial_review"] = (733.5, 412.25)
    app.session_state["position_edit_positions"] = positions
    app.session_state["position_edit_dirty"] = True
    app.run(timeout=30)
    assert not app.exception

    assert app.session_state["graph_source_node_layout_x::proc_initial_review"] == 733.5
    assert app.session_state["graph_source_node_layout_y::proc_initial_review"] == 412.25
    saved = load_structured_payload(source_path.read_bytes())
    assert "custom_layout" not in saved or "proc_initial_review" not in saved.get(
        "custom_layout", {}
    )


def test_streamlit_admin_can_edit_selected_flow_source_node(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    app.session_state["selected_id"] = "proc_initial_review"
    app.run(timeout=30)
    login_as_admin(app)

    set_text_input(app, "Заголовок", "UI updated node")
    set_number_input(app, "X", 444.5)
    set_number_input(app, "Y", 222.25)
    set_selectbox(app, "Ответственный", "completion")
    click_button(app, "Сохранить")

    saved = load_structured_payload(source_path.read_bytes())
    assert saved["nodes"]["proc_initial_review"]["title"] == "UI updated node"
    assert saved["nodes"]["proc_initial_review"]["responsible"] == "completion"
    assert saved["layout"]["proc_initial_review"]["x"] == 444.5
    assert saved["layout"]["proc_initial_review"]["y"] == 222.25


def test_streamlit_admin_can_rename_card_without_touching_coordinates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)
    original = load_structured_payload(source_path.read_bytes())
    original_layout = original["layout"]["proc_initial_review"]

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    app.session_state["selected_id"] = "proc_initial_review"
    app.run(timeout=30)
    login_as_admin(app)

    set_text_input(app, "Заголовок", "Only title changed")
    click_button(app, "Сохранить")

    saved = load_structured_payload(source_path.read_bytes())
    assert saved["nodes"]["proc_initial_review"]["title"] == "Only title changed"
    assert saved["layout"]["proc_initial_review"]["x"] == original_layout["x"]
    assert saved["layout"]["proc_initial_review"]["y"] == original_layout["y"]


def test_streamlit_admin_can_edit_selected_flow_source_edge(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    app.session_state["selected_id"] = "e_review_decision"
    app.run(timeout=30)
    login_as_admin(app)

    set_selectbox(app, "Тип связи", "dashed")
    click_button(app, "Сохранить связь")

    saved = load_structured_payload(source_path.read_bytes())
    transition = saved["nodes"]["proc_initial_review"]["transitions"][0]
    assert transition["to"] == "dec_data_complete"
    assert transition["kind"] == "dashed"


def test_streamlit_admin_can_delete_selected_flow_source_edge(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    app.session_state["selected_id"] = "e_review_decision"
    app.run(timeout=30)
    login_as_admin(app)

    set_checkbox(app, "Подтвердить удаление связи", True)
    click_button(app, "Удалить связь")

    saved = load_structured_payload(source_path.read_bytes())
    transition_ids = [
        item.get("id")
        for item in saved["nodes"]["proc_initial_review"].get("transitions", [])
    ]
    assert "e_review_decision" not in transition_ids
    assert "selected_id" not in app.session_state or (
        app.session_state["selected_id"] != "e_review_decision"
    )


def test_streamlit_admin_can_create_edge_from_selected_card(
    tmp_path: Path,
    monkeypatch,
) -> None:
    graph_path, wells_path, source_path = prepare_temp_workspace(tmp_path)
    before = load_structured_payload(source_path.read_bytes())
    before_count = len(before["nodes"]["proc_initial_review"].get("transitions", []))

    app = run_app_with_temp_data(
        (graph_path, wells_path),
        monkeypatch,
        source_path=source_path,
    )
    app.session_state["selected_id"] = "proc_initial_review"
    app.run(timeout=30)
    login_as_admin(app)

    assert any(
        "Связи" in getattr(item, "value", "")
        for item in app.markdown
        if getattr(item, "value", None)
    )

    create_prefix = "graph_source_edge_create::proc_initial_review_"
    target_box = next(
        item
        for item in app.selectbox
        if getattr(item, "key", None) == f"{create_prefix}target"
    )
    kind_box = next(
        item
        for item in app.selectbox
        if getattr(item, "key", None) == f"{create_prefix}kind"
    )
    label_input = next(
        item
        for item in app.text_input
        if getattr(item, "key", None) == f"{create_prefix}label"
    )
    target_box.set_value("card_mitigation").run(timeout=30)
    assert not app.exception
    kind_box.set_value("dashed").run(timeout=30)
    assert not app.exception
    label_input.set_value("UI create").run(timeout=30)
    assert not app.exception
    click_button(app, "Добавить связь")

    saved = load_structured_payload(source_path.read_bytes())
    transitions = saved["nodes"]["proc_initial_review"]["transitions"]
    assert len(transitions) == before_count + 1
    created = transitions[-1]
    assert created["to"] == "card_mitigation"
    assert created["kind"] == "dashed"
    assert created["label"] == "UI create"
