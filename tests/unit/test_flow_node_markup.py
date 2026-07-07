from __future__ import annotations

from pydiag.rendering.flow_node_markup import (
    duration_badge_content,
    responsible_badge_content,
    well_token_content,
)


def test_badge_and_token_markup_escape_and_format_values(documents) -> None:
    _graph, wells = documents
    well = next(item for item in wells.wells if item.id == "well_1001")

    well_markup = well_token_content(well)
    duration_markup = duration_badge_content("2 day")
    responsible_markup = responsible_badge_content("Geo & <Ops>")

    assert "Скв." in well_markup
    assert well.name.replace("Скв.", "").strip()[:16] in well_markup
    assert "2 д" in duration_markup
    assert "Geo &amp; &lt;Ops&gt;" in responsible_markup
    assert "<strong>GO</strong>" in responsible_markup
