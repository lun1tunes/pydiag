from __future__ import annotations

from .flow_route_geometry import NodeGeometry, RowBounds

ROUTE_ROW_LANE_GAP = 46
ROUTE_ROW_LANE_STEP = 18
ROUTE_GUTTER_GAP = 52
ROUTE_GUTTER_STEP = 18
ROUTE_OBSTACLE_MARGIN = 18
ROUTE_OBSTACLE_LANE_GAP = 18
ROUTE_CANVAS_PADDING = 24
ROUTE_ANCHOR_SIZE = 8

__all__ = [
    "ROUTE_ANCHOR_SIZE",
    "ROUTE_CANVAS_PADDING",
    "ROUTE_GUTTER_GAP",
    "ROUTE_GUTTER_STEP",
    "ROUTE_OBSTACLE_LANE_GAP",
    "ROUTE_OBSTACLE_MARGIN",
    "ROUTE_ROW_LANE_GAP",
    "ROUTE_ROW_LANE_STEP",
    "adjacent_row_lane_y",
    "distribute_lane_in_gap",
    "local_lane_gap_rows",
    "local_lane_key",
    "preferred_same_row_lane_side",
    "row_route_lane_y",
]


def row_route_lane_y(
    source: NodeGeometry,
    target: NodeGeometry,
    bounds: dict[int, RowBounds],
    lane_index: int,
) -> float:
    gap_rows = local_lane_gap_rows(source, target, bounds)
    if gap_rows is not None:
        upper_row, lower_row = gap_rows
        return distribute_lane_in_gap(bounds[upper_row].y_max, bounds[lower_row].y_min, lane_index)

    if source.row == target.row:
        side = preferred_same_row_lane_side(source.row, bounds)
        return adjacent_row_lane_y(source.row, side, bounds, lane_index)

    upper_row = min(source.row, target.row)
    lower_row = max(source.row, target.row)
    if lower_row == upper_row + 1 and upper_row in bounds and lower_row in bounds:
        gap_start = bounds[upper_row].y_max
        gap_end = bounds[lower_row].y_min
        return distribute_lane_in_gap(gap_start, gap_end, lane_index)

    side = "below" if target.row > source.row else "above"
    return adjacent_row_lane_y(source.row, side, bounds, lane_index)


def local_lane_key(
    source: NodeGeometry,
    target: NodeGeometry,
    bounds: dict[int, RowBounds],
) -> tuple[int, str]:
    gap_rows = local_lane_gap_rows(source, target, bounds)
    if gap_rows is not None:
        return (gap_rows[0], "gap")
    return (source.row, "above" if target.row < source.row else "below")


def local_lane_gap_rows(
    source: NodeGeometry,
    target: NodeGeometry,
    bounds: dict[int, RowBounds],
) -> tuple[int, int] | None:
    if source.row == target.row:
        side = preferred_same_row_lane_side(source.row, bounds)
        if side == "above" and source.row - 1 in bounds:
            return (source.row - 1, source.row)
        if side == "below" and source.row + 1 in bounds:
            return (source.row, source.row + 1)
        return None

    upper_row = min(source.row, target.row)
    lower_row = max(source.row, target.row)
    if lower_row == upper_row + 1 and upper_row in bounds and lower_row in bounds:
        return (upper_row, lower_row)
    return None


def preferred_same_row_lane_side(row: int, bounds: dict[int, RowBounds]) -> str:
    if row % 2 == 0 and row + 1 in bounds:
        return "below"
    if row % 2 == 1 and row - 1 in bounds:
        return "above"
    if row + 1 in bounds:
        return "below"
    return "above"


def adjacent_row_lane_y(
    row: int,
    side: str,
    bounds: dict[int, RowBounds],
    lane_index: int,
) -> float:
    current = bounds[row]
    if side == "above":
        if row - 1 in bounds:
            return distribute_lane_in_gap(
                bounds[row - 1].y_max,
                current.y_min,
                lane_index,
                prefer_lower=False,
            )
        return max(
            ROUTE_CANVAS_PADDING,
            current.y_min - ROUTE_ROW_LANE_GAP - lane_index * ROUTE_ROW_LANE_STEP,
        )

    if row + 1 in bounds:
        return distribute_lane_in_gap(current.y_max, bounds[row + 1].y_min, lane_index)
    return current.y_max + ROUTE_ROW_LANE_GAP + lane_index * ROUTE_ROW_LANE_STEP


def distribute_lane_in_gap(
    gap_start: float,
    gap_end: float,
    lane_index: int,
    prefer_lower: bool = True,
) -> float:
    middle = (gap_start + gap_end) / 2
    direction = 1 if prefer_lower else -1
    if lane_index:
        direction = 1 if lane_index % 2 else -1
    offset = ((lane_index + 1) // 2) * ROUTE_ROW_LANE_STEP
    lane = middle + direction * offset
    return min(gap_end - ROUTE_OBSTACLE_LANE_GAP, max(gap_start + ROUTE_OBSTACLE_LANE_GAP, lane))
