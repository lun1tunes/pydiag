from __future__ import annotations

import copy
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydiag.infrastructure.figma_schema import FigmaConnectorNode, FigmaTextNode

DEFAULT_RESPONSIBLES: dict[str, dict[str, str]] = {
    "planning": {
        "label": "Планирование",
        "fill": "#dcecff",
        "border": "#356ca8",
        "text": "#17314f",
    },
    "geology": {
        "label": "Геология",
        "fill": "#e3f7ea",
        "border": "#3f8a55",
        "text": "#17311e",
    },
    "procurement": {
        "label": "Закупки",
        "fill": "#fff2d6",
        "border": "#b17a23",
        "text": "#43300d",
    },
    "hse": {
        "label": "ПБОТОС",
        "fill": "#ffe3e3",
        "border": "#b84c4c",
        "text": "#4e1717",
    },
    "drilling": {
        "label": "Бурение",
        "fill": "#e9e4ff",
        "border": "#6954b8",
        "text": "#261b53",
    },
    "completion": {
        "label": "Заканчивание",
        "fill": "#dff5f2",
        "border": "#16877d",
        "text": "#123834",
    },
    "logistics": {
        "label": "Логистика",
        "fill": "#edf2f7",
        "border": "#64748b",
        "text": "#253041",
    },
    "default": {
        "label": "По умолчанию",
        "fill": "#eef2f6",
        "border": "#64748b",
        "text": "#253041",
    },
}
NODE_KIND_FALLBACK = "figma_text"
EDGE_KIND_FALLBACK = "usual"
NAME_TOKEN_SPLIT_RE = re.compile(r"\s*;\s*")
IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9_.:-]+")
STRUCTURED_RESPONSIBLE_KEYS = ("responsibles", "responsible", "departments", "department_ids")
STRUCTURED_NODE_KEYS = ("flowNode", "flow_node")
STRUCTURED_EDGE_KEYS = ("flowEdge", "flow_edge")


@dataclass(frozen=True)
class FlowNodeSkeletonData:
    id: str
    kind: str
    responsible: list[str]
    time: str | None


@dataclass(frozen=True)
class FlowEdgeSkeletonData:
    id: str
    kind: str
    source: str | None
    target: str | None
    label: str | None


