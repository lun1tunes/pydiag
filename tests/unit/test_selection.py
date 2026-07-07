from __future__ import annotations

from pydiag.presentation.selection import resolve_selection


def test_route_segment_selection_resolves_to_domain_edge(documents) -> None:
    graph, wells = documents

    selection_kind, selected = resolve_selection(
        "route::e_input_review::2",
        graph,
        wells,
    )

    assert selection_kind == "edge"
    assert selected is not None
    assert selected.id == "e_input_review"


def test_route_segment_selection_allows_colons_in_domain_edge_id(documents) -> None:
    graph, wells = documents
    graph.edges[0].id = "edge::with::colon"

    selection_kind, selected = resolve_selection(
        "route::edge::with::colon::2",
        graph,
        wells,
    )

    assert selection_kind == "edge"
    assert selected is not None
    assert selected.id == "edge::with::colon"
