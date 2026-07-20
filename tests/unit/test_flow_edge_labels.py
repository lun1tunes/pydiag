from __future__ import annotations

from pydiag.rendering.flow_edge_labels import fallback_edge_label_position
from pydiag.rendering.flow_route_geometry import NodeGeometry


def _geometry() -> NodeGeometry:
    return NodeGeometry(
        id="node",
        index=0,
        x=100.0,
        y=200.0,
        width=180,
        height=64,
        row=0,
        visual_col=0,
    )


def test_fallback_edge_label_position_resolves_ports_without_source_side() -> None:
    # Regression: missing node_ports import used to raise NameError here.
    x, y = fallback_edge_label_position(_geometry(), label_width=80, layout_mode="custom", edge_kind="yes")
    assert isinstance(x, float)
    assert isinstance(y, float)


def test_fallback_edge_label_position_honors_explicit_source_side() -> None:
    x, y = fallback_edge_label_position(
        _geometry(),
        label_width=80,
        layout_mode="custom",
        edge_kind="no",
        source_side="left",
    )
    assert x < 100.0
    assert isinstance(y, float)