def build_responsibles(
    payload: object,
    flow_nodes: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    raw_responsibles = None
    if isinstance(payload, dict):
        if isinstance(payload.get("responsibles"), dict):
            raw_responsibles = payload["responsibles"]
        elif isinstance(payload.get("departments"), dict):
            raw_responsibles = payload["departments"]
    if isinstance(raw_responsibles, dict):
        for key, style in raw_responsibles.items():
            if isinstance(style, dict):
                result[str(key)] = {
                    "label": str(style.get("label") or key),
                    "fill": str(style.get("fill") or DEFAULT_RESPONSIBLES["default"]["fill"]),
                    "border": str(style.get("border") or DEFAULT_RESPONSIBLES["default"]["border"]),
                    "text": str(style.get("text") or DEFAULT_RESPONSIBLES["default"]["text"]),
                }

    for node in flow_nodes:
        for responsible in node["responsible"]:
            if responsible in result:
                continue
            if responsible in DEFAULT_RESPONSIBLES:
                result[responsible] = copy.deepcopy(DEFAULT_RESPONSIBLES[responsible])
                continue
            result[responsible] = {
                "label": responsible.replace("_", " ").strip().title() or responsible,
                "fill": DEFAULT_RESPONSIBLES["default"]["fill"],
                "border": DEFAULT_RESPONSIBLES["default"]["border"],
                "text": DEFAULT_RESPONSIBLES["default"]["text"],
            }

    if result:
        return result
    return {"default": copy.deepcopy(DEFAULT_RESPONSIBLES["default"])}


def parse_name_metadata(name: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in NAME_TOKEN_SPLIT_RE.split(name.strip()):
        if not token or "=" not in token:
            continue
        key, value = token.split("=", 1)
        result[key.strip().lower()] = value.strip()
    return result


def split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def infer_flow_node_id(node: FigmaTextNode) -> str:
    metadata = parse_name_metadata(node.name)
    raw_value = metadata.get("id") or node.id or node.characters or node.name
    return normalize_identifier(raw_value, fallback=node.id)


def infer_flow_edge_id(node: FigmaConnectorNode) -> str:
    metadata = parse_name_metadata(node.name)
    raw_value = metadata.get("id") or node.id or node.name
    return normalize_identifier(raw_value, fallback=node.id)


def infer_flow_node_kind(node: FigmaTextNode, metadata: dict[str, str]) -> str:
    del node
    return normalize_flow_node_kind(metadata.get("kind"))


def infer_flow_edge_kind(metadata: dict[str, str]) -> str:
    return normalize_flow_edge_kind(metadata.get("kind"))


def normalize_flow_node_kind(value: str | None) -> str:
    raw_kind = (value or NODE_KIND_FALLBACK).strip().lower()
    allowed = {
        "process",
        "decision_diamond",
        "decision_card",
        "database",
        "input_data",
        "event",
        "figma_text",
    }
    if raw_kind in allowed:
        return raw_kind
    return NODE_KIND_FALLBACK


def normalize_flow_edge_kind(value: str | None) -> str:
    raw_kind = (value or EDGE_KIND_FALLBACK).strip().lower()
    if raw_kind in {"usual", "yes", "no", "dashed"}:
        return raw_kind
    return EDGE_KIND_FALLBACK


def normalize_time_value(value: str | None) -> str | None:
    if not value:
        return None
    normalized = " ".join(value.strip().lower().split())
    return normalized or None


def normalize_identifier(value: str, *, fallback: str) -> str:
    normalized = IDENTIFIER_RE.sub("_", value.strip()).strip("._:-")
    if normalized:
        return normalized
    return fallback


def resolve_flow_node_data(
    node: FigmaTextNode,
    raw_item: Mapping[str, object],
) -> FlowNodeSkeletonData:
    metadata = parse_name_metadata(node.name)
    structured = structured_mapping(raw_item, STRUCTURED_NODE_KEYS)
    raw_id = (
        text_value(structured, "id", "nodeId")
        or metadata.get("id")
        or node.id
        or node.characters
        or node.name
    )
    responsible = list_value(structured, *STRUCTURED_RESPONSIBLE_KEYS) or split_csv(
        metadata.get("responsible")
    )
    time = normalize_time_value(text_value(structured, "time", "duration") or metadata.get("time"))
    return FlowNodeSkeletonData(
        id=normalize_identifier(raw_id, fallback=node.id),
        kind=normalize_flow_node_kind(
            text_value(structured, "type", "kind") or metadata.get("kind")
        ),
        responsible=responsible,
        time=time,
    )


def resolve_flow_edge_data(
    node: FigmaConnectorNode,
    raw_item: Mapping[str, object],
) -> FlowEdgeSkeletonData:
    metadata = parse_name_metadata(node.name)
    structured = structured_mapping(raw_item, STRUCTURED_EDGE_KEYS)
    raw_id = text_value(structured, "id", "edgeId") or metadata.get("id") or node.id or node.name
    return FlowEdgeSkeletonData(
        id=normalize_identifier(raw_id, fallback=node.id),
        kind=normalize_flow_edge_kind(
            text_value(structured, "kind", "type") or metadata.get("kind")
        ),
        source=normalize_terminal_identifier(
            text_value(structured, "source", "from") or metadata.get("source")
        ),
        target=normalize_terminal_identifier(
            text_value(structured, "target", "to") or metadata.get("target")
        ),
        label=text_value(structured, "label") or metadata.get("label") or None,
    )


def build_flow_node_mapping(data: FlowNodeSkeletonData) -> dict[str, object]:
    result: dict[str, object] = {
        "id": data.id,
        "type": data.kind,
    }
    if data.responsible:
        result["responsibles"] = data.responsible
    if data.time is not None:
        result["time"] = data.time
    return result


def build_flow_edge_mapping(data: FlowEdgeSkeletonData) -> dict[str, object]:
    result: dict[str, object] = {
        "id": data.id,
        "kind": data.kind,
    }
    if data.source is not None:
        result["source"] = data.source
    if data.target is not None:
        result["target"] = data.target
    if data.label is not None:
        result["label"] = data.label
    return result


def build_flow_node_name(
    data: FlowNodeSkeletonData,
    *,
    extras: Mapping[str, str] | None = None,
) -> str:
    payload = {
        "id": data.id,
        "kind": data.kind,
        "responsible": ",".join(data.responsible) if data.responsible else None,
        "time": data.time,
    }
    return serialize_name_metadata(
        payload,
        extras=extras,
        preferred_order=("id", "kind", "responsible", "time"),
    )


def build_flow_edge_name(
    data: FlowEdgeSkeletonData,
    *,
    extras: Mapping[str, str] | None = None,
) -> str:
    payload = {
        "id": data.id,
        "kind": data.kind,
        "source": data.source,
        "target": data.target,
        "label": data.label,
    }
    return serialize_name_metadata(
        payload,
        extras=extras,
        preferred_order=("id", "kind", "source", "target", "label"),
    )


def normalize_terminal_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    return normalize_identifier(value, fallback=value)


def structured_mapping(
    raw_item: Mapping[str, object],
    keys: tuple[str, ...],
) -> Mapping[str, object] | None:
    for key in keys:
        value = raw_item.get(key)
        if isinstance(value, Mapping):
            return value
    return None


def text_value(mapping: Mapping[str, object] | None, *keys: str) -> str | None:
    if mapping is None:
        return None
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        normalized = " ".join(str(value).strip().split())
        if normalized:
            return normalized
    return None


def list_value(mapping: Mapping[str, object] | None, *keys: str) -> list[str]:
    if mapping is None:
        return []
    for key in keys:
        value = mapping.get(key)
        if value is None:
            continue
        if isinstance(value, str):
            parsed = split_csv(value)
            if parsed:
                return parsed
            continue
        if isinstance(value, list):
            parsed = []
            for item in value:
                normalized = " ".join(str(item).strip().split())
                if normalized:
                    parsed.append(normalized)
            if parsed:
                return parsed
    return []


def serialize_name_metadata(
    payload: Mapping[str, str | None],
    *,
    extras: Mapping[str, str] | None,
    preferred_order: tuple[str, ...],
) -> str:
    merged = dict(extras or {})
    for key in payload:
        merged.pop(key, None)
    for key, value in payload.items():
        if value:
            merged[key] = value

    ordered_tokens: list[str] = []
    seen: set[str] = set()
    for key in preferred_order:
        value = merged.get(key)
        if value:
            ordered_tokens.append(f"{key}={value}")
            seen.add(key)
    for key in sorted(merged):
        if key in seen:
            continue
        value = merged[key]
        if value:
            ordered_tokens.append(f"{key}={value}")
    return ";".join(ordered_tokens)
