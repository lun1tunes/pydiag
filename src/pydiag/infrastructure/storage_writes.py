from __future__ import annotations

from pathlib import Path

from pydiag.common.graph_source_admin import (
    UpdateGraphSourceEdgeCommand,
    UpdateGraphSourceNodeCommand,
)
from pydiag.common.errors import VersionConflictError
from pydiag.domain.models import FlowGraphDocument, WellsDocument, validate_wells_against_graph

from .editable_flow_graph import EditableFlowGraphDocument, editable_flow_graph_to_runtime
from .editable_flow_graph import (
    is_editable_flow_graph_payload,
    update_editable_graph_payload_positions,
)
from .figma_import import (
    is_figma_skeleton_payload,
    update_figma_payload_positions,
)
from .flow_source_graph import (
    dump_flow_source_payload,
    editable_flow_graph_payload_from_source_payload,
    graph_source_edge_draft_from_payload,
    graph_source_node_draft_from_payload,
    dump_structured_yaml_payload,
    is_flow_source_payload,
    load_structured_payload,
    update_flow_source_payload_custom_layout,
    update_flow_source_payload_edge,
    update_flow_source_payload_layout,
    update_flow_source_payload_node,
)
from .storage_io import json_file_lock, save_json_atomic, save_text_atomic
from .storage_loading import load_graph_doc, load_wells_doc
from .storage_materialization import materialize_flow_graph_from_source
from .storage_paths import graph_path, preferred_graph_source_path, wells_path

__all__ = [
    "load_graph_source_edge_draft",
    "load_graph_source_node_draft",
    "save_graph_positions_with_version_check",
    "save_graph_source_edge_with_version_check",
    "save_graph_source_node_with_version_check",
    "save_wells_with_version_check",
]


def save_wells_with_version_check(
    wells_doc: WellsDocument,
    expected_version: int,
    path: str | Path | None = None,
    graph: FlowGraphDocument | None = None,
) -> WellsDocument:
    target = Path(path or wells_path())
    with json_file_lock(target):
        current = load_wells_doc(target)
        if current.version != expected_version:
            raise VersionConflictError(
                f"Conflict: expected wells version {expected_version}, "
                f"actual version is {current.version}"
            )

        to_save = wells_doc.model_copy(deep=True)
        to_save.version = expected_version + 1
        if graph is not None:
            validate_wells_against_graph(graph, to_save)
        payload = to_save.model_dump(mode="json")
        if target.suffix.lower() in {".yaml", ".yml"}:
            save_text_atomic(target, dump_structured_yaml_payload(payload))
        else:
            save_json_atomic(target, payload)
        return load_wells_doc(target)


