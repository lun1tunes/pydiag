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


def test_runtime_run_splits_canvas_and_inspector_into_separate_fragments() -> None:
    source = inspect.getsource(StreamlitAppRuntime.run)

    assert "@self.st_module.fragment" in source
    assert "def render_canvas_fragment() -> None:" in source
    assert "def render_inspector_fragment() -> None:" in source
    assert "with diagram_col:" in source
    assert "render_canvas_fragment()" in source
    assert "with side_col:" in source
    assert "render_inspector_fragment()" in source
