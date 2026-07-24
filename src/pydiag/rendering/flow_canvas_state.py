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

    if "duration_context" in raw:
        duration_context = raw.get("duration_context")
        if duration_context is not None and not isinstance(duration_context, str):
            return None
        patch["duration_context"] = duration_context

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
        "duration_context",
        "note",
    }
    if not editable_keys.intersection(patch):
        return None
    return patch


CANVAS_EDGE_EDIT_KINDS = frozenset({"default", "yes", "no", "dashed"})


def component_pending_node_edits_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return validated bulk canvas node edits: {request_id?, node_ids, patch}."""
    if component_state is None:
        return None
    raw = component_state.get("pending_node_edits")
    if not isinstance(raw, Mapping):
        return None
    node_ids_raw = raw.get("node_ids")
    if not isinstance(node_ids_raw, list) or not node_ids_raw:
        return None
    node_ids = [item for item in node_ids_raw if isinstance(item, str) and item]
    known = {node.id for node in graph.nodes}
    node_ids = [node_id for node_id in node_ids if node_id in known]
    if not node_ids:
        return None

    nested = raw.get("patch")
    sample_fields: Mapping[str, Any]
    if isinstance(nested, Mapping):
        sample_fields = nested
    else:
        sample_fields = {
            key: value
            for key, value in raw.items()
            if key not in {"node_ids", "request_id", "patch"}
        }
    sample = dict(sample_fields)
    sample["node_id"] = node_ids[0]
    validated = component_pending_node_edit_from_state(
        graph, {"pending_node_edit": sample}
    )
    if validated is None:
        return None
    patch = dict(validated)
    patch.pop("node_id", None)
    patch.pop("request_id", None)
    result: dict[str, Any] = {"node_ids": node_ids, "patch": patch}
    request_id = raw.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        result["request_id"] = request_id.strip()
    return result


def component_pending_edge_edits_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return validated bulk canvas edge edits: {request_id?, edge_ids, patch}."""
    if component_state is None:
        return None
    raw = component_state.get("pending_edge_edits")
    if not isinstance(raw, Mapping):
        return None
    edge_ids_raw = raw.get("edge_ids")
    if not isinstance(edge_ids_raw, list) or not edge_ids_raw:
        return None
    edge_ids = [item for item in edge_ids_raw if isinstance(item, str) and item]
    known = {edge.id for edge in graph.edges}
    edge_ids = [edge_id for edge_id in edge_ids if edge_id in known]
    if not edge_ids:
        return None

    nested = raw.get("patch")
    if isinstance(nested, Mapping):
        sample_fields = nested
    else:
        sample_fields = {
            key: value
            for key, value in raw.items()
            if key not in {"edge_ids", "request_id", "patch"}
        }
    sample = dict(sample_fields)
    sample["edge_id"] = edge_ids[0]
    validated = component_pending_edge_edit_from_state(
        graph, {"pending_edge_edit": sample}
    )
    if validated is None:
        return None
    patch = dict(validated)
    patch.pop("edge_id", None)
    patch.pop("request_id", None)
    result: dict[str, Any] = {"edge_ids": edge_ids, "patch": patch}
    request_id = raw.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        result["request_id"] = request_id.strip()
    return result


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


