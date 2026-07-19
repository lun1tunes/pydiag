from __future__ import annotations

import inspect

from pydiag.presentation.runtime import StreamlitAppRuntime


class FakeStreamlitModule:
    def __init__(self) -> None:
        self.session_state: dict[str, object] = {}


class DummyDocumentsGateway:
    pass


def test_sync_layout_draft_inputs_initializes_widget_values() -> None:
    st_module = FakeStreamlitModule()
    runtime = StreamlitAppRuntime(st_module, DummyDocumentsGateway())

    runtime._sync_layout_draft_inputs(
        layout_mode="manual",
        node_id="proc_initial_review",
        current_x=733.5,
        current_y=412.25,
    )

    assert (
        st_module.session_state["layout_draft_x::manual::proc_initial_review"]
        == "733.50"
    )
    assert (
        st_module.session_state["layout_draft_y::manual::proc_initial_review"]
        == "412.25"
    )


def test_sync_layout_draft_inputs_preserves_manual_edit_until_position_changes() -> None:
    st_module = FakeStreamlitModule()
    runtime = StreamlitAppRuntime(st_module, DummyDocumentsGateway())

    runtime._sync_layout_draft_inputs(
        layout_mode="manual",
        node_id="proc_initial_review",
        current_x=733.5,
        current_y=412.25,
    )
    st_module.session_state["layout_draft_x::manual::proc_initial_review"] = "999.99"

    runtime._sync_layout_draft_inputs(
        layout_mode="manual",
        node_id="proc_initial_review",
        current_x=733.5,
        current_y=412.25,
    )

    assert st_module.session_state["layout_draft_x::manual::proc_initial_review"] == "999.99"

    runtime._sync_layout_draft_inputs(
        layout_mode="manual",
        node_id="proc_initial_review",
        current_x=801.0,
        current_y=412.25,
    )

    assert st_module.session_state["layout_draft_x::manual::proc_initial_review"] == "801"


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
    assert "self.st_module.columns((2.3, 1.1), gap=\"large\")" in fragment_source
    assert source.index("def render_workspace_fragment()") < source.index(
        "self.st_module.columns((2.3, 1.1), gap=\"large\")"
    )
    assert "Ошибка отрисовки схемы:" in source
    assert "Ошибка панели инспектора:" in source
