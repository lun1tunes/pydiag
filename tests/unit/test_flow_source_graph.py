from __future__ import annotations

import pytest
from pydantic import ValidationError

from pydiag.infrastructure.editable_flow_graph import EditableFlowGraphNode
from pydiag.infrastructure.figma_metadata import normalize_flow_node_kind
from pydiag.infrastructure.flow_source_graph import (
    FlowSourceDocument,
    dump_flow_source_payload,
    editable_flow_graph_payload_from_source_payload,
    flow_source_payload_from_editable_payload,
    load_structured_payload,
)


def valid_flow_source_payload() -> dict[str, object]:
    return {
        "schema_version": "flow-source/1.0",
        "graph_id": "pilot-drilling",
        "title": "Pilot drilling flow",
        "version": 7,
        "responsibles": {
            "planning": {
                "label": "Planning",
                "type": "team",
                "fill": "#dcecff",
                "border": "#356ca8",
                "text": "#17314f",
            },
            "geology": {
                "label": "Geology",
                "type": "team",
                "fill": "#e3f7ea",
                "border": "#3f8a55",
                "text": "#17311e",
            },
            "hse": {
                "label": "HSE",
                "type": "team",
                "fill": "#ffe3e3",
                "border": "#b84c4c",
                "text": "#4e1717",
            },
        },
        "sections": {
            "intake": {
                "title": "Intake",
                "order": 10,
            }
        },
        "nodes": {
            "review_data": {
                "title": "Проверка комплекта данных",
                "kind": "process",
                "section": "intake",
                "responsible": "planning",
                "participants": ["geology"],
                "approvers": ["hse"],
                "duration": "40m",
                "tags": ["critical", "intake"],
                "source_ref": {"figma_text_id": "text_review"},
                "transitions": [
                    {"to": "data_complete"},
                ],
            },
            "data_complete": {
                "title": "Данные полные?",
                "kind": "decision_diamond",
                "responsible": "planning",
                "participants": ["geology"],
                "transitions": [
                    {
                        "to": "well_design",
                        "kind": "yes",
                        "condition": "dataset complete",
                    },
                    {
                        "to": "review_data",
                        "kind": "no",
                        "note": "вернуть на доработку",
                    },
                ],
            },
            "well_design": {
                "title": "Проект скважины",
                "kind": "process",
                "responsible": "geology",
                "duration": "2d",
            },
        },
        "layout": {
            "review_data": {
                "x": 380.0,
                "y": 60.0,
                "w": 320,
                "h": 120,
            }
        },
    }


def test_flow_source_payload_materializes_rich_editable_graph() -> None:
    editable_payload = editable_flow_graph_payload_from_source_payload(
        valid_flow_source_payload()
    )

    review_node = next(
        node for node in editable_payload["nodes"] if node["id"] == "review_data"
    )
    decision_node = next(
        node for node in editable_payload["nodes"] if node["id"] == "data_complete"
    )
    yes_edge = next(edge for edge in editable_payload["edges"] if edge["kind"] == "yes")
    no_edge = next(edge for edge in editable_payload["edges"] if edge["kind"] == "no")

    assert editable_payload["schema_version"] == "editable-flow-graph/1.0"
    assert review_node["participants"] == ["geology"]
    assert review_node["approvers"] == ["hse"]
    assert review_node["duration"] == "40 minutes"
    assert review_node["metadata"]["source_section"] == "intake"
    assert review_node["metadata"]["source_tags"] == "critical, intake"
    assert review_node["metadata"]["source_ref:figma_text_id"] == "text_review"
    assert decision_node["size"] == {"w": 280, "h": 96}
    assert yes_edge["label"] == "Да"
    assert yes_edge["metadata"]["condition"] == "dataset complete"
    assert no_edge["label"] == "Нет"
    assert no_edge["metadata"]["note"] == "вернуть на доработку"


