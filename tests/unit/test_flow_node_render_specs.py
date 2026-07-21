from __future__ import annotations

from pydiag.rendering.flow_node_filters import wells_grouped_by_node
from pydiag.rendering.flow_node_render_specs import (
    MANUAL_LAYOUT_SIZE_META,
    build_node_render_specs,
    node_render_spec,
)


def test_build_node_render_specs_keeps_content_and_minimum_process_size(documents) -> None:
    graph, wells = documents
    node = next(item for item in graph.nodes if item.id == "proc_initial_review")

    render_specs = build_node_render_specs(graph, wells_grouped_by_node(wells))
    spec = render_specs[node.id]

    assert node.text in spec.content
    assert spec.width >= 200
    assert spec.height >= 56


def test_node_render_spec_hugs_text_by_default(documents) -> None:
    graph, _ = documents
    payload = graph.model_dump(mode="json")
    node_index = next(
        index for index, node in enumerate(payload["nodes"]) if node["id"] == "proc_initial_review"
    )
    payload["nodes"][node_index]["metadata"] = {}
    payload["nodes"][node_index]["text"] = "Короткий текст"
    payload["nodes"][node_index]["size"] = {"w": 460, "h": 300}
    oversized = type(graph).model_validate(payload, strict=True)

    spec = node_render_spec(oversized.nodes[node_index], oversized, [])

    assert spec.width < 460
    assert spec.height < 300


def test_node_render_spec_grows_for_longer_text_when_unlocked(documents) -> None:
    graph, _ = documents
    payload = graph.model_dump(mode="json")
    node_index = next(
        index for index, node in enumerate(payload["nodes"]) if node["id"] == "proc_initial_review"
    )
    payload["nodes"][node_index]["metadata"] = {}
    payload["nodes"][node_index]["size"] = {"w": 280, "h": 100}

    payload["nodes"][node_index]["text"] = "Короткий текст"
    short_graph = type(graph).model_validate(payload, strict=True)
    short_spec = node_render_spec(short_graph.nodes[node_index], short_graph, [])

    payload["nodes"][node_index]["text"] = (
        "Очень длинный текст для оценки переноса строк и увеличения высоты карточки " * 14
    )
    long_graph = type(graph).model_validate(payload, strict=True)
    long_spec = node_render_spec(long_graph.nodes[node_index], long_graph, [])

    assert long_spec.height > short_spec.height


def test_manual_layout_size_uses_yaml_dimensions(documents) -> None:
    graph, _ = documents
    payload = graph.model_dump(mode="json")
    node_index = next(
        index for index, node in enumerate(payload["nodes"]) if node["id"] == "proc_initial_review"
    )
    payload["nodes"][node_index]["metadata"] = {MANUAL_LAYOUT_SIZE_META: True}
    payload["nodes"][node_index]["text"] = "Короткий текст"
    payload["nodes"][node_index]["size"] = {"w": 460, "h": 300}
    sized = type(graph).model_validate(payload, strict=True)

    spec = node_render_spec(sized.nodes[node_index], sized, [])

    assert spec.width == 460
    assert spec.height == 300


def test_manual_layout_size_works_for_all_domain_kinds(documents) -> None:
    graph, _ = documents
    kinds = {
        "process": "proc_initial_review",
        "decision_diamond": "dec_operational_issue",
        "database": "db_offset_wells",
        "input_data": "input_geo_license",
        "event": "event_handover_done",
    }
    for kind, node_id in kinds.items():
        payload = graph.model_dump(mode="json")
        node_index = next(
            index for index, node in enumerate(payload["nodes"]) if node["id"] == node_id
        )
        assert payload["nodes"][node_index]["type"] == kind
        payload["nodes"][node_index]["metadata"] = {MANUAL_LAYOUT_SIZE_META: True}
        payload["nodes"][node_index]["text"] = "Короткий"
        payload["nodes"][node_index]["size"] = {"w": 340, "h": 180}
        sized = type(graph).model_validate(payload, strict=True)
        spec = node_render_spec(sized.nodes[node_index], sized, [])
        assert spec.width == 340, kind
        assert spec.height == 180, kind


def test_figma_fixed_size_preserves_imported_dimensions(documents) -> None:
    graph, _ = documents
    payload = graph.model_dump(mode="json")
    payload["nodes"][0]["type"] = "figma_text"
    payload["nodes"][0]["responsible"] = []
    payload["nodes"][0]["metadata"] = {"figma_fixed_size": True}
    payload["nodes"][0]["size"] = {"w": 321, "h": 87}
    figma_graph = type(graph).model_validate(payload, strict=True)

    spec = node_render_spec(figma_graph.nodes[0], figma_graph, [])

    assert spec.width == 321
    assert spec.height == 87
