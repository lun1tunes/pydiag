from __future__ import annotations

import pytest

from pydiag.infrastructure import (
    flow_graph_payload_from_figma_payload,
    is_figma_skeleton_payload,
    normalize_figma_skeleton_payload,
    update_figma_payload_positions,
)


def test_figma_skeleton_payload_is_detected() -> None:
    payload = {
        "version": 1,
        "elements": [
            {
                "id": "text_1",
                "name": "id=start;kind=figma_text",
                "type": "TEXT",
                "characters": "Start",
                "x": 10,
                "y": 20,
                "width": 120,
                "height": 32,
            }
        ],
    }

    assert is_figma_skeleton_payload(payload) is True


def test_figma_components_payload_with_shape_text_is_detected() -> None:
    payload = {
        "components": [
            {
                "id": "shape_1",
                "name": "Start",
                "type": "SHAPE_WITH_TEXT",
                "x": 10,
                "y": 20,
                "width": 120,
                "height": 32,
            }
        ]
    }

    assert is_figma_skeleton_payload(payload) is True


def test_figma_payload_converts_texts_and_connectors_to_flow_graph_payload() -> None:
    payload = {
        "version": 3,
        "responsibles": {
            "planning": {
                "label": "Планирование",
                "fill": "#dcecff",
                "border": "#356ca8",
                "text": "#17314f",
            }
        },
        "elements": [
            {
                "id": "text_start",
                "name": "id=start;kind=process;responsible=planning;time=1 hour",
                "type": "TEXT",
                "characters": "Start",
                "fontSize": 18,
                "x": 10,
                "y": 20,
                "width": 180,
                "height": 60,
            },
            {
                "id": "text_end",
                "name": "id=end;kind=event",
                "type": "TEXT",
                "characters": "End",
                "fontSize": 18,
                "x": 260,
                "y": 20,
                "width": 160,
                "height": 60,
            },
            {
                "id": "conn_1",
                "name": "id=edge_1;kind=usual;source=start;target=end",
                "type": "CONNECTOR",
                "x": 190,
                "y": 50,
                "width": 70,
                "height": 2,
                "rotation": 0,
            },
        ],
    }

    graph_payload = flow_graph_payload_from_figma_payload(payload)

    assert graph_payload["version"] == 3
    assert [node["id"] for node in graph_payload["nodes"]] == ["start", "end"]
    assert graph_payload["nodes"][0]["type"] == "process"
    assert graph_payload["nodes"][0]["responsible"] == ["planning"]
    assert graph_payload["nodes"][0]["time"] == "1 hour"
    assert graph_payload["nodes"][1]["type"] == "event"
    assert graph_payload["edges"][0]["source"] == "start"
    assert graph_payload["edges"][0]["target"] == "end"


def test_figma_components_payload_converts_shape_texts_and_connectors_to_flow_graph_payload() -> (
    None
):
    payload = {
        "components": [
            {
                "id": "shape_1",
                "name": "Start",
                "type": "SHAPE_WITH_TEXT",
                "x": 0,
                "y": 0,
                "width": 120,
                "height": 60,
            },
            {
                "id": "shape_2",
                "name": "End",
                "type": "SHAPE_WITH_TEXT",
                "x": 220,
                "y": 0,
                "width": 120,
                "height": 60,
            },
            {
                "id": "conn_1",
                "name": "Connector line",
                "type": "CONNECTOR",
                "x": 120,
                "y": 29,
                "width": 100,
                "height": 2,
                "rotation": 0,
            },
        ]
    }

    graph_payload = flow_graph_payload_from_figma_payload(payload)

    assert graph_payload["version"] == 1
    assert [node["id"] for node in graph_payload["nodes"]] == ["shape_1", "shape_2"]
    assert graph_payload["nodes"][0]["type"] == "figma_text"
    assert graph_payload["nodes"][0]["text"] == "Start"
    assert graph_payload["responsibles"] == {
        "default": {
            "label": "По умолчанию",
            "fill": "#eef2f6",
            "border": "#64748b",
            "text": "#253041",
        }
    }
    assert graph_payload["edges"][0]["source"] == "shape_1"
    assert graph_payload["edges"][0]["target"] == "shape_2"


def test_figma_payload_clamps_text_node_size_to_domain_bounds() -> None:
    payload = {
        "components": [
            {
                "id": "tiny",
                "name": "I",
                "type": "SHAPE_WITH_TEXT",
                "x": 0,
                "y": 0,
                "width": 30,
                "height": 30,
            },
            {
                "id": "wide",
                "name": "Very wide heading",
                "type": "TEXT",
                "characters": "Very wide heading",
                "x": 220,
                "y": 0,
                "width": 1463,
                "height": 900,
            },
        ]
    }

    graph_payload = flow_graph_payload_from_figma_payload(payload)

    assert graph_payload["nodes"][0]["size"] == {"w": 80, "h": 40}
    assert graph_payload["nodes"][1]["size"] == {"w": 1200, "h": 800}