def test_flow_source_duration_range_shorthand() -> None:
    payload = valid_flow_source_payload()
    payload["nodes"]["review_data"]["duration"] = "1-2h"
    payload["nodes"]["review_data"]["duration_context"] = "после запроса"
    document = FlowSourceDocument.model_validate(payload, strict=True)
    assert document.nodes["review_data"].duration == "1-2 hours"
    assert document.nodes["review_data"].duration_context == "после запроса"


def test_flow_source_payload_omits_deleted_nodes_and_their_edges() -> None:
    payload = valid_flow_source_payload()
    payload["nodes"]["review_data"]["deleted"] = True

    editable_payload = editable_flow_graph_payload_from_source_payload(payload)

    assert {node["id"] for node in editable_payload["nodes"]} == {
        "data_complete",
        "well_design",
    }
    assert editable_payload["edges"] == [
        {
            "id": "edge_data_complete_well_design_yes_1",
            "kind": "yes",
            "source": "data_complete",
            "target": "well_design",
            "label": "Да",
            "metadata": {"condition": "dataset complete"},
        }
    ]


def test_editable_flow_graph_payload_converts_back_to_flow_source_payload() -> None:
    editable_payload = editable_flow_graph_payload_from_source_payload(
        valid_flow_source_payload()
    )

    source_payload = flow_source_payload_from_editable_payload(
        editable_payload,
        graph_id="pilot-drilling",
        title="Pilot drilling flow",
    )

    review_node = source_payload["nodes"]["review_data"]
    decision_node = source_payload["nodes"]["data_complete"]
    no_transition = next(
        transition
        for transition in decision_node["transitions"]
        if transition["to"] == "review_data"
    )

    assert source_payload["schema_version"] == "flow-source/1.0"
    assert review_node["responsible"] == "planning"
    assert review_node["participants"] == ["geology"]
    assert review_node["approvers"] == ["hse"]
    assert review_node["duration"] == "40 minutes"
    assert review_node["section"] == "intake"
    assert review_node["tags"] == ["critical", "intake"]
    assert review_node["source_ref"]["figma_text_id"] == "text_review"
    assert source_payload["layout"]["review_data"] == {
        "x": 380.0,
        "y": 60.0,
        "w": 320,
        "h": 120,
    }
    assert no_transition["kind"] == "no"
    assert no_transition["label"] is None
    assert no_transition["note"] == "вернуть на доработку"


def test_editable_flow_graph_payload_roundtrips_custom_layout_without_metadata_leaks() -> None:
    payload = valid_flow_source_payload()
    payload["custom_layout"] = {
        "review_data": {
            "x": 811.25,
            "y": 455.5,
            "w": 320,
            "h": 120,
        }
    }

    editable_payload = editable_flow_graph_payload_from_source_payload(payload)
    review_node = next(
        node for node in editable_payload["nodes"] if node["id"] == "review_data"
    )
    assert review_node["metadata"]["_pydiag_custom_layout_x"] == 811.25
    assert review_node["metadata"]["_pydiag_custom_layout_y"] == 455.5

    source_payload = flow_source_payload_from_editable_payload(
        editable_payload,
        graph_id="pilot-drilling",
        title="Pilot drilling flow",
    )

    assert source_payload["custom_layout"]["review_data"] == {
        "x": 811.25,
        "y": 455.5,
        "w": 320,
        "h": 120,
    }
    assert "_pydiag_custom_layout_x" not in source_payload["nodes"]["review_data"]["metadata"]
    assert "_pydiag_custom_layout_y" not in source_payload["nodes"]["review_data"]["metadata"]


def test_dump_flow_source_payload_strips_figma_trace_metadata() -> None:
    payload = valid_flow_source_payload()
    payload["nodes"]["review_data"]["metadata"] = {
        "figma_source_id": "3029:949",
        "figma_parent_id": "875:1085",
        "figma_source_type": "SHAPE_WITH_TEXT",
        "kept": "value",
    }
    payload["nodes"]["data_complete"]["transitions"][0]["metadata"] = {
        "figma_source_id": "3029:1002",
        "figma_parent_id": "875:1085",
        "note": "keep me",
    }

    serialized = dump_flow_source_payload(payload)
    normalized = load_structured_payload(serialized)

    assert normalized["nodes"]["review_data"]["metadata"] == {"kept": "value"}
    assert normalized["nodes"]["data_complete"]["transitions"][0]["metadata"] == {
        "note": "keep me"
    }


