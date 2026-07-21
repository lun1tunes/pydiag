from __future__ import annotations

from pydiag.domain.models import Well, WellsDocument
from pydiag.infrastructure.flow_source_graph import (
    dump_structured_yaml_payload,
    load_structured_payload,
)


def test_dump_structured_yaml_keeps_empty_dict_and_list() -> None:
    text = dump_structured_yaml_payload({"metadata": {}, "tags": []})
    assert "metadata: {}" in text
    assert "tags: []" in text
    assert load_structured_payload(text.encode()) == {"metadata": {}, "tags": []}


def test_well_accepts_null_metadata_from_legacy_yaml() -> None:
    well = Well.model_validate(
        {
            "id": "well_1",
            "name": "Скв. 1",
            "current_node_id": "n1",
            "history": [],
            "metadata": None,
        },
        strict=True,
    )
    assert well.metadata == {}


def test_wells_document_roundtrips_empty_metadata_through_yaml() -> None:
    document = WellsDocument(
        version=1,
        wells=[
            Well(id="well_1", name="Скв. 1", current_node_id="n1", metadata={}),
        ],
    )
    text = dump_structured_yaml_payload(document.model_dump(mode="json"))
    loaded = WellsDocument.model_validate(
        load_structured_payload(text.encode()),
        strict=False,
    )
    assert loaded.wells[0].metadata == {}
