from __future__ import annotations

from typing import Any, Literal

try:
    from streamlit_flow.elements import StreamlitFlowEdge, StreamlitFlowNode
except ImportError:  # pragma: no cover - compatibility for the local canvas runtime

    class StreamlitFlowNode:
        def __init__(
            self,
            id: str,
            pos: tuple[float, float],
            data: dict[str, object],
            node_type: Literal["default", "input", "output"] = "default",
            source_position: Literal["bottom", "top", "left", "right"] = "bottom",
            target_position: Literal["bottom", "top", "left", "right"] = "top",
            hidden: bool = False,
            selected: bool = False,
            dragging: bool = False,
            draggable: bool = True,
            selectable: bool = False,
            connectable: bool = False,
            resizing: bool = False,
            deletable: bool = False,
            z_index: float = 0,
            focusable: bool = True,
            style: dict[str, object] | None = None,
            **kwargs: Any,
        ) -> None:
            style = dict(style or {})
            style.setdefault("width", "auto")
            style.setdefault("height", "auto")
            self.id = id
            self.position = {"x": pos[0], "y": pos[1]}
            self.data = data
            self.type = node_type
            self.source_position = source_position
            self.target_position = target_position
            self.hidden = hidden
            self.selected = selected
            self.dragging = dragging
            self.draggable = draggable
            self.selectable = selectable
            self.connectable = connectable
            self.resizing = resizing
            self.deletable = deletable
            self.z_index = z_index
            self.focusable = focusable
            self.style = style
            self.kwargs = kwargs

        def asdict(self) -> dict[str, object]:
            payload = {
                "id": self.id,
                "position": self.position,
                "data": self.data,
                "type": self.type,
                "sourcePosition": self.source_position,
                "targetPosition": self.target_position,
                "hidden": self.hidden,
                "selected": self.selected,
                "dragging": self.dragging,
                "draggable": self.draggable,
                "selectable": self.selectable,
                "connectable": self.connectable,
                "resizing": self.resizing,
                "deletable": self.deletable,
                "zIndex": self.z_index,
                "focusable": self.focusable,
                "style": self.style,
            }
            payload.update(self.kwargs)
            return payload

    class StreamlitFlowEdge:
        def __init__(
            self,
            id: str,
            source: str,
            target: str,
            edge_type: Literal[
                "default", "straight", "step", "smoothstep", "simplebezier"
            ] = "default",
            marker_start: dict[str, object] | None = None,
            marker_end: dict[str, object] | None = None,
            hidden: bool = False,
            animated: bool = False,
            selected: bool = False,
            deletable: bool = False,
            focusable: bool = False,
            z_index: float = 0,
            label: str = "",
            label_style: dict[str, object] | None = None,
            label_show_bg: bool = False,
            label_bg_style: dict[str, object] | None = None,
            style: dict[str, object] | None = None,
            **kwargs: Any,
        ) -> None:
            self.id = id
            self.source = source
            self.target = target
            self.type = edge_type
            self.marker_start = marker_start or {}
            self.marker_end = marker_end or {}
            self.hidden = hidden
            self.animated = animated
            self.selected = selected
            self.deletable = deletable
            self.focusable = focusable
            self.z_index = z_index
            self.label = label
            self.label_style = label_style or {}
            self.label_show_bg = label_show_bg
            self.label_bg_style = label_bg_style or {}
            self.style = style or {}
            self.kwargs = kwargs

        def asdict(self) -> dict[str, object]:
            payload = {
                "id": self.id,
                "source": self.source,
                "target": self.target,
                "type": self.type,
                "markerStart": self.marker_start,
                "markerEnd": self.marker_end,
                "hidden": self.hidden,
                "animated": self.animated,
                "selected": self.selected,
                "deletable": self.deletable,
                "focusable": self.focusable,
                "zIndex": self.z_index,
                "label": self.label,
                "labelStyle": self.label_style,
                "labelShowBg": self.label_show_bg,
                "labelBgStyle": self.label_bg_style,
                "style": self.style,
            }
            payload.update(self.kwargs)
            return payload


__all__ = [
    "StreamlitFlowEdge",
    "StreamlitFlowNode",
]
