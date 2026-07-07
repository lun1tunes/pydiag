from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydiag.common.graph_versions import GraphVersionInfo
from pydiag.domain.models import FlowGraphDocument, WellsDocument

from .graph_versions import (
    can_materialize_graph_version,
    list_graph_versions,
    materialize_new_graph_version_from_raw_source,
    resolve_graph_version_path,
)
from .storage import (
    graph_path,
    load_documents,
    preferred_graph_source_path,
    save_graph_positions_with_version_check,
    save_wells_with_version_check,
    wells_path,
)

__all__ = ["JsonDocumentsGateway"]


@dataclass(frozen=True)
class JsonDocumentsGateway:
    load_documents_fn: Callable[..., tuple[FlowGraphDocument, WellsDocument]] = load_documents
    resolve_graph_version_path_fn: Callable[[str | None], Path] = resolve_graph_version_path
    list_graph_versions_fn: Callable[[], list[GraphVersionInfo]] = list_graph_versions
    can_materialize_graph_version_fn: Callable[[], bool] = can_materialize_graph_version
    materialize_graph_version_fn: Callable[[], GraphVersionInfo] = (
        materialize_new_graph_version_from_raw_source
    )
    graph_path_fn: Callable[[], Path] = graph_path
    preferred_graph_source_path_fn: Callable[[], Path | None] = preferred_graph_source_path
    wells_path_fn: Callable[[], Path] = wells_path
    save_graph_positions_fn: Callable[..., FlowGraphDocument] = (
        save_graph_positions_with_version_check
    )
    save_wells_fn: Callable[..., WellsDocument] = save_wells_with_version_check

    def load_documents(
        self,
        graph_version_id: str | None = None,
    ) -> tuple[FlowGraphDocument, WellsDocument]:
        if graph_version_id is None:
            return self.load_documents_fn()
        return self.load_documents_fn(
            graph_doc_path=self.resolve_graph_version_path_fn(graph_version_id)
        )

    def save_wells(
        self,
        document: WellsDocument,
        *,
        graph: FlowGraphDocument,
        expected_version: int,
    ) -> WellsDocument:
        return self.save_wells_fn(
            document,
            expected_version=expected_version,
            path=self.wells_path_fn(),
            graph=graph,
        )

    def save_graph_positions(
        self,
        positions: dict[str, tuple[float, float]],
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ) -> FlowGraphDocument:
        if graph_version_id is None:
            path = self.preferred_graph_source_path_fn() or self.graph_path_fn()
        else:
            path = self.resolve_graph_version_path_fn(graph_version_id)
        return self.save_graph_positions_fn(
            positions,
            expected_version=expected_version,
            path=path,
        )

    def list_graph_versions(self) -> list[GraphVersionInfo]:
        return self.list_graph_versions_fn()

    def can_materialize_graph_version(self) -> bool:
        return self.can_materialize_graph_version_fn()

    def materialize_graph_version(self) -> GraphVersionInfo:
        return self.materialize_graph_version_fn()
