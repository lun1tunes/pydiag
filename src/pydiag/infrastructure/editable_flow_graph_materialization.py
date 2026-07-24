from __future__ import annotations

import copy
import re
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from pydiag.infrastructure.editable_flow_graph import (
    EditableFlowGraphDocument,
    EditableNodeKind,
)
from pydiag.infrastructure.figma_geometry import (
    Rect,
    infer_connector_terminal,
    secondary_nearest_terminal,
)
from pydiag.infrastructure.figma_metadata import (
    FlowEdgeSkeletonData,
    build_flow_edge_mapping,
    build_flow_edge_name,
    parse_name_metadata,
    resolve_flow_edge_data,
    resolve_flow_node_data,
    structured_mapping,
)
from pydiag.infrastructure.figma_schema import (
    FigmaConnectorNode,
    FigmaTextNode,
    extract_typed_elements,
    payload_version,
)

EDITABLE_DEFAULT_STYLE = {
    "fill": "#eef2f6",
    "border": "#64748b",
    "text": "#253041",
}
RESPONSIBLE_STYLE_PALETTE = (
    {"fill": "#dcecff", "border": "#356ca8", "text": "#17314f"},
    {"fill": "#e3f7ea", "border": "#3f8a55", "text": "#17311e"},
    {"fill": "#fff2d6", "border": "#b17a23", "text": "#43300d"},
    {"fill": "#ffe3e3", "border": "#b84c4c", "text": "#4e1717"},
    {"fill": "#e9e4ff", "border": "#6954b8", "text": "#261b53"},
    {"fill": "#dff5f2", "border": "#16877d", "text": "#123834"},
    {"fill": "#fde7f3", "border": "#c24180", "text": "#4c1130"},
    {"fill": "#ede9fe", "border": "#7c3aed", "text": "#2e1065"},
)
GENERIC_CONNECTOR_NAMES = {"connector line"}
ALLOWED_ACTOR_ABBREVIATIONS = {
    "ОГМ": ("ogm", "ОГМ"),
    "ОРМ": ("orm", "ОРМ"),
    "РПГ": ("rpg", "РПГ"),
    "СГСБ": ("sgsb", "СГСБ"),
    "ДЗО": ("dzo", "ДЗО"),
    "ПАО": ("pao", "ПАО"),
    "РП": ("rp", "РП"),
    "ДО": ("do", "ДО"),
    "ННБ": ("nnb", "ННБ"),
    "ЗАМДД": ("zamdd", "ЗамДД"),
    "ДСС НТЦ": ("dss_ntc", "ДСС НТЦ"),
    "ПРОЕКТНАЯ ГРУППА": ("project_group", "Проектная группа"),
    "СЕЙС": ("seismic", "Сейсмик"),
    "СЕЙСМИК": ("seismic", "Сейсмик"),
    "СОС": ("well_completion", "Специалист по освоению скважин"),
    "Б": ("b", "Б"),
}
NON_RESPONSIBLE_ABBREVIATIONS = {
    "ТС",
    "ГС",
    "ГДМ",
    "РИГИС",
    "ИС",
    "ПЛАН",
    "МЕМО",
    "ПМ",
    "ГИС",
    "КДПЭ",
    "ЭБ",
    "ГУ",
    "ГМ",
    "СРР",
    "СПО",
    "ИГ",
    "КП",
}
QUESTION_END_RE = re.compile(r"\?\s*$")
DATABASE_PREFIX_RE = re.compile(r"^(?:ис|иг)\s+геонова\b", re.IGNORECASE)
INPUT_PREFIX_RE = re.compile(
    r"^(?:чек-?лист|таблица|форма|обоснование|пояснение|презентация)\b",
    re.IGNORECASE,
)
EVENT_PREFIX_RE = re.compile(
    r"^(?:начало|достижение|получение|происходит)\b", re.IGNORECASE
)
STRONG_PRIMARY_PREFIX_RE = re.compile(
    r"^(?:сгсб|петрофизик|геонавигация|дсс\s+нтц|дзо|пао)\b",
    re.IGNORECASE,
)
CONTEXT_ONLY_PREFIX_RE = re.compile(
    r"^(?:запрос|согласование|информирование|уведомление|оповещение|проработка)\b",
    re.IGNORECASE,
)
ACTOR_PATTERNS: tuple[tuple[re.Pattern[str], list[tuple[str, str]]], ...] = (
    (
        re.compile(r"\bдсс\s+нтц\b", re.IGNORECASE),
        [("dss_ntc", "ДСС НТЦ")],
    ),
    (
        re.compile(
            r"\bкуратор(?:а|у|ом)?(?:\s+от)?\s+геонавигаци[ияе]\b", re.IGNORECASE
        ),
        [("geosteering_curator", "Куратор геонавигации")],
    ),
    (
        re.compile(r"\bинженер(?:а|у|ом)?\s+по\s+геонавигации\b", re.IGNORECASE),
        [("geosteering_engineer", "Инженер по геонавигации")],
    ),
    (
        re.compile(r"\bподрядчик(?:у|ом)?\s+бурового\s+сервиса\b", re.IGNORECASE),
        [("drilling_service_contractor", "Подрядчик бурового сервиса")],
    ),
    (
        re.compile(r"\bспециалист(?:ам|а|у|ом)?\s+ннб\b", re.IGNORECASE),
        [("nnb", "ННБ")],
    ),
    (
        re.compile(r"\bподрядчик(?:а|у|ом)?\s+по\s+ннб\b", re.IGNORECASE),
        [("nnb", "ННБ")],
    ),
    (
        re.compile(r"\bпетрофизик(?:а|у|ом)?\b", re.IGNORECASE),
        [("petrophysics", "Петрофизик")],
    ),
    (
        re.compile(r"\bгеонавигаци[яеи]\b", re.IGNORECASE),
        [("geosteering", "Геонавигация")],
    ),
    (
        re.compile(r"\bпроектную\s+группу\b", re.IGNORECASE),
        [("project_group", "Проектная группа")],
    ),
    (
        re.compile(r"\bзамдд\b", re.IGNORECASE),
        [("zamdd", "ЗамДД")],
    ),
)