def test_flow_source_document_migrates_decision_card_kind_to_process() -> None:
    payload = valid_flow_source_payload()
    payload["nodes"]["well_design"]["kind"] = "decision_card"

    document = FlowSourceDocument.model_validate(payload, strict=True)

    assert document.nodes["well_design"].kind == "process"


def test_editable_and_figma_paths_migrate_decision_card_kind_to_process() -> None:
    node = EditableFlowGraphNode.model_validate(
        {
            "id": "legacy_card",
            "kind": "decision_card",
            "title": "Legacy follow-up",
            "position": {"x": 10.0, "y": 20.0},
            "size": {"w": 320, "h": 120},
            "responsible": "planning",
        },
        strict=True,
    )

    assert node.kind == "process"
    assert normalize_flow_node_kind("decision_card") == "process"


def test_flow_source_document_rejects_unknown_transition_target() -> None:
    payload = valid_flow_source_payload()
    payload["nodes"]["review_data"]["transitions"] = [{"to": "missing_node"}]

    with pytest.raises(ValidationError, match="unknown transition target missing_node"):
        FlowSourceDocument.model_validate(payload, strict=True)


def test_flow_source_document_rejects_duplicate_responsibles_within_node() -> None:
    payload = valid_flow_source_payload()
    payload["nodes"]["review_data"]["participants"] = ["planning"]

    with pytest.raises(ValidationError, match="duplicate responsibles are not allowed"):
        FlowSourceDocument.model_validate(payload, strict=True)


def test_flow_source_document_accepts_missing_processes() -> None:
    payload = valid_flow_source_payload()
    document = FlowSourceDocument.model_validate(payload, strict=True)
    assert document.processes == {}


def test_flow_source_document_accepts_processes_and_rejects_overlap() -> None:
    payload = valid_flow_source_payload()
    payload["processes"] = {
        "intake_block": {
            "title": "Подготовка",
            "node_ids": ["review_data", "data_complete"],
        }
    }
    document = FlowSourceDocument.model_validate(payload, strict=True)
    assert document.processes["intake_block"].title == "Подготовка"
    assert document.processes["intake_block"].node_ids == ["review_data", "data_complete"]

    payload["processes"]["other"] = {
        "title": "Другой",
        "node_ids": ["review_data"],
    }
    with pytest.raises(ValidationError, match="belongs to multiple processes"):
        FlowSourceDocument.model_validate(payload, strict=True)


def test_flow_source_document_rejects_unknown_process_member() -> None:
    payload = valid_flow_source_payload()
    payload["processes"] = {
        "intake_block": {
            "title": "Подготовка",
            "node_ids": ["missing_node"],
        }
    }
    with pytest.raises(ValidationError, match="unknown node id missing_node"):
        FlowSourceDocument.model_validate(payload, strict=True)


def test_flow_source_processes_roundtrip_through_editable() -> None:
    payload = valid_flow_source_payload()
    payload["processes"] = {
        "intake_block": {
            "title": "Подготовка",
            "node_ids": ["review_data", "data_complete"],
        }
    }
    editable = editable_flow_graph_payload_from_source_payload(payload)
    assert editable["processes"]["intake_block"]["node_ids"] == [
        "review_data",
        "data_complete",
    ]
    restored = flow_source_payload_from_editable_payload(
        editable,
        graph_id="pilot-drilling",
        title="Pilot drilling flow",
    )
    assert restored["processes"]["intake_block"]["title"] == "Подготовка"
    assert restored["processes"]["intake_block"]["node_ids"] == [
        "review_data",
        "data_complete",
    ]


