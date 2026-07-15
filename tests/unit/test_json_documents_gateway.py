from __future__ import annotations

from pathlib import Path

from pydiag.common.graph_source_admin import (
    GraphSourceEdgeDraft,
    GraphSourceNodeDraft,
    UpdateGraphSourceEdgeCommand,
    UpdateGraphSourceNodeCommand,
)
from pydiag.common.graph_versions import GraphVersionInfo
from pydiag.infrastructure.json_documents_gateway import JsonDocumentsGateway


def test_json_documents_gateway_delegates_to_storage_functions(documents) -> None:
    graph, wells = documents
    calls: list[tuple[object, ...]] = []
    version_info = GraphVersionInfo(
        id="flow_source.v0001.yaml",
        label="flow_source.v0001.yaml",
        path=Path("/tmp/flow_source.v0001.yaml"),
        is_versioned=True,
    )

    def fake_load_documents(*, graph_doc_path: Path | None = None):
        calls.append(("load_documents", graph_doc_path))
        return graph, wells

    def fake_resolve_graph_version_path(version_id: str | None) -> Path:
        calls.append(("resolve_graph_version_path", version_id))
        return version_info.path

    def fake_wells_path() -> Path:
        return Path("/tmp/test-wells.yaml")

    def fake_ensure_live_graph_source() -> Path:
        calls.append(("ensure_live_graph_source",))
        return Path("/tmp/flow_source.yaml")

    def fake_save_graph_positions(
        positions,
        *,
        expected_version: int,
        path: Path,
        layout_mode: str,
    ):
        calls.append(
            ("save_graph_positions", positions, expected_version, path, layout_mode)
        )
        return graph

    def fake_load_graph_source_node(path: Path, node_id: str) -> GraphSourceNodeDraft:
        calls.append(("load_graph_source_node", path, node_id))
        return GraphSourceNodeDraft(
            node_id=node_id,
            title="Node",
            kind="process",
            layout_x=100.0,
            layout_y=200.0,
            layout_w=320,
            layout_h=120,
            responsible="planning",
            participants=("geology",),
            approvers=(),
            duration="1 hour",
            note=None,
        )

    def fake_load_graph_source_edge(path: Path, edge_id: str) -> GraphSourceEdgeDraft:
        calls.append(("load_graph_source_edge", path, edge_id))
        return GraphSourceEdgeDraft(
            edge_id=edge_id,
            source="proc_initial_review",
            target="dec_data_complete",
            kind="default",
            label=None,
            condition=None,
            note=None,
        )

    def fake_save_graph_source_node(command, *, expected_version: int, path: Path):
        calls.append(("save_graph_source_node", command.node_id, expected_version, path))
        return graph

    def fake_save_graph_source_edge(command, *, expected_version: int, path: Path):
        calls.append(("save_graph_source_edge", command.edge_id, expected_version, path))
        return graph

    def fake_save_wells(document, *, expected_version: int, path: Path, graph):
        calls.append(("save_wells", document.version, expected_version, path, graph.version))
        return document

    def fake_list_graph_versions() -> list[GraphVersionInfo]:
        calls.append(("list_graph_versions",))
        return [version_info]

    def fake_can_materialize_graph_version() -> bool:
        calls.append(("can_materialize_graph_version",))
        return True

    def fake_materialize_graph_version() -> GraphVersionInfo:
        calls.append(("materialize_graph_version",))
        return version_info

    gateway = JsonDocumentsGateway(
        load_documents_fn=fake_load_documents,
        resolve_graph_version_path_fn=fake_resolve_graph_version_path,
        list_graph_versions_fn=fake_list_graph_versions,
        can_materialize_graph_version_fn=fake_can_materialize_graph_version,
        ensure_live_graph_source_fn=fake_ensure_live_graph_source,
        materialize_graph_version_fn=fake_materialize_graph_version,
        wells_path_fn=fake_wells_path,
        save_graph_positions_fn=fake_save_graph_positions,
        load_graph_source_node_fn=fake_load_graph_source_node,
        load_graph_source_edge_fn=fake_load_graph_source_edge,
        save_graph_source_node_fn=fake_save_graph_source_node,
        save_graph_source_edge_fn=fake_save_graph_source_edge,
        save_wells_fn=fake_save_wells,
    )

    assert gateway.load_documents() == (graph, wells)
    assert gateway.load_documents(version_info.id) == (graph, wells)
    assert gateway.ensure_live_graph_source() == Path("/tmp/flow_source.yaml")
    assert (
        gateway.save_wells(
            wells,
            graph=graph,
            expected_version=wells.version,
        )
        == wells
    )
    assert (
        gateway.save_graph_positions(
            {"proc_initial_review": (10.0, 20.0)},
            expected_version=graph.version,
            layout_mode="manual",
            graph_version_id=version_info.id,
        )
        == graph
    )
    assert gateway.load_graph_source_node("proc_initial_review").node_id == "proc_initial_review"
    assert gateway.load_graph_source_edge("e_review_decision").edge_id == "e_review_decision"
    assert (
        gateway.save_graph_source_node(
            UpdateGraphSourceNodeCommand(
                node_id="proc_initial_review",
                title="Updated node",
                kind="process",
                layout_x=100.0,
                layout_y=200.0,
                layout_w=320,
                layout_h=120,
                responsible="planning",
                participants=("geology",),
                approvers=(),
                duration="2 hours",
                note="note",
            ),
            expected_version=graph.version,
        )
        == graph
    )
    assert (
        gateway.save_graph_source_edge(
            UpdateGraphSourceEdgeCommand(
                edge_id="e_review_decision",
                source="proc_initial_review",
                target="card_data_rework",
                kind="dashed",
                label="обход",
                condition=None,
                note=None,
            ),
            expected_version=graph.version,
        )
        == graph
    )
    assert gateway.list_graph_versions() == [version_info]
    assert gateway.can_materialize_graph_version() is True
    assert gateway.materialize_graph_version() == version_info

    assert calls == [
        ("load_documents", None),
        ("resolve_graph_version_path", version_info.id),
        ("load_documents", version_info.path),
        ("ensure_live_graph_source",),
        ("save_wells", wells.version, wells.version, Path("/tmp/test-wells.yaml"), graph.version),
        ("resolve_graph_version_path", version_info.id),
        (
            "save_graph_positions",
            {"proc_initial_review": (10.0, 20.0)},
            graph.version,
            version_info.path,
            "manual",
        ),
        ("ensure_live_graph_source",),
        ("load_graph_source_node", Path("/tmp/flow_source.yaml"), "proc_initial_review"),
        ("ensure_live_graph_source",),
        ("load_graph_source_edge", Path("/tmp/flow_source.yaml"), "e_review_decision"),
        ("ensure_live_graph_source",),
        ("save_graph_source_node", "proc_initial_review", graph.version, Path("/tmp/flow_source.yaml")),
        ("ensure_live_graph_source",),
        ("save_graph_source_edge", "e_review_decision", graph.version, Path("/tmp/flow_source.yaml")),
        ("list_graph_versions",),
        ("can_materialize_graph_version",),
        ("materialize_graph_version",),
    ]
