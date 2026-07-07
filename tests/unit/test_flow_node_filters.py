from __future__ import annotations

from pydiag.rendering.flow_node_filters import node_matches_filters, wells_grouped_by_node


def test_wells_grouped_by_node_excludes_archived_and_sorts_by_name(documents) -> None:
    _, wells = documents

    grouped = wells_grouped_by_node(wells)

    assert "event_handover_done" not in grouped
    assert [well.name for well in grouped["proc_initial_review"]] == sorted(
        well.name for well in grouped["proc_initial_review"]
    )


def test_node_matches_filters_searches_responsible_labels_and_well_names(documents) -> None:
    graph, wells = documents
    grouped = wells_grouped_by_node(wells)
    node = next(item for item in graph.nodes if item.id == "proc_initial_review")

    assert node_matches_filters(graph, node, "геология", [], [], grouped[node.id]) is True
    assert node_matches_filters(graph, node, "1001", [], [], grouped[node.id]) is True
    assert node_matches_filters(graph, node, "no-such-match", [], [], grouped[node.id]) is False


def test_node_matches_filters_respects_kind_and_responsible_filters(documents) -> None:
    graph, wells = documents
    grouped = wells_grouped_by_node(wells)
    node = next(item for item in graph.nodes if item.id == "proc_initial_review")

    assert node_matches_filters(graph, node, "", ["planning"], [], grouped[node.id]) is True
    assert node_matches_filters(graph, node, "", ["drilling"], [], grouped[node.id]) is False
    assert node_matches_filters(graph, node, "", [], ["process"], grouped[node.id]) is True
    assert node_matches_filters(graph, node, "", [], ["event"], grouped[node.id]) is False