__all__ = [
    "editable_flow_graph_payload_from_figma_payload",
    "normalize_editable_flow_graph_payload",
]


@dataclass(frozen=True)
class NodeDraft:
    id: str
    kind: EditableNodeKind
    title: str
    position: dict[str, float]
    size: dict[str, int]
    responsible: str | None
    participants: list[str]
    approvers: list[str]
    duration: str | None
    metadata: dict[str, Any]


@dataclass(frozen=True)
class ActorMatch:
    responsible_id: str
    label: str
    position: int


def editable_flow_graph_payload_from_figma_payload(payload: object) -> dict[str, Any]:
    elements = extract_typed_elements(payload)
    text_items, connector_items = split_materializable_elements(elements)
    drafts, responsible_labels = build_node_drafts(text_items)
    node_rects = {
        draft.id: Rect(
            left=float(draft.position["x"]),
            top=float(draft.position["y"]),
            right=float(draft.position["x"] + draft.size["w"]),
            bottom=float(draft.position["y"] + draft.size["h"]),
        )
        for draft in drafts
    }
    raw_edges = [
        convert_connector_node(raw_item, node, node_rects)
        for raw_item, node in connector_items
        if node.visible
    ]
    edges = normalize_imported_edges(raw_edges)
    drafts = ensure_required_node_responsibles(drafts)
    responsibles = build_responsibles_payload(payload, drafts, responsible_labels)

    editable_payload = {
        "schema_version": "editable-flow-graph/1.0",
        "version": payload_version(payload),
        "responsibles": responsibles,
        "nodes": [draft_to_payload(draft) for draft in drafts],
        "edges": edges,
    }
    EditableFlowGraphDocument.model_validate(editable_payload, strict=True)
    return editable_payload


