from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from pydiag.domain.models import FlowGraphDocument, WellsDocument


def component_positions_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> dict[str, tuple[float, float]] | None:
    if component_state is None:
        return None
    raw_positions = component_state.get("positions")
    if not isinstance(raw_positions, Mapping):
        return None

    result: dict[str, tuple[float, float]] = {}
    known_ids = {node.id for node in graph.nodes}
    for node_id, value in raw_positions.items():
        if node_id not in known_ids or not isinstance(value, Mapping):
            continue
        x = value.get("x")
        y = value.get("y")
        if not isinstance(x, int | float) or not isinstance(y, int | float):
            continue
        result[node_id] = (round(float(x), 2), round(float(y), 2))
    return result or None


def component_responsible_filter_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> list[str] | None:
    if component_state is None or "responsible_filter" not in component_state:
        return None
    raw_filter = component_state.get("responsible_filter")
    if not isinstance(raw_filter, list):
        return None
    known = set(graph.responsibles)
    return [item for item in raw_filter if isinstance(item, str) and item in known]


def component_pending_edge_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    """Return a validated {source, target, kind[, request_id]} pending edge."""
    if component_state is None:
        return None
    raw = component_state.get("pending_edge")
    if not isinstance(raw, Mapping):
        return None
    source = raw.get("source")
    target = raw.get("target")
    kind = raw.get("kind", "default")
    if not isinstance(source, str) or not isinstance(target, str):
        return None
    if not source or not target or source == target:
        return None
    node_ids = {node.id for node in graph.nodes}
    if source not in node_ids or target not in node_ids:
        return None
    if kind not in {"default", "yes", "no", "dashed"}:
        kind = "default"
    result = {"source": source, "target": target, "kind": kind}
    request_id = raw.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        result["request_id"] = request_id.strip()
    return result


CANVAS_NODE_EDIT_KINDS = frozenset(
    {
        "process",
        "decision_diamond",
        "database",
        "input_data",
        "event",
    }
)


def component_pending_node_edit_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return validated pending canvas node edit patch (+ request_id)."""
    if component_state is None:
        return None
    raw = component_state.get("pending_node_edit")
    if not isinstance(raw, Mapping):
        return None
    node_id = raw.get("node_id")
    if not isinstance(node_id, str) or not node_id:
        return None
    node_ids = {node.id for node in graph.nodes}
    if node_id not in node_ids:
        return None

    patch: dict[str, Any] = {"node_id": node_id}
    request_id = raw.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        patch["request_id"] = request_id.strip()

    if raw.get("deleted") is True:
        patch["deleted"] = True
        return patch

    if "title" in raw:
        title = raw.get("title")
        if not isinstance(title, str):
            return None
        patch["title"] = title

    if "kind" in raw:
        kind = raw.get("kind")
        if kind not in CANVAS_NODE_EDIT_KINDS:
            return None
        patch["kind"] = kind

    if "responsible" in raw:
        responsible = raw.get("responsible")
        if responsible is not None and not isinstance(responsible, str):
            return None
        if isinstance(responsible, str) and responsible not in graph.responsibles:
            return None
        patch["responsible"] = responsible

    if "participants" in raw:
        participants = _role_id_list(raw.get("participants"), graph)
        if participants is None:
            return None
        patch["participants"] = participants

    if "approvers" in raw:
        approvers = _role_id_list(raw.get("approvers"), graph)
        if approvers is None:
            return None
        patch["approvers"] = approvers

    if "duration" in raw:
        duration = raw.get("duration")
        if duration is not None and not isinstance(duration, str):
            return None
        patch["duration"] = duration

    if "note" in raw:
        note = raw.get("note")
        if note is not None and not isinstance(note, str):
            return None
        patch["note"] = note

    editable_keys = {
        "title",
        "kind",
        "responsible",
        "participants",
        "approvers",
        "duration",
        "note",
    }
    if not editable_keys.intersection(patch):
        return None
    return patch


CANVAS_EDGE_EDIT_KINDS = frozenset({"default", "yes", "no", "dashed"})


def component_pending_edge_edit_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return validated pending canvas edge edit patch (+ request_id)."""
    if component_state is None:
        return None
    raw = component_state.get("pending_edge_edit")
    if not isinstance(raw, Mapping):
        return None
    edge_id = raw.get("edge_id")
    if not isinstance(edge_id, str) or not edge_id:
        return None
    edge_ids = {edge.id for edge in graph.edges}
    if edge_id not in edge_ids:
        return None

    patch: dict[str, Any] = {"edge_id": edge_id}
    request_id = raw.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        patch["request_id"] = request_id.strip()

    if raw.get("deleted") is True:
        patch["deleted"] = True
        return patch

    if "kind" in raw:
        kind = raw.get("kind")
        if kind not in CANVAS_EDGE_EDIT_KINDS:
            return None
        patch["kind"] = kind

    if "kind" not in patch:
        return None
    return patch


def _role_id_list(value: object, graph: FlowGraphDocument) -> list[str] | None:
    if not isinstance(value, list):
        return None
    result: list[str] = []
    known = set(graph.responsibles)
    for item in value:
        if not isinstance(item, str) or item not in known:
            return None
        result.append(item)
    return result


def component_history_action_from_state(
    component_state: Mapping[str, Any] | None,
) -> dict[str, str] | None:
    """Return validated {action: undo|redo, request_id} from canvas state."""
    if component_state is None:
        return None
    raw = component_state.get("history_action")
    if not isinstance(raw, Mapping):
        return None
    action = raw.get("action")
    if action not in {"undo", "redo"}:
        return None
    request_id = raw.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        return None
    return {"action": action, "request_id": request_id.strip()}


def component_selected_id_from_state(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument,
    component_state: Mapping[str, Any] | None,
) -> str | None:
    if component_state is None:
        return None
    selected_id = component_state.get("selected_id")
    if not isinstance(selected_id, str) or not selected_id:
        return None

    node_ids = {node.id for node in graph.nodes}
    edge_ids = {edge.id for edge in graph.edges}
    well_ids = {f"well::{well.id}" for well in wells_doc.wells}
    if (
        selected_id in node_ids
        or selected_id in edge_ids
        or selected_id in well_ids
        or selected_id.startswith("well-extra::")
    ):
        return selected_id
    return None


def component_view_state_from_state(
    component_state: Mapping[str, Any] | None,
) -> dict[str, float | bool] | None:
    if component_state is None:
        return None

    raw_view = component_state.get("view")
    if not isinstance(raw_view, Mapping):
        return None

    x = _finite_float(raw_view.get("x"))
    y = _finite_float(raw_view.get("y"))
    scale = _finite_float(raw_view.get("scale"))
    if x is None or y is None or scale is None:
        return None
    if scale <= 0:
        return None

    user_moved_view = component_state.get("user_moved_view")
    return {
        "x": x,
        "y": y,
        "scale": scale,
        "user_moved_view": bool(user_moved_view),
    }


def _finite_float(value: object) -> float | None:
    if not isinstance(value, int | float):
        return None
    result = round(float(value), 4)
    if not isfinite(result):
        return None
    return result
