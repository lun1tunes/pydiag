from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from pydiag.domain.models import FlowGraphDocument, WellsDocument, validate_wells_against_graph

from .editable_flow_graph import (
    EditableFlowGraphDocument,
    editable_flow_graph_to_runtime,
    is_editable_flow_graph_payload,
)
from .figma_import import (
    flow_graph_payload_from_figma_payload,
    is_figma_skeleton_payload,
)
from .flow_source_graph import (
    editable_flow_graph_payload_from_source_payload,
    is_flow_source_payload,
    load_structured_payload,
)
from .storage_materialization import (
    ensure_wells_doc_exists as ensure_wells_doc_bootstrap,
)
from .storage_paths import (
    GRAPH_PATH,
    configured_graph_path,
    preferred_graph_source_path,
    wells_path,
)

__all__ = [
    "load_documents",
    "load_graph_doc",
    "load_wells_doc",
]


def load_graph_doc(path: str | Path | None = None) -> FlowGraphDocument:
    resolved_path = resolve_graph_read_path(path)
    raw = resolved_path.read_bytes()
    try:
        return FlowGraphDocument.model_validate_json(raw, strict=True)
    except ValidationError:
        payload = load_structured_payload(raw)
        if is_editable_flow_graph_payload(payload):
            editable = EditableFlowGraphDocument.model_validate(payload, strict=True)
            return editable_flow_graph_to_runtime(editable)
        if is_flow_source_payload(payload):
            editable_payload = editable_flow_graph_payload_from_source_payload(payload)
            editable = EditableFlowGraphDocument.model_validate(editable_payload, strict=True)
            return editable_flow_graph_to_runtime(editable)
        if is_figma_skeleton_payload(payload):
            return FlowGraphDocument.model_validate(
                flow_graph_payload_from_figma_payload(payload),
                strict=True,
            )
        raise


def load_wells_doc(path: str | Path | None = None) -> WellsDocument:
    target = Path(path or wells_path())
    ensure_wells_doc_bootstrap(target)
    raw = target.read_bytes()
    try:
        return WellsDocument.model_validate_json(raw, strict=True)
    except ValidationError:
        payload = load_structured_payload(raw)
        return WellsDocument.model_validate_json(
            json.dumps(payload, ensure_ascii=False),
            strict=True,
        )


def load_documents(
    graph_doc_path: str | Path | None = None,
    wells_doc_path: str | Path | None = None,
) -> tuple[FlowGraphDocument, WellsDocument]:
    graph = load_graph_doc(graph_doc_path)
    wells = load_wells_doc(wells_doc_path)
    validate_wells_against_graph(graph, wells)
    return graph, wells


def resolve_graph_read_path(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path)

    source = preferred_graph_source_path()
    if source is not None:
        return source

    configured = configured_graph_path()
    if configured is not None:
        return configured
    if GRAPH_PATH.exists():
        return GRAPH_PATH
    return GRAPH_PATH
