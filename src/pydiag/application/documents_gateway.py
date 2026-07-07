from __future__ import annotations

from typing import Protocol

from pydiag.common.graph_versions import GraphVersionInfo
from pydiag.domain.models import FlowGraphDocument, WellsDocument

__all__ = ["DocumentsGateway"]


class DocumentsGateway(Protocol):
    def load_documents(
        self,
        graph_version_id: str | None = None,
    ) -> tuple[FlowGraphDocument, WellsDocument]: ...

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

    def list_graph_versions(self) -> list[GraphVersionInfo]: ...

    def can_materialize_graph_version(self) -> bool: ...

    def materialize_graph_version(self) -> GraphVersionInfo: ...
