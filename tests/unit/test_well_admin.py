from __future__ import annotations

import pytest

from pydiag.application import CreateWellCommand, WellAdminService
from pydiag.domain import well_by_id


def test_well_admin_service_advances_well_by_edge(documents) -> None:
    graph, wells = documents
    service = WellAdminService(graph=graph, wells=wells, actor="pytest")

    updated = service.advance_well(
        well_id="well_1001",
        edge_id="e_review_decision",
        comment="advance",
    )

    moved = well_by_id(updated)["well_1001"]
    assert moved.current_node_id == "dec_data_complete"
    assert moved.history[-1].action == "move"
    assert moved.history[-1].by == "pytest"


def test_well_admin_service_rejects_unknown_edge(documents) -> None:
    graph, wells = documents
    service = WellAdminService(graph=graph, wells=wells, actor="pytest")

    with pytest.raises(ValueError, match="Unknown edge"):
        service.advance_well(well_id="well_1001", edge_id="missing")


def test_well_admin_service_rolls_back_and_deletes(documents) -> None:
    graph, wells = documents
    service = WellAdminService(graph=graph, wells=wells, actor="pytest")
    moved = service.advance_well(well_id="well_1001", edge_id="e_review_decision")

    rolled = WellAdminService(graph=graph, wells=moved, actor="pytest").rollback_well(
        well_id="well_1001",
        comment="rollback",
    )
    deleted = WellAdminService(graph=graph, wells=rolled, actor="pytest").delete_well(
        well_id="well_1004"
    )

    assert well_by_id(rolled)["well_1001"].current_node_id == "proc_initial_review"
    assert well_by_id(rolled)["well_1001"].history[-1].action == "rollback"
    assert "well_1004" not in well_by_id(deleted)


def test_well_admin_service_creates_well_from_command(documents) -> None:
    graph, wells = documents
    service = WellAdminService(graph=graph, wells=wells, actor="pytest")

    created = service.create_well(
        CreateWellCommand(
            well_id="well_new",
            name="New well",
            start_node_id="input_geo_license",
            metadata={"field": "North"},
            comment="manual-create",
        )
    )

    well = well_by_id(created)["well_new"]
    assert well.current_node_id == "input_geo_license"
    assert well.metadata == {"field": "North"}
    assert well.history[-1].by == "pytest"