def normalize_editable_flow_graph_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        raise ValueError("Editable graph normalization requires an object payload")

    normalized = copy.deepcopy(payload)
    elements = extract_typed_elements(normalized)
    text_items, connector_items = split_materializable_elements(elements)
    drafts, _ = build_node_drafts(text_items)
    node_rects = {
        draft.id: Rect(
            left=float(draft.position["x"]),
            top=float(draft.position["y"]),
            right=float(draft.position["x"] + draft.size["w"]),
            bottom=float(draft.position["y"] + draft.size["h"]),
        )
        for draft in drafts
    }
    raw_edges = [
        convert_connector_node(raw_item, node, node_rects)
        for raw_item, node in connector_items
        if node.visible
    ]
    edges = raw_edges
    drafts = ensure_required_node_responsibles(drafts)
    for raw_item, draft in zip((item for item, _ in text_items), drafts, strict=True):
        raw_item["editableNode"] = {
            "id": draft.id,
            "kind": draft.kind,
            "title": draft.title,
            "responsible": draft.responsible,
            "participants": draft.participants,
            "approvers": draft.approvers,
            "duration": draft.duration,
        }
    for (raw_item, node), edge in zip(connector_items, edges, strict=True):
        flow_edge = FlowEdgeSkeletonData(
            id=str(edge["id"]),
            kind="usual" if edge["kind"] == "default" else str(edge["kind"]),
            source=str(edge["source"]),
            target=str(edge["target"]),
            label=str(edge["label"]) if edge["label"] is not None else None,
        )
        raw_item["flowEdge"] = build_flow_edge_mapping(flow_edge)
        raw_item["name"] = build_flow_edge_name(
            flow_edge,
            extras=parse_name_metadata(node.name),
        )
    normalized["schema_version"] = "figma-editable/1.0"
    return normalized


def split_materializable_elements(
    elements: list[tuple[dict[str, object], object]],
) -> tuple[
    list[tuple[dict[str, object], FigmaTextNode]],
    list[tuple[dict[str, object], FigmaConnectorNode]],
]:
    has_shapes = any(
        isinstance(node, FigmaTextNode)
        and str(raw_item.get("type") or "").upper() == "SHAPE_WITH_TEXT"
        for raw_item, node in elements
    )
    text_items: list[tuple[dict[str, object], FigmaTextNode]] = []
    connector_items: list[tuple[dict[str, object], FigmaConnectorNode]] = []
    for raw_item, node in elements:
        if isinstance(node, FigmaConnectorNode):
            connector_items.append((raw_item, node))
            continue
        if not isinstance(node, FigmaTextNode) or not node.visible:
            continue
        raw_type = str(raw_item.get("type") or "").upper()
        if has_shapes:
            if raw_type == "SHAPE_WITH_TEXT" or has_structured_flow_node(raw_item):
                text_items.append((raw_item, node))
            continue
        text_items.append((raw_item, node))
    return text_items, connector_items


def has_structured_flow_node(raw_item: dict[str, object]) -> bool:
    return (
        structured_mapping(
            raw_item, ("editableNode", "editable_node", "flowNode", "flow_node")
        )
        is not None
    )


def build_node_drafts(
    text_items: list[tuple[dict[str, object], FigmaTextNode]],
) -> tuple[list[NodeDraft], dict[str, str]]:
    drafts: list[NodeDraft] = []
    responsible_labels: dict[str, str] = {}
    used_ids: set[str] = set()
    for raw_item, node in text_items:
        draft = convert_text_node(raw_item, node, used_ids)
        drafts.append(draft)
        for responsible_id, label in infer_labels_from_draft(draft).items():
            responsible_labels.setdefault(responsible_id, label)
    return drafts, responsible_labels


def convert_text_node(
    raw_item: dict[str, object],
    node: FigmaTextNode,
    used_ids: set[str],
) -> NodeDraft:
    title = normalize_title(node.characters or node.name or node.id)
    flow_node = resolve_flow_node_data(node, raw_item)
    explicit_kind = flow_node.kind if flow_node.kind != "figma_text" else None
    explicit_responsibles = list(flow_node.responsible)
    responsible, participants = infer_node_responsibles(title, explicit_responsibles)
    node_id = (
        flow_node.id
        if has_explicit_identifier(raw_item, node)
        else make_unique_identifier(title, used_ids, fallback=node.id)
    )
    used_ids.add(node_id)
    metadata: dict[str, Any] = {
        "figma_source_id": node.id,
        "figma_parent_id": node.parent,
        "figma_source_type": str(raw_item.get("type") or node.type),
    }
    kind = infer_node_kind(title, explicit_kind=explicit_kind)
    return NodeDraft(
        id=node_id,
        kind=kind,
        title=title,
        position={
            "x": round(float(node.x), 2),
            "y": round(float(node.y), 2),
        },
        size={
            "w": max(
                80, min(1200, int(round(float(node.width or max(60, len(title) * 8)))))
            ),
            "h": max(
                40,
                min(
                    800,
                    int(
                        round(
                            float(node.height or max(24, (node.font_size or 16) * 1.4))
                        )
                    ),
                ),
            ),
        },
        responsible=responsible,
        participants=participants,
        approvers=[],
        duration=flow_node.time,
        metadata={key: value for key, value in metadata.items() if value is not None},
    )


