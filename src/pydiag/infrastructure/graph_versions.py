from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path

from pydantic import ValidationError

from pydiag.common.graph_versions import GraphVersionInfo, RawImportResult
from pydiag.domain.models import FlowGraphDocument

from .editable_flow_graph import is_editable_flow_graph_payload
from .editable_flow_graph_materialization import editable_flow_graph_payload_from_figma_payload
from .figma_import import is_figma_skeleton_payload
from .flow_source_graph import (
    dump_flow_source_payload,
    flow_source_payload_from_editable_payload,
    flow_source_payload_from_runtime_payload,
    is_flow_source_payload,
    load_structured_payload,
)
from .storage_io import save_text_atomic
from .storage_paths import (
    configured_graph_path,
    graph_version_paths,
    next_graph_version_path,
    preferred_graph_source_path,
    raw_graph_path,
    source_graph_path,
)

__all__ = [
    "can_materialize_graph_version",
    "can_import_raw_graph_source",
    "ensure_live_graph_source",
    "GraphVersionInfo",
    "import_live_graph_source_from_raw",
    "list_graph_versions",
    "materialize_new_graph_version_from_raw_source",
    "resolve_graph_version_path",
]

GRAPH_ID_SANITIZE_RE = re.compile(r"[^a-z0-9_]+")


def can_materialize_graph_version() -> bool:
    return preferred_graph_source_path() is not None


def can_import_raw_graph_source() -> bool:
    return raw_graph_path().exists()


def list_graph_versions() -> list[GraphVersionInfo]:
    return [
        GraphVersionInfo(
            id=path.name,
            label=path.name,
            path=path,
            is_versioned=True,
        )
        for path in reversed(graph_version_paths())
    ]


def resolve_graph_version_path(version_id: str | None) -> Path:
    configured = configured_graph_path()
    if configured is not None and version_id == configured.name:
        return configured

    if version_id is not None:
        for version in list_graph_versions():
            if version.id == version_id:
                return version.path
    raise FileNotFoundError(f"Unknown graph version: {version_id}")


def inferred_graph_id(path: Path) -> str:
    stem = path.stem.strip().replace("-", "_").replace(" ", "_").lower()
    normalized = GRAPH_ID_SANITIZE_RE.sub("_", stem).strip("_")
    return normalized or "flow_source"


def inferred_title(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip() or "Flow source"


def materialized_flow_source_payload(source: Path) -> dict[str, object]:
    payload = load_structured_payload(source.read_bytes())
    if is_flow_source_payload(payload):
        return payload
    if is_editable_flow_graph_payload(payload):
        return flow_source_payload_from_editable_payload(
            payload,
            graph_id=inferred_graph_id(source),
            title=inferred_title(source),
        )
    if is_figma_skeleton_payload(payload):
        editable_payload = editable_flow_graph_payload_from_figma_payload(payload)
        return flow_source_payload_from_editable_payload(
            editable_payload,
            graph_id=inferred_graph_id(source),
            title=inferred_title(source),
        )
    try:
        runtime_payload = FlowGraphDocument.model_validate(
            payload,
            strict=True,
        ).model_dump(mode="json")
    except ValidationError as exc:
        raise ValueError(f"Unsupported graph source payload: {source}") from exc
    return flow_source_payload_from_runtime_payload(
        runtime_payload,
        graph_id=inferred_graph_id(source),
        title=inferred_title(source),
    )


def ensure_live_graph_source(
    source_path: str | Path | None = None,
    target_path: str | Path | None = None,
) -> Path:
    target = Path(target_path or source_graph_path())
    if target.exists():
        return target

    resolved_source = source_path or preferred_graph_source_path()
    if resolved_source is None:
        raise FileNotFoundError("Graph source not found")
    source = Path(resolved_source)
    if source.resolve() == target.resolve():
        if target.exists():
            return target
        raise FileNotFoundError(f"Graph source not found: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    save_text_atomic(
        target,
        dump_flow_source_payload(materialized_flow_source_payload(source)),
    )
    return target


def import_live_graph_source_from_raw(
    source_path: str | Path | None = None,
    target_path: str | Path | None = None,
) -> RawImportResult:
    source = Path(source_path or raw_graph_path())
    if not source.exists():
        raise FileNotFoundError(f"Raw graph source not found: {source}")

    target = Path(target_path or source_graph_path())
    imported_payload = materialized_flow_source_payload(source)
    target.parent.mkdir(parents=True, exist_ok=True)

    if not target.exists():
        save_text_atomic(target, dump_flow_source_payload(imported_payload))
        return RawImportResult(live_path=target, changed=True)

    current_payload = materialized_flow_source_payload(target)
    if _payloads_equal_ignoring_version(current_payload, imported_payload):
        return RawImportResult(live_path=target, changed=False)

    backup_path = next_graph_version_path()
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    save_text_atomic(
        backup_path,
        dump_flow_source_payload(current_payload),
    )
    imported_payload["version"] = max(
        int(imported_payload.get("version", 1)),
        int(current_payload.get("version", 1)) + 1,
    )
    save_text_atomic(target, dump_flow_source_payload(imported_payload))
    return RawImportResult(
        live_path=target,
        changed=True,
        backup_version=GraphVersionInfo(
            id=backup_path.name,
            label=backup_path.name,
            path=backup_path,
            is_versioned=True,
        ),
    )


def materialize_new_graph_version_from_raw_source(
    source_path: str | Path | None = None,
) -> GraphVersionInfo:
    resolved_source = source_path or preferred_graph_source_path()
    if resolved_source is None:
        raise FileNotFoundError("Graph source not found")
    source = Path(resolved_source)
    target = next_graph_version_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    save_text_atomic(
        target,
        dump_flow_source_payload(materialized_flow_source_payload(source)),
    )
    return GraphVersionInfo(
        id=target.name,
        label=target.name,
        path=target,
        is_versioned=True,
    )


def _payloads_equal_ignoring_version(
    current_payload: dict[str, object],
    imported_payload: dict[str, object],
) -> bool:
    current = load_structured_payload(
        dump_flow_source_payload(deepcopy(current_payload))
    )
    imported = load_structured_payload(
        dump_flow_source_payload(deepcopy(imported_payload))
    )
    if not isinstance(current, dict) or not isinstance(imported, dict):
        return False
    current.pop("version", None)
    imported.pop("version", None)
    return current == imported
