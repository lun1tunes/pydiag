from __future__ import annotations

from pydiag.rendering.flow_node_shape_backgrounds import (
    database_background,
    decision_diamond_background,
    input_data_background,
)


def test_shape_background_builders_emit_svg_data_uris_with_expected_strokes() -> None:
    diamond = decision_diamond_background("#dcecff")
    input_data = input_data_background()
    database = database_background()

    assert diamond.startswith('url("data:image/svg+xml,')
    assert input_data.startswith('url("data:image/svg+xml,')
    assert database.startswith('url("data:image/svg+xml,')
    assert "%23000000" in diamond
    assert "%235477aa" in input_data
    assert "stroke-width%3D%271.6%27" in diamond
    assert "stroke-width%3D%271.6%27" in database
    assert "stroke-width%3D%270.85%27" in database
    assert "vector-effect%3D%27non-scaling-stroke%27" in database
    assert "%3Cellipse" in database