def component_pending_node_create_from_state(
    component_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return validated create-node request from canvas state."""
    if component_state is None:
        return None
    raw = component_state.get("pending_node_create")
    if not isinstance(raw, Mapping):
        return None
    title = raw.get("title")
    kind = raw.get("kind", "process")
    if not isinstance(title, str) or not title.strip():
        return None
    if kind not in CANVAS_NODE_EDIT_KINDS:
        kind = "process"
    layout_x = raw.get("layout_x")
    layout_y = raw.get("layout_y")
    layout_w = raw.get("layout_w", 280)
    layout_h = raw.get("layout_h", 72)
    if not isinstance(layout_x, int | float) or not isinstance(layout_y, int | float):
        return None
    if not isinstance(layout_w, int | float) or not isinstance(layout_h, int | float):
        return None
    result: dict[str, Any] = {
        "title": " ".join(title.split()).strip(),
        "kind": kind,
        "layout_x": round(float(layout_x), 2),
        "layout_y": round(float(layout_y), 2),
        "layout_w": int(layout_w),
        "layout_h": int(layout_h),
    }
    request_id = raw.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        result["request_id"] = request_id.strip()

    if "responsible" in raw:
        responsible = raw.get("responsible")
        if responsible is not None and not isinstance(responsible, str):
            return None
        result["responsible"] = responsible
    if "participants" in raw:
        participants = raw.get("participants")
        if participants is not None:
            if not isinstance(participants, list) or not all(
                isinstance(item, str) for item in participants
            ):
                return None
            result["participants"] = list(participants)
    if "duration" in raw:
        duration = raw.get("duration")
        if duration is not None and not isinstance(duration, str):
            return None
        result["duration"] = duration
    if "duration_context" in raw:
        duration_context = raw.get("duration_context")
        if duration_context is not None and not isinstance(duration_context, str):
            return None
        result["duration_context"] = duration_context
    if "note" in raw:
        note = raw.get("note")
        if note is not None and not isinstance(note, str):
            return None
        result["note"] = note
    return result


def component_pending_node_creates_from_state(
    component_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return validated bulk create-node request: {request_id?, nodes:[...]}."""
    if component_state is None:
        return None
    raw = component_state.get("pending_node_creates")
    if not isinstance(raw, Mapping):
        return None
    nodes_raw = raw.get("nodes")
    if not isinstance(nodes_raw, list) or not nodes_raw:
        return None
    nodes: list[dict[str, Any]] = []
    for item in nodes_raw:
        if not isinstance(item, Mapping):
            return None
        parsed = component_pending_node_create_from_state(
            {"pending_node_create": dict(item)}
        )
        if parsed is None:
            return None
        parsed.pop("request_id", None)
        nodes.append(parsed)
    result: dict[str, Any] = {"nodes": nodes}
    request_id = raw.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        result["request_id"] = request_id.strip()
    return result


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


def component_pending_process_create_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return validated {title, member_ids, request_id?} process create."""
    if component_state is None:
        return None
    raw = component_state.get("pending_process_create")
    if not isinstance(raw, Mapping):
        return None
    title = raw.get("title")
    if not isinstance(title, str) or not title.strip():
        return None
    member_ids_raw = raw.get("member_ids")
    if not isinstance(member_ids_raw, list) or not member_ids_raw:
        return None
    known = {node.id for node in graph.nodes}
    member_ids = [
        item for item in member_ids_raw if isinstance(item, str) and item in known
    ]
    if not member_ids:
        return None
    result: dict[str, Any] = {
        "title": " ".join(title.split()).strip(),
        "member_ids": member_ids,
    }
    request_id = raw.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        result["request_id"] = request_id.strip()
    return result


def component_pending_process_edit_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return validated process edit: process_id + optional title/member_ids."""
    if component_state is None:
        return None
    raw = component_state.get("pending_process_edit")
    if not isinstance(raw, Mapping):
        return None
    process_id = raw.get("process_id")
    if not isinstance(process_id, str) or not process_id:
        return None
    if process_id not in graph.processes:
        return None
    result: dict[str, Any] = {"process_id": process_id}
    if "title" in raw:
        title = raw.get("title")
        if not isinstance(title, str) or not title.strip():
            return None
        result["title"] = " ".join(title.split()).strip()
    if "member_ids" in raw:
        member_ids_raw = raw.get("member_ids")
        if not isinstance(member_ids_raw, list):
            return None
        known = {node.id for node in graph.nodes}
        result["member_ids"] = [
            item for item in member_ids_raw if isinstance(item, str) and item in known
        ]
    if "title" not in result and "member_ids" not in result:
        return None
    request_id = raw.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        result["request_id"] = request_id.strip()
    return result


def component_pending_process_delete_from_state(
    graph: FlowGraphDocument,
    component_state: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    """Return validated {process_id, request_id?} process delete."""
    if component_state is None:
        return None
    raw = component_state.get("pending_process_delete")
    if not isinstance(raw, Mapping):
        return None
    process_id = raw.get("process_id")
    if not isinstance(process_id, str) or not process_id:
        return None
    if process_id not in graph.processes:
        return None
    result: dict[str, Any] = {"process_id": process_id}
    request_id = raw.get("request_id")
    if isinstance(request_id, str) and request_id.strip():
        result["request_id"] = request_id.strip()
    return result
