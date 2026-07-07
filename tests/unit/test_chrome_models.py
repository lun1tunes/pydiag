from __future__ import annotations

from pydiag.presentation.chrome import build_header_model, build_legend_model


def test_build_legend_model_preserves_public_labels_and_responsibles(documents) -> None:
    graph, _ = documents

    model = build_legend_model(graph)

    assert model.kind_title == "Типы блоков"
    assert [item.label for item in model.kind_items] == [
        "Процесс",
        "Решение",
        "База данных",
        "Входные данные",
        "Событие",
    ]
    assert model.responsible_title == "Цвета ответственных"
    assert model.responsible_items[0].key == "planning"
    assert model.responsible_items[0].label == "Планирование"
    assert model.responsible_items[0].fill == graph.responsibles["planning"].fill
    assert model.responsible_items[0].border == graph.responsibles["planning"].border


def test_build_header_model_counts_only_active_wells_and_busy_nodes(documents) -> None:
    graph, wells = documents
    active_wells = [well for well in wells.wells if not well.is_archived]
    busy_node_count = len({well.current_node_id for well in active_wells})

    model = build_header_model(graph, wells)
    metrics = {item.label: item.value for item in model.metrics}

    assert model.title == "Карта планирования и бурения"
    assert "current_node_id" in model.subtitle
    assert metrics == {
        "Узлы": len(graph.nodes),
        "Связи": len(graph.edges),
        "Скважины": len(active_wells),
        "Занятые этапы": busy_node_count,
    }
