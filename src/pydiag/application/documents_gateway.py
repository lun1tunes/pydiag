from __future__ import annotations

from typing import Protocol

from pydiag.common.graph_versions import GraphVersionInfo, RawImportResult
from pydiag.domain.models import FlowGraphDocument, WellsDocument

__all__ = ["DocumentsGateway"]


class DocumentsGateway(Protocol):
    def load_documents(
        self,
        graph_version_id: str | None = None,
    ) -> tuple[FlowGraphDocument, WellsDocument]: ...

    def ensure_live_graph_source(self) -> object: ...

    def save_wells(
        self,
        document: WellsDocument,
        *,
        graph: FlowGraphDocument,
        expected_version: int,
    ) -> WellsDocument: ...

    def save_graph_positions(
        self,
        positions: dict[str, tuple[float, float]],
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ) -> FlowGraphDocument: ...

    def load_graph_source_node(
        self,
        node_id: str,
        *,
        graph_version_id: str | None = None,
    ) -> object: ...

    def load_graph_source_edge(
        self,
        edge_id: str,
        *,
        graph_version_id: str | None = None,
    ) -> object: ...

    def save_graph_source_node(
        self,
        command: object,
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ) -> FlowGraphDocument: ...

    def save_graph_source_edge(
        self,
        command: object,
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ) -> FlowGraphDocument: ...

    def create_graph_source_edge(
        self,
        command: object,
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ) -> FlowGraphDocument: ...

    def create_graph_source_node(
        self,
        command: object,
        *,
        expected_version: int,
        graph_version_id: str | None = None,
    ) -> FlowGraphDocument: ...

    def list_graph_versions(self) -> list[GraphVersionInfo]: ...

    def live_graph_source_exists(self) -> bool: ...

    def can_materialize_graph_version(self) -> bool: ...

    def materialize_graph_version(self) -> GraphVersionInfo: ...

    def can_import_raw_graph_source(self) -> bool: ...

    def import_live_graph_source_from_raw(self) -> RawImportResult: ...
