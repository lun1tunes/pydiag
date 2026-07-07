from __future__ import annotations

from pydiag.rendering.flow_node_overlays import duration_label, responsible_abbreviation


def test_overlay_labels_compact_domain_values() -> None:
    assert duration_label("3 day") == "3 д"
    assert responsible_abbreviation("Планирование") == "ПЛА"
    assert responsible_abbreviation("Health Safety Environment") == "HSE"
