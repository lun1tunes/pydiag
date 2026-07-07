from __future__ import annotations

import re
from dataclasses import dataclass

from pydiag.application import CreateWellCommand
from pydiag.domain.models import FlowGraphDocument, FlowNode, Well, WellsDocument
from pydiag.domain.services import outgoing_edges, transition_label

WELL_ID_RE = re.compile(r"[A-Za-z0-9_.:-]+")


@dataclass(frozen=True)
class AdminPanelDefaults:
    default_well_id: str | None
    default_node_id: str


def admin_panel_defaults(
    graph: FlowGraphDocument,
    selected_kind: str,
    selected: FlowNode | Well | object | None,
) -> AdminPanelDefaults:
    default_well_id = (
        selected.id if selected_kind == "well" and isinstance(selected, Well) else None
    )
    default_node_id = (
        str(selected.id)
        if selected_kind == "node" and selected is not None and hasattr(selected, "id")
        else graph.nodes[0].id
    )
    return AdminPanelDefaults(
        default_well_id=default_well_id,
        default_node_id=default_node_id,
    )


def active_wells(wells: WellsDocument) -> list[Well]:
    return [well for well in wells.wells if not well.is_archived]


def default_option_index(options: list[str], preferred: str | None) -> int:
    if preferred in options:
        return options.index(preferred)
    return 0


def transition_ids_for_well(graph: FlowGraphDocument, well: Well) -> list[str]:
    return [edge.id for edge in outgoing_edges(graph, well.current_node_id)]


def transition_option_label(graph: FlowGraphDocument, well: Well, edge_id: str) -> str:
    edge = next(edge for edge in outgoing_edges(graph, well.current_node_id) if edge.id == edge_id)
    return transition_label(edge, graph)


def validate_create_well_identity(well_id: str, name: str) -> str | None:
    normalized_well_id = well_id.strip()
    normalized_name = name.strip()
    if not WELL_ID_RE.fullmatch(normalized_well_id):
        return "ID должен состоять из латиницы, цифр, _, ., :, -"
    if not normalized_name:
        return "Название скважины обязательно."
    return None


def build_create_well_command(
    *,
    well_id: str,
    name: str,
    start_node_id: str,
    field: str,
    rig: str,
    comment: str,
) -> CreateWellCommand:
    return CreateWellCommand(
        well_id=well_id.strip(),
        name=name.strip(),
        start_node_id=start_node_id,
        metadata={
            key: value
            for key, value in {
                "field": field.strip(),
                "rig": rig.strip(),
            }.items()
            if value
        },
        comment=normalized_optional_text(comment),
    )


def normalized_optional_text(value: str) -> str | None:
    normalized = value.strip()
    return normalized or None


def suggest_well_id(wells: WellsDocument) -> str:
    max_number = 1000
    for well in wells.wells:
        match = re.search(r"(\d+)$", well.id)
        if match:
            max_number = max(max_number, int(match.group(1)))
    return f"well_{max_number + 1}"
