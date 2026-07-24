"""Guards: canvas edits never app-remount; drag path stays cheap."""

from __future__ import annotations

from pathlib import Path

from pydiag.rendering.flow_canvas_component import ASSETS_DIR

RUNTIME_PATH = Path(__file__).resolve().parents[2] / "src/pydiag/presentation/runtime.py"


def _asset_text(name: str) -> str:
    return (ASSETS_DIR / name).read_text(encoding="utf-8")


def test_drag_hot_path_skips_expensive_global_work() -> None:
    js = _asset_text("flow_canvas.js")

    # Incident edges only while dragging (not every edge on the board).
    assert "function updateEdgeGeometry(state, nodeIds = null)" in js
    assert "updateEdgeGeometry(state, state.draggingNodeIds);" in js
    assert "updateEdgeGeometry(state, [state.draggingNodeId]);" in js

    # Process frames sync once per frame, not once per dragged card.
    drag_fn = js[js.index("function updateDraggedNode(state, nodeId)") :]
    drag_fn = drag_fn[: drag_fn.index("\nfunction ")]
    assert "syncProcessFrames" not in drag_fn

    # Note collision layout skipped mid-drag.
    assert "if (!dragging) {" in js
    assert "layoutAllNodeNotes(state);" in js

    # Pan/zoom must not re-dim every node/edge every RAF.
    assert "renderedFilterDimSignature" in js
    assert "if (state.renderedFilterDimSignature === signature)" in js


def test_inspector_persist_wrappers_use_fragment_scope() -> None:
    """Inspector shares the workspace fragment — never app-remount the canvas host."""
    text = RUNTIME_PATH.read_text(encoding="utf-8")
    assert "persist_graph_source_node_update=lambda graph, command:" in text
    assert "persist_graph_source_node_update=session.save_graph_source_node," not in text
    assert "persist_graph_source_edge_update=session.save_graph_source_edge," not in text
    assert "persist_graph_source_edge_create=session.create_graph_source_edge," not in text

    # Node/edge wrappers must be quiet (fragment scope).
    node_wrap_start = text.index("persist_graph_source_node_update=lambda graph, command:")
    node_wrap = text[node_wrap_start : node_wrap_start + 350]
    assert "quiet=True" in node_wrap

    wells_block = text[text.index("def _persist_wells_update(") :]
    wells_block = wells_block[: wells_block.index("\n    def ")]
    assert "quiet=True" in wells_block
    assert "rerun=True" in wells_block
