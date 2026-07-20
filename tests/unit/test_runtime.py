from __future__ import annotations

import inspect

from pydiag.presentation.runtime import (
    CARD_LAYOUT_SYNC_TOKEN_KEY,
    StreamlitAppRuntime,
    card_layout_x_key,
    card_layout_y_key,
)


class FakeStreamlitModule:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}


class DummyDocumentsGateway:
    pass


def test_sync_card_layout_inputs_initializes_widget_values() -> None:
    st_module = FakeStreamlitModule()
    runtime = StreamlitAppRuntime(st_module, DummyDocumentsGateway())

    runtime._sync_card_layout_inputs(
        node_id="proc_initial_review",
        current_x=733.5,
        current_y=412.25,
    )

    assert st_module.session_state[card_layout_x_key("proc_initial_review")] == 733.5
    assert st_module.session_state[card_layout_y_key("proc_initial_review")] == 412.25
    assert (
        st_module.session_state[CARD_LAYOUT_SYNC_TOKEN_KEY]
        == "proc_initial_review|733.5|412.25"
    )


def test_sync_card_layout_inputs_preserves_manual_edit_until_position_changes() -> None:
    st_module = FakeStreamlitModule()
    runtime = StreamlitAppRuntime(st_module, DummyDocumentsGateway())
    node_id = "proc_initial_review"

    runtime._sync_card_layout_inputs(
        node_id=node_id,
        current_x=733.5,
        current_y=412.25,
    )
    st_module.session_state[card_layout_x_key(node_id)] = 999.99

    runtime._sync_card_layout_inputs(
        node_id=node_id,
        current_x=733.5,
        current_y=412.25,
    )

    assert st_module.session_state[card_layout_x_key(node_id)] == 999.99

    runtime._sync_card_layout_inputs(
        node_id=node_id,
        current_x=801.0,
        current_y=412.25,
    )

    assert st_module.session_state[card_layout_x_key(node_id)] == 801.0


def test_sync_card_layout_inputs_updates_when_selected_node_changes() -> None:
    st_module = FakeStreamlitModule()
    runtime = StreamlitAppRuntime(st_module, DummyDocumentsGateway())

    runtime._sync_card_layout_inputs(
        node_id="proc_initial_review",
        current_x=100.0,
        current_y=200.0,
    )
    runtime._sync_card_layout_inputs(
        node_id="dec_data_complete",
        current_x=100.0,
        current_y=200.0,
    )

    assert st_module.session_state[card_layout_x_key("dec_data_complete")] == 100.0
    assert (
        st_module.session_state[CARD_LAYOUT_SYNC_TOKEN_KEY]
        == "dec_data_complete|100.0|200.0"
    )


def test_runtime_run_keeps_canvas_and_inspector_in_one_workspace_fragment() -> None:
    source = inspect.getsource(StreamlitAppRuntime.run)

    assert "@self.st_module.fragment" in source
    assert "def render_workspace_fragment() -> None:" in source
    assert "render_workspace_fragment()" in source
    assert "consume_flow_selection_rerun_request" not in source
    assert "def render_canvas_fragment() -> None:" not in source
    assert "def render_inspector_fragment() -> None:" not in source
    # Columns must be created inside the fragment — writing widgets into
    # outer-run containers raises StreamlitFragmentWidgetsNotAllowedOutsideError.
    fragment_source = source.split("def render_workspace_fragment()", 1)[1]
    assert 'self.st_module.columns((2.3, 1.1), gap="large")' in fragment_source
    assert source.index("def render_workspace_fragment()") < source.index(
        'self.st_module.columns((2.3, 1.1), gap="large")'
    )
    assert "Ошибка отрисовки схемы:" in source
    assert "Ошибка панели инспектора:" in source
    assert "_render_layout_draft_panel" not in source