def test_create_and_delete_flow_source_process() -> None:
    from pydiag.common.graph_source_admin import (
        CreateGraphSourceProcessCommand,
        DeleteGraphSourceProcessCommand,
        UpdateGraphSourceProcessCommand,
    )
    from pydiag.infrastructure.flow_source_graph import (
        create_flow_source_payload_process,
        delete_flow_source_payload_process,
        update_flow_source_payload_process,
    )

    payload = valid_flow_source_payload()
    created = create_flow_source_payload_process(
        payload,
        command=CreateGraphSourceProcessCommand(
            title="Подготовка",
            node_ids=("review_data", "data_complete"),
        ),
        expected_version=7,
    )
    assert created["version"] == 8
    assert "block_podgotovka" in created["processes"]
    assert created["processes"]["block_podgotovka"]["node_ids"] == [
        "review_data",
        "data_complete",
    ]

    deleted = delete_flow_source_payload_process(
        created,
        command=DeleteGraphSourceProcessCommand(process_id="block_podgotovka"),
        expected_version=8,
    )
    assert deleted["version"] == 9
    assert "block_podgotovka" not in deleted.get("processes", {})


def test_update_process_empty_membership_deletes_process() -> None:
    from pydiag.common.graph_source_admin import (
        CreateGraphSourceProcessCommand,
        UpdateGraphSourceProcessCommand,
    )
    from pydiag.infrastructure.flow_source_graph import (
        create_flow_source_payload_process,
        update_flow_source_payload_process,
    )

    payload = valid_flow_source_payload()
    created = create_flow_source_payload_process(
        payload,
        command=CreateGraphSourceProcessCommand(
            title="Блок",
            node_ids=("review_data", "data_complete"),
            process_id="block_test",
        ),
        expected_version=7,
    )
    emptied = update_flow_source_payload_process(
        created,
        command=UpdateGraphSourceProcessCommand(
            process_id="block_test",
            node_ids=(),
        ),
        expected_version=8,
    )
    assert "block_test" not in emptied.get("processes", {})
    assert emptied["version"] == 9


def test_create_process_claims_members_and_deletes_emptied_donor() -> None:
    from pydiag.common.graph_source_admin import CreateGraphSourceProcessCommand
    from pydiag.infrastructure.flow_source_graph import create_flow_source_payload_process

    payload = valid_flow_source_payload()
    payload["processes"] = {
        "donor": {
            "title": "Донор",
            "node_ids": ["review_data", "data_complete"],
        }
    }
    created = create_flow_source_payload_process(
        payload,
        command=CreateGraphSourceProcessCommand(
            title="Новый",
            node_ids=("review_data", "data_complete"),
            process_id="block_new",
        ),
        expected_version=7,
    )
    assert "donor" not in created["processes"]
    assert created["processes"]["block_new"]["node_ids"] == [
        "review_data",
        "data_complete",
    ]


def test_soft_delete_node_removes_from_process_and_prunes_empty() -> None:
    from pydiag.common.graph_source_admin import (
        CreateGraphSourceProcessCommand,
        UpdateGraphSourceNodeCommand,
    )
    from pydiag.infrastructure.flow_source_graph import (
        create_flow_source_payload_process,
        update_flow_source_payload_node,
    )

    payload = valid_flow_source_payload()
    created = create_flow_source_payload_process(
        payload,
        command=CreateGraphSourceProcessCommand(
            title="Один",
            node_ids=("review_data",),
            process_id="block_one",
        ),
        expected_version=7,
    )
    node = created["nodes"]["review_data"]
    layout = created["layout"]["review_data"]
    soft_deleted = update_flow_source_payload_node(
        created,
        command=UpdateGraphSourceNodeCommand(
            node_id="review_data",
            title=node["title"],
            kind=node["kind"],
            layout_x=layout["x"],
            layout_y=layout["y"],
            layout_w=layout["w"],
            layout_h=layout["h"],
            responsible=node.get("responsible"),
            participants=tuple(node.get("participants") or []),
            approvers=tuple(node.get("approvers") or []),
            duration=node.get("duration"),
            note=node.get("note"),
            duration_context=node.get("duration_context"),
            deleted=True,
        ),
        expected_version=8,
    )
    assert "block_one" not in soft_deleted.get("processes", {})