def test_figma_payload_prefers_structured_flow_metadata_over_legacy_name_tokens() -> (
    None
):
    payload = {
        "version": 2,
        "elements": [
            {
                "id": "text_start",
                "name": "id=legacy_start;kind=event",
                "type": "TEXT",
                "characters": "Start",
                "x": 10,
                "y": 20,
                "width": 180,
                "height": 60,
                "flowNode": {
                    "id": "start",
                    "type": "process",
                    "responsibles": ["planning"],
                    "time": "1 hour",
                },
            },
            {
                "id": "text_end",
                "name": "id=legacy_end;kind=process;responsible=planning",
                "type": "TEXT",
                "characters": "End",
                "x": 260,
                "y": 20,
                "width": 160,
                "height": 60,
                "flowNode": {
                    "id": "end",
                    "type": "event",
                },
            },
            {
                "id": "conn_1",
                "name": "id=legacy_edge;kind=no;source=legacy_start;target=legacy_end;label=Нет",
                "type": "CONNECTOR",
                "x": 190,
                "y": 50,
                "width": 70,
                "height": 2,
                "rotation": 0,
                "flowEdge": {
                    "id": "edge_1",
                    "kind": "usual",
                    "source": "start",
                    "target": "end",
                    "label": "Go",
                },
            },
        ],
    }

    graph_payload = flow_graph_payload_from_figma_payload(payload)

    assert [node["id"] for node in graph_payload["nodes"]] == ["start", "end"]
    assert graph_payload["nodes"][0]["type"] == "process"
    assert graph_payload["nodes"][0]["responsible"] == ["planning"]
    assert graph_payload["nodes"][0]["time"] == "1 hour"
    assert graph_payload["nodes"][1]["type"] == "event"
    assert graph_payload["edges"][0]["id"] == "edge_1"
    assert graph_payload["edges"][0]["kind"] == "usual"
    assert graph_payload["edges"][0]["source"] == "start"
    assert graph_payload["edges"][0]["target"] == "end"
    assert graph_payload["edges"][0]["label"] == "Go"


def test_figma_connector_can_infer_terminals_from_geometry() -> None:
    payload = {
        "version": 1,
        "elements": [
            {
                "id": "text_a",
                "name": "id=node_a",
                "type": "TEXT",
                "characters": "A",
                "x": 0,
                "y": 0,
                "width": 80,
                "height": 40,
            },
            {
                "id": "text_b",
                "name": "id=node_b",
                "type": "TEXT",
                "characters": "B",
                "x": 220,
                "y": 0,
                "width": 80,
                "height": 40,
            },
            {
                "id": "conn",
                "name": "id=edge_ab",
                "type": "CONNECTOR",
                "x": 80,
                "y": 19,
                "width": 140,
                "height": 2,
                "rotation": 0,
            },
        ],
    }

    graph_payload = flow_graph_payload_from_figma_payload(payload)

    assert graph_payload["edges"][0]["source"] == "node_a"
    assert graph_payload["edges"][0]["target"] == "node_b"


def test_update_figma_payload_positions_updates_raw_text_coordinates_and_version() -> (
    None
):
    payload = {
        "version": 2,
        "elements": [
            {
                "id": "text_start",
                "name": "id=start;kind=figma_text",
                "type": "TEXT",
                "characters": "Start",
                "x": 10,
                "y": 20,
                "width": 180,
                "height": 60,
            }
        ],
    }

    updated = update_figma_payload_positions(
        payload, {"start": (44.345, 88.991)}, expected_version=2
    )

    assert updated["version"] == 3
    assert updated["elements"][0]["x"] == 44.34
    assert updated["elements"][0]["y"] == 88.99


def test_update_figma_payload_positions_updates_shape_text_coordinates_and_version() -> (
    None
):
    payload = {
        "components": [
            {
                "id": "shape_1",
                "name": "Start",
                "type": "SHAPE_WITH_TEXT",
                "x": 10,
                "y": 20,
                "width": 180,
                "height": 60,
            }
        ],
    }

    updated = update_figma_payload_positions(
        payload, {"shape_1": (44.345, 88.991)}, expected_version=1
    )

    assert updated["version"] == 2
    assert updated["components"][0]["x"] == 44.34
    assert updated["components"][0]["y"] == 88.99


