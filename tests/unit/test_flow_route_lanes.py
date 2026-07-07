from __future__ import annotations

from pydiag.rendering.flow_route_geometry import RowBounds
from pydiag.rendering.flow_route_lanes import (
    adjacent_row_lane_y,
    distribute_lane_in_gap,
    preferred_same_row_lane_side,
)


def test_distribute_lane_in_gap_alternates_around_the_middle_and_clamps() -> None:
    assert distribute_lane_in_gap(100, 200, 0) == 150.0
    assert distribute_lane_in_gap(100, 200, 1) == 168.0
    assert distribute_lane_in_gap(100, 200, 2) == 132.0
    assert distribute_lane_in_gap(100, 200, 0, prefer_lower=False) == 150.0
    assert distribute_lane_in_gap(100, 200, 4) == 118.0
    assert distribute_lane_in_gap(100, 140, 4) == 118


def test_same_row_lane_side_prefers_neighbouring_gap_before_canvas_padding() -> None:
    bounds = {
        0: RowBounds(x_min=0, x_max=100, y_min=10, y_max=50),
        1: RowBounds(x_min=0, x_max=100, y_min=120, y_max=160),
        2: RowBounds(x_min=0, x_max=100, y_min=230, y_max=270),
    }

    assert preferred_same_row_lane_side(0, bounds) == "below"
    assert preferred_same_row_lane_side(1, bounds) == "above"
    assert preferred_same_row_lane_side(2, bounds) == "above"
    assert adjacent_row_lane_y(1, "above", bounds, 0) == 85.0
    assert adjacent_row_lane_y(2, "below", bounds, 0) == 316