def has_explicit_identifier(raw_item: dict[str, object], node: FigmaTextNode) -> bool:
    metadata = parse_name_metadata(node.name)
    return (
        metadata.get("id") is not None
        or structured_mapping(
            raw_item, ("editableNode", "editable_node", "flowNode", "flow_node")
        )
        is not None
    )


def infer_labels_from_draft(draft: NodeDraft) -> dict[str, str]:
    labels: dict[str, str] = {}
    for responsible_id in [draft.responsible, *draft.participants, *draft.approvers]:
        if responsible_id is None:
            continue
        labels[responsible_id] = responsible_label_for_id(responsible_id)
    return labels


def draft_to_payload(draft: NodeDraft) -> dict[str, Any]:
    return {
        "id": draft.id,
        "kind": draft.kind,
        "title": draft.title,
        "position": draft.position,
        "size": draft.size,
        "responsible": draft.responsible,
        "participants": draft.participants,
        "approvers": draft.approvers,
        "note": None,
        "duration": draft.duration,
        "metadata": draft.metadata,
    }


def build_responsibles_payload(
    payload: object,
    drafts: list[NodeDraft],
    responsible_labels: dict[str, str],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    if isinstance(payload, dict) and isinstance(payload.get("responsibles"), dict):
        for responsible_id, raw_style in payload["responsibles"].items():
            if not isinstance(raw_style, dict):
                continue
            result[str(responsible_id)] = {
                "label": str(raw_style.get("label") or responsible_id),
                "fill": str(raw_style.get("fill") or EDITABLE_DEFAULT_STYLE["fill"]),
                "border": str(
                    raw_style.get("border") or EDITABLE_DEFAULT_STYLE["border"]
                ),
                "text": str(raw_style.get("text") or EDITABLE_DEFAULT_STYLE["text"]),
            }

    ordered_ids: list[str] = []
    for draft in drafts:
        for responsible_id in [
            draft.responsible,
            *draft.participants,
            *draft.approvers,
        ]:
            if responsible_id is None or responsible_id in ordered_ids:
                continue
            ordered_ids.append(responsible_id)

    for index, responsible_id in enumerate(ordered_ids):
        if responsible_id in result:
            continue
        if responsible_id == "unassigned":
            result[responsible_id] = {
                "label": "Не назначено",
                **EDITABLE_DEFAULT_STYLE,
            }
            continue
        palette = RESPONSIBLE_STYLE_PALETTE[index % len(RESPONSIBLE_STYLE_PALETTE)]
        result[responsible_id] = {
            "label": responsible_labels.get(responsible_id)
            or responsible_label_for_id(responsible_id),
            "fill": palette["fill"],
            "border": palette["border"],
            "text": palette["text"],
        }

    if result:
        return result
    return {
        "unassigned": {
            "label": "Не назначено",
            **EDITABLE_DEFAULT_STYLE,
        }
    }


def ensure_required_node_responsibles(drafts: list[NodeDraft]) -> list[NodeDraft]:
    required_kinds = {"process", "decision_diamond"}
    return [
        NodeDraft(
            id=draft.id,
            kind=draft.kind,
            title=draft.title,
            position=draft.position,
            size=draft.size,
            responsible="unassigned",
            participants=list(draft.participants),
            approvers=list(draft.approvers),
            duration=draft.duration,
            metadata=dict(draft.metadata),
        )
        if draft.kind in required_kinds and draft.responsible is None
        else draft
        for draft in drafts
    ]


def convert_connector_node(
    raw_item: dict[str, object],
    node: FigmaConnectorNode,
    node_rects: dict[str, Rect],
) -> dict[str, Any]:
    flow_edge = resolve_flow_edge_data(node, raw_item)
    source = flow_edge.source or infer_connector_terminal(node, node_rects, end="start")
    target = flow_edge.target or infer_connector_terminal(node, node_rects, end="end")
    if not source or not target:
        raise ValueError(f"Connector {node.id}: source/target could not be resolved")
    if source == target:
        nearest = secondary_nearest_terminal(node, node_rects, excluded=source)
        if nearest is not None:
            target = nearest

    kind, label = infer_edge_kind_and_label(flow_edge, node.name)
    edge_id = infer_edge_id(
        flow_edge.id,
        source=source,
        target=target,
        kind=kind,
        label=label,
    )
    return {
        "id": edge_id,
        "kind": kind,
        "source": source,
        "target": target,
        "label": label,
        "metadata": {
            "figma_source_id": node.id,
            "figma_parent_id": node.parent,
        },
    }


def normalize_imported_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for index, edge in enumerate(edges):
        grouped[(str(edge["source"]), str(edge["target"]))].append((index, edge))

    keep_indexes: set[int] = set()
    for items in grouped.values():
        candidates = [item for item in items if edge_has_semantics(item[1])]
        if not candidates:
            candidates = items

        seen_signatures: set[tuple[str, str | None]] = set()
        for index, edge in candidates:
            signature = (str(edge["kind"]), edge_label(edge))
            if signature in seen_signatures:
                continue
            seen_signatures.add(signature)
            keep_indexes.add(index)

    normalized = [edge for index, edge in enumerate(edges) if index in keep_indexes]
    return assign_unique_edge_ids(normalized)


def edge_has_semantics(edge: dict[str, Any]) -> bool:
    return str(edge["kind"]) != "default" or edge_label(edge) is not None


def edge_label(edge: dict[str, Any]) -> str | None:
    value = edge.get("label")
    if not isinstance(value, str):
        return None
    normalized = normalize_title(value)
    return normalized or None


def assign_unique_edge_ids(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    used_ids: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for edge in edges:
        updated = dict(edge)
        updated["id"] = unique_edge_id(str(edge["id"]), used_ids)
        normalized.append(updated)
    return normalized


def unique_edge_id(base: str, used_ids: set[str]) -> str:
    candidate = base or "edge"
    index = 2
    while candidate in used_ids:
        candidate = f"{base}_{index}"
        index += 1
    used_ids.add(candidate)
    return candidate


def infer_edge_kind_and_label(
    flow_edge: FlowEdgeSkeletonData,
    raw_name: str,
) -> tuple[str, str | None]:
    if flow_edge.kind in {"yes", "no", "dashed"}:
        label = flow_edge.label
        if flow_edge.kind == "yes" and label is None:
            label = "Да"
        if flow_edge.kind == "no" and label is None:
            label = "Нет"
        return ("default" if flow_edge.kind == "usual" else flow_edge.kind), label

    raw_label = normalize_title(flow_edge.label or raw_name)
    if raw_label.lower() in GENERIC_CONNECTOR_NAMES:
        return "default", None

    lowered = raw_label.lower()
    if lowered == "да":
        return "yes", "Да"
    if lowered == "нет":
        return "no", "Нет"
    if lowered == "была":
        return "yes", "Была"
    if lowered == "не было":
        return "no", "не было"
    if lowered:
        return "default", raw_label
    return "default", None


def infer_node_kind(
    title: str,
    *,
    explicit_kind: str | None,
) -> EditableNodeKind:
    if explicit_kind == "decision_card":
        return "process"
    if explicit_kind in {
        "process",
        "decision_diamond",
        "database",
        "input_data",
        "event",
    }:
        return explicit_kind

    if QUESTION_END_RE.search(title):
        return "decision_diamond"
    if DATABASE_PREFIX_RE.search(title):
        return "database"
    if INPUT_PREFIX_RE.search(title):
        return "input_data"
    if EVENT_PREFIX_RE.search(title):
        return "event"
    return "process"


def infer_node_responsibles(
    title: str,
    explicit_responsibles: list[str],
) -> tuple[str | None, list[str]]:
    if explicit_responsibles:
        primary = explicit_responsibles[0]
        return primary, list(dict.fromkeys(explicit_responsibles[1:]))

    matches = find_actor_matches(title)
    if not matches:
        return None, []

    primary = infer_primary_responsible(title, matches)
    participants = [
        match.responsible_id for match in matches if match.responsible_id != primary
    ]
    return primary, list(dict.fromkeys(participants))


def find_actor_matches(title: str) -> list[ActorMatch]:
    matches: list[ActorMatch] = []
    normalized = normalize_title(title)
    upper = normalized.upper()

    for pattern, actors in ACTOR_PATTERNS:
        for match in pattern.finditer(normalized):
            for responsible_id, label in actors:
                matches.append(
                    ActorMatch(
                        responsible_id=responsible_id,
                        label=label,
                        position=match.start(),
                    )
                )

    for token, (responsible_id, label) in ALLOWED_ACTOR_ABBREVIATIONS.items():
        token_pattern = re.compile(rf"\b{re.escape(token)}\b")
        for match in token_pattern.finditer(upper):
            matches.append(
                ActorMatch(
                    responsible_id=responsible_id,
                    label=label,
                    position=match.start(),
                )
            )

    ordered: list[ActorMatch] = []
    seen: set[str] = set()
    for match in sorted(matches, key=lambda item: (item.position, item.responsible_id)):
        if match.label.upper() in NON_RESPONSIBLE_ABBREVIATIONS:
            continue
        if match.responsible_id in seen:
            continue
        seen.add(match.responsible_id)
        ordered.append(match)
    return ordered


def infer_primary_responsible(
    title: str,
    matches: list[ActorMatch],
) -> str | None:
    if not matches:
        return None
    normalized = normalize_title(title)
    lower = normalized.lower()
    if CONTEXT_ONLY_PREFIX_RE.match(normalized):
        return None
    if lower.startswith("куратор сгсб"):
        return "sgsb"
    if lower.startswith("заключение от куратора") or lower.startswith(
        "запрос к куратору"
    ):
        return "geosteering_curator"
    if lower.startswith("заключение петрофизика"):
        return "petrophysics"
    if lower.startswith("геонавигация"):
        return "geosteering"
    if lower.startswith("петрофизик"):
        return "petrophysics"
    if STRONG_PRIMARY_PREFIX_RE.match(normalized):
        first_position = matches[0].position
        leading = [match for match in matches if match.position == first_position]
        if len(leading) == 1:
            return leading[0].responsible_id
    return None


def infer_edge_id(
    raw_id: str,
    *,
    source: str,
    target: str,
    kind: str,
    label: str | None,
) -> str:
    if raw_id and ":" not in raw_id:
        return raw_id
    parts = ["edge", source, target]
    if kind != "default":
        parts.append(kind)
    if label:
        parts.append(label)
    return slugify(" ".join(parts))


def normalize_title(value: str) -> str:
    normalized = value.replace("\u2028", " ").replace("\n", " ")
    return " ".join(normalized.split()).strip()


def make_unique_identifier(value: str, used_ids: set[str], *, fallback: str) -> str:
    base = slugify(value) or slugify(fallback) or "node"
    candidate = base
    index = 2
    while candidate in used_ids:
        candidate = f"{base}_{index}"
        index += 1
    return candidate


def slugify(value: str) -> str:
    transliterated = "".join(
        CYRILLIC_TO_LATIN.get(char, char) for char in value.lower()
    )
    normalized = re.sub(r"[^a-z0-9]+", "_", transliterated).strip("_")
    normalized = re.sub(r"_+", "_", normalized)
    return normalized[:96]


def responsible_label_for_id(responsible_id: str) -> str:
    for _token, (candidate_id, label) in ALLOWED_ACTOR_ABBREVIATIONS.items():
        if candidate_id == responsible_id:
            return label
    fixed = {
        "petrophysics": "Петрофизик",
        "geosteering": "Геонавигация",
        "geosteering_curator": "Куратор геонавигации",
        "geosteering_engineer": "Инженер по геонавигации",
        "drilling_service_contractor": "Подрядчик бурового сервиса",
        "project_group": "Проектная группа",
    }
    if responsible_id in fixed:
        return fixed[responsible_id]
    return responsible_id.replace("_", " ").strip().title() or responsible_id


CYRILLIC_TO_LATIN = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "i",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "h",
    "ц": "c",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}
