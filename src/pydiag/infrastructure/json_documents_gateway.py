from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydiag.common.graph_versions import GraphVersionInfo, RawImportResult
from pydiag.domain.models import FlowGraphDocument, WellsDocument

from .graph_versions import (
    can_materialize_graph_version,
    can_import_raw_graph_source,
    ensure_live_graph_source,
    import_live_graph_source_from_raw,
    list_graph_versions,
    materialize_new_graph_version_from_raw_source,
    resolve_graph_version_path,
)
from .storage import (
    existing_default_graph_path,
    graph_path,
    live_graph_source_exists,
    load_graph_source_edge_draft,
    load_graph_source_node_draft,
    load_documents,
    preferred_graph_source_path,
    create_graph_source_edge_with_version_check,
    create_graph_source_node_with_version_check,
    save_graph_source_edge_with_version_check,
    save_graph_source_node_with_version_check,
    save_graph_positions_with_version_check,
    save_wells_with_version_check,
    source_graph_path,
    wells_path,
)

__all__ = ["JsonDocumentsGateway"]


@dataclass(frozen=True)
class JsonDocumentsGateway:
    load_documents_fn: Callable[..., tuple[FlowGraphDocument, WellsDocument]] = load_documents
    resolve_graph_version_path_fn: Callable[[str | None], Path] = resolve_graph_version_path
    list_graph_versions_fn: Callable[[], list[GraphVersionInfo]] = list_graph_versions
    can_materialize_graph_version_fn: Callable[[], bool] = can_materialize_graph_version
    can_import_raw_graph_source_fn: Callable[[], bool] = can_import_raw_graph_source
    ensure_live_graph_source_fn: Callable[[], Path] = ensure_live_graph_source
    materialize_graph_version_fn: Callable[[], GraphVersionInfo] = (
        materialize_new_graph_version_from_raw_source
    )
    import_live_graph_source_from_raw_fn: Callable[[], RawImportResult] = (
        import_live_graph_source_from_raw
    )
    graph_path_fn: Callable[[], Path] = graph_path
    preferred_graph_source_path_fn: Callable[[], Path | None] = preferred_graph_source_path
    existing_default_graph_path_fn: Callable[[], Path | None] = existing_default_graph_path
    live_graph_source_exists_fn: Callable[[], bool] = live_graph_source_exists
    source_graph_path_fn: Callable[[], Path] = source_graph_path
    wells_path_fn: Callable[[], Path] = wells_path
    save_graph_positions_fn: Callable[..., FlowGraphDocument] = (
        save_graph_positions_with_version_check
    )
    load_graph_source_node_fn: Callable[..., object] = load_graph_source_node_draft
    load_graph_source_edge_fn: Callable[..., object] = load_graph_source_edge_draft
    save_graph_source_node_fn: Callable[..., FlowGraphDocument] = (
        save_graph_source_node_with_version_check
    )
    save_graph_source_edge_fn: Callable[..., FlowGraphDocument] = (
        save_graph_source_edge_with_version_check
    )
    create_graph_source_edge_fn: Callable[..., FlowGraphDocument] = (
        create_graph_source_edge_with_version_check
    )
    create_graph_source_node_fn: Callable[..., FlowGraphDocument] = (
        create_graph_source_node_with_version_check
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

    def ensure_live_graph_source(self) -> Path:
        return self.ensure_live_graph_source_fn()

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
            # Live YAML, else newest archive, else existing materialized JSON.
            path = self.existing_default_graph_path_fn()
            if path is None:
                raise FileNotFoundError(
                    "Нет файла схемы для сохранения положения. "
                    "Выберите версию схемы или импортируйте данные."
                )
        else:
            path = self.resolve_graph_version_path_fn(graph_version_id)
        return self.save_graph_positions_fn(
            positions,
            expected_version=expected_version,
            path=path,
            layout_mode="manual",
        )

    def load_graph_source_node(
        self,
        node_id: str,
        *,
        graph_version_id: str | None = None,
    ) -> object:
        return self.load_graph_source_node_fn(
            self._graph_source_path(graph_version_id),
            node_id,
        )

    def load_graph_source_edge(
        self,
        edge_id: str,
        *,
        graph_version_id: str | None = None,
    ) -> object:
        return self.load_graph_source_edge_fn(
            self._graph_source_path(graph_version_id),
            edge_id,
        )

    def save_graph_source_node(
        self,
        command: object,
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ) -> FlowGraphDocument:
        return self.save_graph_source_node_fn(
            command,
            expected_version=expected_version,
            path=self._graph_source_path(graph_version_id),
        )

    def save_graph_source_edge(
        self,
        command: object,
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ) -> FlowGraphDocument:
        return self.save_graph_source_edge_fn(
            command,
            expected_version=expected_version,
            path=self._graph_source_path(graph_version_id),
        )

    def create_graph_source_edge(
        self,
        command: object,
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ) -> FlowGraphDocument:
        return self.create_graph_source_edge_fn(
            command,
            expected_version=expected_version,
            path=self._graph_source_path(graph_version_id),
        )

    def create_graph_source_node(
        self,
        command: object,
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ) -> FlowGraphDocument:
        return self.create_graph_source_node_fn(
            command,
            expected_version=expected_version,
            path=self._graph_source_path(graph_version_id),
        )

    def list_graph_versions(self) -> list[GraphVersionInfo]:
        return self.list_graph_versions_fn()

    def live_graph_source_exists(self) -> bool:
        return self.live_graph_source_exists_fn()

    def can_materialize_graph_version(self) -> bool:
        return self.can_materialize_graph_version_fn()

    def materialize_graph_version(self) -> GraphVersionInfo:
        return self.materialize_graph_version_fn()

    def can_import_raw_graph_source(self) -> bool:
        return self.can_import_raw_graph_source_fn()

    def import_live_graph_source_from_raw(self) -> RawImportResult:
        return self.import_live_graph_source_from_raw_fn()

    def _graph_source_path(self, graph_version_id: str | None) -> Path:
        if graph_version_id is None:
            return self.ensure_live_graph_source_fn()
        return self.resolve_graph_version_path_fn(graph_version_id)
