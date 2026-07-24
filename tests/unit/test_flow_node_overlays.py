from __future__ import annotations

from pydiag.rendering.flow_node_overlays import duration_label, responsible_abbreviation


def test_overlay_labels_compact_domain_values() -> None:
    assert duration_label("3 day") == "3 д"
    assert duration_label("1-2 hours") == "1–2 ч"
    assert responsible_abbreviation("Планирование") == "ПЛА"
    assert responsible_abbreviation("Health Safety Environment") == "HSE"
    assert responsible_abbreviation("Сейсмик", "Сейс") == "Сейс"
    assert responsible_abbreviation("Б", "Б") == "Б"