def save_graph_positions_with_version_check(
    positions: dict[str, tuple[float, float]],
    expected_version: int,
    path: str | Path | None = None,
    layout_mode: str = "manual",
) -> FlowGraphDocument:
    if layout_mode not in {"manual", "custom"}:
        raise ValueError(
            "Graph positions can only be saved for 'manual' or 'custom' layout modes"
        )

    target = Path(path or graph_path())
    with json_file_lock(target):
        raw_payload = load_structured_payload(target.read_bytes())
        if is_flow_source_payload(raw_payload):
            try:
                if layout_mode == "custom":
                    payload = update_flow_source_payload_custom_layout(
                        raw_payload,
                        positions=positions,
                        expected_version=expected_version,
                    )
                else:
                    payload = update_flow_source_payload_layout(
                        raw_payload,
                        positions=positions,
                        expected_version=expected_version,
                    )
            except RuntimeError as exc:
                raise VersionConflictError(str(exc)) from exc
            save_text_atomic(target, dump_flow_source_payload(payload))
            live_source = preferred_graph_source_path()
            if live_source is not None and target.resolve() == live_source.resolve():
                materialize_flow_graph_from_source(
                    source_path=target,
                    target_path=graph_path(),
                )
            return load_graph_doc(target)

        if is_figma_skeleton_payload(raw_payload):
            try:
                payload = update_figma_payload_positions(
                    raw_payload,
                    positions=positions,
                    expected_version=expected_version,
                )
            except RuntimeError as exc:
                raise VersionConflictError(str(exc)) from exc
            save_json_atomic(target, payload)
            return load_graph_doc(target)

        if is_editable_flow_graph_payload(raw_payload):
            try:
                payload = update_editable_graph_payload_positions(
                    raw_payload,
                    positions=positions,
                    expected_version=expected_version,
                )
            except RuntimeError as exc:
                raise VersionConflictError(str(exc)) from exc
            save_json_atomic(target, payload)
            return load_graph_doc(target)

        current = load_graph_doc(target)
        if current.version != expected_version:
            raise VersionConflictError(
                f"Conflict: expected graph version {expected_version}, "
                f"actual version is {current.version}"
            )

        current_node_ids = {node.id for node in current.nodes}
        unknown_ids = sorted(set(positions) - current_node_ids)
        if unknown_ids:
            raise ValueError(f"Unknown graph node positions: {', '.join(unknown_ids)}")

        payload = current.model_dump(mode="json")
        payload["version"] = expected_version + 1
        for node_payload in payload["nodes"]:
            node_position = positions.get(node_payload["id"])
            if node_position is None:
                continue
            node_payload["position"] = {
                "x": round(float(node_position[0]), 2),
                "y": round(float(node_position[1]), 2),
            }

        FlowGraphDocument.model_validate(payload, strict=True)
        save_json_atomic(target, payload)
        return load_graph_doc(target)


def load_graph_source_node_draft(path: str | Path, node_id: str):
    payload = load_structured_payload(Path(path).read_bytes())
    if not is_flow_source_payload(payload):
        raise ValueError(f"Graph source editing requires source YAML: {path}")
    return graph_source_node_draft_from_payload(payload, node_id)


def load_graph_source_edge_draft(path: str | Path, edge_id: str):
    payload = load_structured_payload(Path(path).read_bytes())
    if not is_flow_source_payload(payload):
        raise ValueError(f"Graph source editing requires source YAML: {path}")
    return graph_source_edge_draft_from_payload(payload, edge_id)


def save_graph_source_node_with_version_check(
    command: UpdateGraphSourceNodeCommand,
    *,
    expected_version: int,
    path: str | Path,
) -> FlowGraphDocument:
    target = Path(path)
    with json_file_lock(target):
        payload = load_structured_payload(target.read_bytes())
        if not is_flow_source_payload(payload):
            raise ValueError(f"Graph source editing requires source YAML: {target}")
        try:
            updated_payload = update_flow_source_payload_node(
                payload,
                command=command,
                expected_version=expected_version,
            )
        except RuntimeError as exc:
            raise VersionConflictError(str(exc)) from exc
        return save_flow_source_payload(target, updated_payload)


def save_graph_source_edge_with_version_check(
    command: UpdateGraphSourceEdgeCommand,
    *,
    expected_version: int,
    path: str | Path,
) -> FlowGraphDocument:
    target = Path(path)
    with json_file_lock(target):
        payload = load_structured_payload(target.read_bytes())
        if not is_flow_source_payload(payload):
            raise ValueError(f"Graph source editing requires source YAML: {target}")
        try:
            updated_payload = update_flow_source_payload_edge(
                payload,
                command=command,
                expected_version=expected_version,
            )
        except RuntimeError as exc:
            raise VersionConflictError(str(exc)) from exc
        return save_flow_source_payload(target, updated_payload)


def save_flow_source_payload(target: Path, payload: object) -> FlowGraphDocument:
    editable_payload = editable_flow_graph_payload_from_source_payload(payload)
    editable_document = EditableFlowGraphDocument.model_validate(
        editable_payload,
        strict=True,
    )
    editable_flow_graph_to_runtime(editable_document)
    save_text_atomic(target, dump_flow_source_payload(payload))
    live_source = preferred_graph_source_path()
    if live_source is not None and target.resolve() == live_source.resolve():
        return materialize_flow_graph_from_source(
            source_path=target,
            target_path=graph_path(),
        )
    return load_graph_doc(target)
