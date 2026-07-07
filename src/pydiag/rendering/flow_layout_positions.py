from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from pydiag.domain.models import FlowGraphDocument

from .flow_node_render_specs import NodeRenderSpec
from .flow_route_geometry import NodeGeometry, RowBounds

SNAKE_COLUMNS = 4
SNAKE_ORIGIN_X = 60
SNAKE_ORIGIN_Y = 80
SNAKE_CELL_WIDTH = 350
SNAKE_CELL_HEIGHT = 220

__all__ = [
    "SNAKE_CELL_HEIGHT",
    "SNAKE_CELL_WIDTH",
    "SNAKE_COLUMNS",
    "SNAKE_ORIGIN_X",
    "SNAKE_ORIGIN_Y",
    "build_node_geometries",
    "build_row_bounds",
    "layout_positions",
    "manual_row_lookup",
    "node_ports",
]


def layout_positions(
    graph: FlowGraphDocument,
    layout_mode: str = "snake",
    render_specs: dict[str, NodeRenderSpec] | None = None,
) -> dict[str, tuple[float, float]]:
    if layout_mode == "manual":
        return {node.id: (node.position.x, node.position.y) for node in graph.nodes}
    return snake_layout_positions(graph, render_specs or {})


def snake_layout_positions(
    graph: FlowGraphDocument,
    render_specs: dict[str, NodeRenderSpec],
) -> dict[str, tuple[float, float]]:
    positions: dict[str, tuple[float, float]] = {}
    y = SNAKE_ORIGIN_Y
    row_index = 0
    for row_start in range(0, len(graph.nodes), SNAKE_COLUMNS):
        row_nodes = graph.nodes[row_start : row_start + SNAKE_COLUMNS]
        row_height = max((render_specs[node.id].height for node in row_nodes), default=0)
        for row_col, node in enumerate(row_nodes):
            visual_col = row_col if row_index % 2 == 0 else SNAKE_COLUMNS - row_col - 1
            render_spec = render_specs[node.id]
            x = SNAKE_ORIGIN_X + visual_col * SNAKE_CELL_WIDTH
            x += max(0, (SNAKE_CELL_WIDTH - render_spec.width) / 2)
            positions[node.id] = (x, y)
        y += max(SNAKE_CELL_HEIGHT, row_height + 104)
        row_index += 1
    return positions


def node_ports(index: int, layout_mode: str) -> tuple[str, str]:
    if layout_mode != "snake":
        return "right", "left"
    row = index // SNAKE_COLUMNS
    if row % 2 == 0:
        return "right", "left"
    return "left", "right"


def build_node_geometries(
    graph: FlowGraphDocument,
    positions: dict[str, tuple[float, float]],
    render_specs: dict[str, NodeRenderSpec],
    layout_mode: str,
) -> dict[str, NodeGeometry]:
    manual_rows = (
        manual_row_lookup(graph, positions, render_specs) if layout_mode == "manual" else {}
    )
    geometries: dict[str, NodeGeometry] = {}
    for index, node in enumerate(graph.nodes):
        position = positions[node.id]
        render_spec = render_specs[node.id]
        if layout_mode == "manual":
            row, visual_col = manual_rows[node.id]
        else:
            row = index // SNAKE_COLUMNS
            row_col = index % SNAKE_COLUMNS
            visual_col = row_col if row % 2 == 0 else SNAKE_COLUMNS - row_col - 1
        geometries[node.id] = NodeGeometry(
            id=node.id,
            index=index,
            x=position[0],
            y=position[1],
            width=render_spec.width,
            height=render_spec.height,
            row=row,
            visual_col=visual_col,
        )
    return geometries


def manual_row_lookup(
    graph: FlowGraphDocument,
    positions: dict[str, tuple[float, float]],
    render_specs: dict[str, NodeRenderSpec],
) -> dict[str, tuple[int, int]]:
    rows: list[list[tuple[str, float, float]]] = []
    for node in graph.nodes:
        x, y = positions[node.id]
        center_y = y + render_specs[node.id].height / 2
        for row in rows:
            row_center = sum(item[2] for item in row) / len(row)
            if abs(center_y - row_center) <= SNAKE_CELL_HEIGHT / 2:
                row.append((node.id, x, center_y))
                break
        else:
            rows.append([(node.id, x, center_y)])

    rows.sort(key=lambda row: sum(item[2] for item in row) / len(row))
    lookup: dict[str, tuple[int, int]] = {}
    for row_index, row in enumerate(rows):
        for visual_col, item in enumerate(sorted(row, key=lambda value: value[1])):
            lookup[item[0]] = (row_index, visual_col)
    return lookup


def build_row_bounds(geometries: Mapping[str, NodeGeometry]) -> dict[int, RowBounds]:
    grouped: dict[int, list[NodeGeometry]] = defaultdict(list)
    for geometry in geometries.values():
        grouped[geometry.row].append(geometry)
    return {
        row: RowBounds(
            x_min=min(item.x for item in row_items),
            x_max=max(item.x + item.width for item in row_items),
            y_min=min(item.y for item in row_items),
            y_max=max(item.bottom for item in row_items),
        )
        for row, row_items in grouped.items()
    }
