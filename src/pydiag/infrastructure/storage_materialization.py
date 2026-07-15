from __future__ import annotations

from pathlib import Path
from textwrap import dedent

from pydiag.domain.models import FlowGraphDocument

from .editable_flow_graph import EditableFlowGraphDocument, editable_flow_graph_to_runtime
from .editable_flow_graph_materialization import editable_flow_graph_payload_from_figma_payload
from .figma_import import is_figma_skeleton_payload
from .flow_source_graph import (
    editable_flow_graph_payload_from_source_payload,
    is_flow_source_payload,
    load_structured_payload,
)
from .storage_io import save_json_atomic, save_text_atomic
from .storage_paths import (
    configured_graph_path,
    graph_path,
    preferred_graph_source_path,
)

__all__ = [
    "ensure_wells_doc_exists",
    "materialize_flow_graph_from_raw_source",
    "materialize_flow_graph_from_source",
]

EMPTY_WELLS_YAML_TEMPLATE = dedent(
    """
    schema_version: "1.0"
    version: 1
    wells: []
    # Replace the empty list above with entries like:
    # wells:
    #   - id: well_1
    #     name: Скв. 1
    #     current_node_id: intake_data
    #     history:
    #       - ts: "2026-05-08T08:00:00Z"
    #         node_id: intake_data
    #         action: create
    #         to_node_id: intake_data
    #         by: system
    #         comment: initial placement
    #     metadata: {}
    #     is_archived: false
    """
).strip() + "\n"


def materialize_flow_graph_from_source(
    source_path: str | Path | None = None,
    target_path: str | Path | None = None,
) -> FlowGraphDocument:
    resolved_source = source_path or preferred_graph_source_path()
    if resolved_source is None:
        raise FileNotFoundError("Graph source not found")
    source = Path(resolved_source)
    target = Path(target_path or configured_graph_path() or graph_path())

    if source.resolve() == target.resolve():
        raise ValueError("Graph source and materialized flow graph target must differ")
    if not source.exists():
        raise FileNotFoundError(f"Graph source not found: {source}")

    payload = load_structured_payload(source.read_bytes())
    if is_flow_source_payload(payload):
        editable_payload = editable_flow_graph_payload_from_source_payload(payload)
    elif is_figma_skeleton_payload(payload):
        editable_payload = editable_flow_graph_payload_from_figma_payload(payload)
    else:
        raise ValueError(f"Unsupported graph source payload: {source}")

    save_json_atomic(target, editable_payload)
    return editable_flow_graph_to_runtime(
        EditableFlowGraphDocument.model_validate(editable_payload, strict=True)
    )


def materialize_flow_graph_from_raw_source(
    source_path: str | Path | None = None,
    target_path: str | Path | None = None,
) -> FlowGraphDocument:
    return materialize_flow_graph_from_source(source_path=source_path, target_path=target_path)


def ensure_wells_doc_exists(path: Path) -> None:
    if path.exists():
        return
    save_text_atomic(path, EMPTY_WELLS_YAML_TEMPLATE)
