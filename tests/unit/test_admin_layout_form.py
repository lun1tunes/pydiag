from __future__ import annotations

from pydiag.presentation.admin import (
    coalesce_layout_field,
    parse_graph_source_layout_form,
)


def test_coalesce_layout_field_prefers_non_empty_form_value() -> None:
    assert coalesce_layout_field("444.5", "100", 12.0) == "444.5"
    assert coalesce_layout_field(444.5, 100.0, 12.0) == "444.50"
    assert coalesce_layout_field("", "100.25", 12.0) == "100.25"
    assert coalesce_layout_field(None, None, 12.5) == "12.50"
    assert coalesce_layout_field("  ", None, 8) == "8"


def test_coalesce_layout_field_ignores_stale_secondary_when_form_has_value() -> None:
    # Submitted form value must win over any cached secondary (session) value.
    assert coalesce_layout_field(999.5, 100.0, 12.0) == "999.50"
    assert coalesce_layout_field("801", "733.50", 0) == "801"


def test_parse_graph_source_layout_form_accepts_blank_recovery_via_coalesce() -> None:
    layout = parse_graph_source_layout_form(
        layout_x=coalesce_layout_field("", None, 733.5),
        layout_y=coalesce_layout_field(None, None, 412.25),
        layout_w=coalesce_layout_field("", None, 180),
        layout_h=coalesce_layout_field("", None, 64),
    )

    assert layout == (733.5, 412.25, 180, 64)
