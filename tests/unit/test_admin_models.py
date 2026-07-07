from __future__ import annotations

from pydiag.application import CreateWellCommand
from pydiag.presentation.admin_models import (
    admin_panel_defaults,
    build_create_well_command,
    default_option_index,
    normalized_optional_text,
    suggest_well_id,
    transition_ids_for_well,
    transition_option_label,
    validate_create_well_identity,
)


def test_admin_panel_defaults_follow_selected_entity(documents) -> None:
    graph, wells = documents
    node = next(item for item in graph.nodes if item.id == "proc_initial_review")
    well = next(item for item in wells.wells if item.id == "well_1001")

    node_defaults = admin_panel_defaults(graph, "node", node)
    well_defaults = admin_panel_defaults(graph, "well", well)
    fallback_defaults = admin_panel_defaults(graph, "none", None)

    assert node_defaults.default_node_id == node.id
    assert node_defaults.default_well_id is None
    assert well_defaults.default_well_id == well.id
    assert well_defaults.default_node_id == graph.nodes[0].id
    assert fallback_defaults.default_node_id == graph.nodes[0].id


def test_default_option_index_uses_preferred_value_when_present() -> None:
    options = ["a", "b", "c"]

    assert default_option_index(options, "b") == 1
    assert default_option_index(options, "missing") == 0
    assert default_option_index(options, None) == 0


def test_transition_helpers_describe_current_well_choices(documents) -> None:
    graph, wells = documents
    well = next(item for item in wells.wells if item.id == "well_1001")

    transition_ids = transition_ids_for_well(graph, well)

    assert transition_ids == ["e_review_decision"]
    assert transition_option_label(graph, well, "e_review_decision").startswith("Далее:")


def test_validate_create_well_identity_checks_id_and_name() -> None:
    assert (
        validate_create_well_identity("bad id", "Well")
        == "ID должен состоять из латиницы, цифр, _, ., :, -"
    )
    assert validate_create_well_identity("well_ok", "   ") == "Название скважины обязательно."
    assert validate_create_well_identity("well_ok", "Well") is None


def test_build_create_well_command_normalizes_payload() -> None:
    command = build_create_well_command(
        well_id="  well_2001  ",
        name="  Скв. 2001 ",
        start_node_id="input_geo_license",
        field="  Северный куст ",
        rig="   ",
        comment="  создать вручную ",
    )

    assert isinstance(command, CreateWellCommand)
    assert command.well_id == "well_2001"
    assert command.name == "Скв. 2001"
    assert command.start_node_id == "input_geo_license"
    assert command.metadata == {"field": "Северный куст"}
    assert command.comment == "создать вручную"


def test_normalized_optional_text_and_suggest_well_id(documents) -> None:
    _, wells = documents

    assert normalized_optional_text("   ") is None
    assert normalized_optional_text("  note ") == "note"
    assert suggest_well_id(wells) == "well_1005"