def test_normalize_figma_skeleton_payload_adds_structured_semantics() -> None:
    payload = {
        "version": 1,
        "elements": [
            {
                "id": "text_start",
                "name": "id=start;kind=process;responsible=planning;time=1 hour",
                "type": "TEXT",
                "characters": "Start",
                "x": 10,
                "y": 20,
                "width": 180,
                "height": 60,
            },
            {
                "id": "text_end",
                "name": "id=end;kind=event",
                "type": "TEXT",
                "characters": "End",
                "x": 260,
                "y": 20,
                "width": 160,
                "height": 60,
            },
            {
                "id": "conn_1",
                "name": "id=edge_1;kind=usual;source=start;target=end",
                "type": "CONNECTOR",
                "x": 190,
                "y": 50,
                "width": 70,
                "height": 2,
                "rotation": 0,
            },
        ],
    }

    normalized = normalize_figma_skeleton_payload(payload)

    assert normalized["schema_version"] == "figma-skeleton/2.0"
    assert normalized["elements"][0]["flowNode"] == {
        "id": "start",
        "type": "process",
        "responsibles": ["planning"],
        "time": "1 hour",
    }
    assert normalized["elements"][1]["flowNode"] == {
        "id": "end",
        "type": "event",
    }
    assert normalized["elements"][2]["flowEdge"] == {
        "id": "edge_1",
        "kind": "usual",
        "source": "start",
        "target": "end",
    }
    assert "flowNode" not in payload["elements"][0]
    assert (
        normalized["elements"][0]["name"]
        == "id=start;kind=process;responsible=planning;time=1 hour"
    )


def test_update_figma_payload_positions_uses_structured_flow_node_ids() -> None:
    payload = {
        "version": 2,
        "elements": [
            {
                "id": "text_start",
                "name": "id=legacy_start;kind=figma_text",
                "type": "TEXT",
                "characters": "Start",
                "x": 10,
                "y": 20,
                "width": 180,
                "height": 60,
                "flowNode": {
                    "id": "start",
                    "type": "figma_text",
                },
            }
        ],
    }

    updated = update_figma_payload_positions(
        payload, {"start": (44.345, 88.991)}, expected_version=2
    )

    assert updated["version"] == 3
    assert updated["elements"][0]["x"] == 44.34
    assert updated["elements"][0]["y"] == 88.99


def test_figma_payload_ignores_hidden_texts_and_connectors() -> None:
    payload = {
        "version": 1,
        "elements": [
            {
                "id": "text_visible",
                "name": "id=visible;kind=process;responsible=planning",
                "type": "TEXT",
                "characters": "Visible",
                "visible": True,
                "x": 10,
                "y": 10,
                "width": 100,
                "height": 40,
            },
            {
                "id": "text_hidden",
                "name": "id=hidden;kind=event",
                "type": "TEXT",
                "characters": "Hidden",
                "visible": False,
                "x": 220,
                "y": 10,
                "width": 100,
                "height": 40,
            },
            {
                "id": "conn_hidden",
                "name": "id=edge_hidden;source=visible;target=hidden",
                "type": "CONNECTOR",
                "visible": False,
                "x": 110,
                "y": 30,
                "width": 110,
                "height": 2,
                "rotation": 0,
            },
        ],
    }

    graph_payload = flow_graph_payload_from_figma_payload(payload)

    assert [node["id"] for node in graph_payload["nodes"]] == ["visible"]
    assert graph_payload["edges"] == []


def test_figma_payload_uses_version_one_for_versionless_raw_list() -> None:
    payload = [
        {
            "id": "text_start",
            "name": "id=start;kind=process;responsible=planning",
            "type": "TEXT",
            "characters": "Start",
            "x": 10,
            "y": 20,
            "width": 180,
            "height": 60,
        }
    ]

    graph_payload = flow_graph_payload_from_figma_payload(payload)

    assert graph_payload["version"] == 1
    assert graph_payload["nodes"][0]["id"] == "start"


def test_update_figma_payload_positions_rejects_unknown_graph_ids() -> None:
    payload = {
        "version": 2,
        "elements": [
            {
                "id": "text_start",
                "name": "id=start;kind=figma_text",
                "type": "TEXT",
                "characters": "Start",
                "x": 10,
                "y": 20,
                "width": 180,
                "height": 60,
            }
        ],
    }

    with pytest.raises(ValueError, match="Unknown graph node positions: missing"):
        update_figma_payload_positions(
            payload, {"missing": (1.0, 2.0)}, expected_version=2
        )


def test_update_figma_payload_positions_requires_object_payload_for_save() -> None:
    with pytest.raises(ValueError, match="requires an object payload"):
        update_figma_payload_positions([], {"start": (1.0, 2.0)}, expected_version=1)
