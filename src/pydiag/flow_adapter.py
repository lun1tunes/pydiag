from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from html import escape
from math import ceil, hypot
from urllib.parse import quote

from streamlit_flow.elements import StreamlitFlowEdge, StreamlitFlowNode

from .models import FlowEdge, FlowGraphDocument, FlowNode, Well, WellsDocument, parse_node_time

DURATION_BADGE_MIN_WIDTH = 64
DURATION_BADGE_MAX_WIDTH = 128
DURATION_BADGE_CHAR_WIDTH = 6.6
DURATION_BADGE_ICON_WIDTH = 14
DURATION_BADGE_HORIZONTAL_PADDING = 18
RESPONSIBLE_BADGE_MIN_WIDTH = 42
RESPONSIBLE_BADGE_MAX_WIDTH = 86
RESPONSIBLE_BADGE_HEIGHT = 24
RESPONSIBLE_BADGE_CHAR_WIDTH = 7.2
RESPONSIBLE_BADGE_HORIZONTAL_PADDING = 18
RESPONSIBLE_BADGE_GAP = 6
WELL_TOKEN_WIDTH = 136
WELL_TOKEN_HEIGHT = 42
WELL_TOKEN_COLUMN_GAP = 10
WELL_TOKEN_ROW_STEP = 50
WELL_TOKEN_STRIPE_WIDTH = 8
ROUTE_ANCHOR_SIZE = 0
ROUTE_ROW_LANE_GAP = 46
ROUTE_ROW_LANE_STEP = 18
ROUTE_GUTTER_GAP = 52
ROUTE_GUTTER_STEP = 18
ROUTE_OBSTACLE_MARGIN = 18
ROUTE_OBSTACLE_LANE_GAP = 18
ROUTE_CANVAS_PADDING = 24
EDGE_LABEL_GAP = 12
EDGE_LABEL_HEIGHT = 24
EDGE_LABEL_MIN_WIDTH = 42
EDGE_LABEL_CHAR_WIDTH = 9
EDGE_LABEL_HORIZONTAL_PADDING = 18
EDGE_LABEL_ROUTE_SIDE_GAP = 22
KIND_LABELS = {
    "process": "Процесс",
    "decision_diamond": "Решение",
    "decision_card": "Решение",
    "database": "База данных",
    "input_data": "Входные данные",
    "event": "Событие",
}
SNAKE_COLUMNS = 4
SNAKE_ORIGIN_X = 60
SNAKE_ORIGIN_Y = 80
SNAKE_CELL_WIDTH = 350
SNAKE_CELL_HEIGHT = 220
TEXT_LINE_HEIGHT = 16
TEXT_CHAR_WIDTH = 7.1
SHAPE_OUTLINE_STROKE_WIDTH = 1.6
SHAPE_DETAIL_STROKE_WIDTH = 0.85
FLOW_NODE_CSS = """
<style>
.route-anchor-node .react-flow__handle,
.react-flow__node.route-anchor-node .react-flow__handle,
.react-flow__node-route-anchor-node .react-flow__handle {
  left: 50% !important;
  top: 50% !important;
  right: auto !important;
  bottom: auto !important;
  width: 1px !important;
  min-width: 1px !important;
  height: 1px !important;
  min-height: 1px !important;
  transform: translate(-50%, -50%) !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  opacity: 0 !important;
  visibility: hidden !important;
  pointer-events: none !important;
}
.well-token-node .react-flow__handle,
.duration-badge-node .react-flow__handle,
.responsible-badge-node .react-flow__handle,
.edge-label-node .react-flow__handle {
  width: 0 !important;
  min-width: 0 !important;
  height: 0 !important;
  min-height: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  opacity: 0 !important;
  visibility: hidden !important;
  pointer-events: none !important;
}
.route-anchor-node,
.react-flow__node.route-anchor-node,
.react-flow__node-route-anchor-node {
  width: 0 !important;
  min-width: 0 !important;
  height: 0 !important;
  min-height: 0 !important;
  padding: 0 !important;
  border: 0 !important;
  background: transparent !important;
  box-shadow: none !important;
  outline: 0 !important;
  color: transparent !important;
  opacity: 0 !important;
  visibility: hidden !important;
  pointer-events: none !important;
}
.well-token-node .markdown-node,
.duration-badge-node .markdown-node,
.responsible-badge-node .markdown-node,
.edge-label-node .markdown-node {
  pointer-events: auto;
  height: 100%;
}
.well-token-node .markdown-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  white-space: nowrap;
}
.duration-badge-node .markdown-node {
  display: flex;
  align-items: center;
  justify-content: center;
  white-space: nowrap;
}
.responsible-badge-node .markdown-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  white-space: nowrap;
}
.edge-label-node .markdown-node {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  white-space: nowrap;
}
.duration-badge-node .duration-badge-content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  max-width: 100%;
}
.responsible-badge-node .responsible-badge-content {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  max-width: 100%;
}
.well-token-node .markdown-node p,
.duration-badge-node .markdown-node p,
.responsible-badge-node .markdown-node p,
.edge-label-node .markdown-node p {
  width: 100%;
  margin: 0 !important;
  text-align: center;
}
.flow-node-decision-diamond .markdown-node {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.flow-node-decision-diamond .markdown-node p {
  width: 100%;
  margin: 0 !important;
}
.flow-node .markdown-node {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}
.react-flow__node.flow-node:hover,
.react-flow__node-flow-node:hover,
.react-flow__node-flow-node-process:hover,
.react-flow__node-flow-node-decision-diamond:hover,
.react-flow__node-flow-node-decision-card:hover,
.react-flow__node-flow-node-database:hover,
.react-flow__node-flow-node-input-data:hover,
.react-flow__node-flow-node-event:hover,
.flow-node:hover {
  outline: 3px solid rgba(20, 184, 166, 0.36) !important;
  outline-offset: 4px !important;
  box-shadow:
    0 0 0 1px rgba(20, 184, 166, 0.20),
    0 18px 36px rgba(15, 23, 42, 0.18) !important;
}
.flow-node .node-card-text {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-weight: 760;
  line-height: 1.24;
  overflow-wrap: anywhere;
}
.flow-node .process-card-content {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  border-radius: 8px;
}
.flow-node .process-card-text {
  width: 100%;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-weight: 770;
  line-height: 1.24;
  overflow-wrap: anywhere;
}
</style>
""".strip()


@dataclass(frozen=True)
class NodeRenderSpec:
    content: str
    width: int
    height: int


@dataclass(frozen=True)
class NodeGeometry:
    id: str
    index: int
    x: float
    y: float
    width: int
    height: int
    row: int
    visual_col: int

    @property
    def center_x(self) -> float:
        return self.x + self.width / 2

    @property
    def center_y(self) -> float:
        return self.y + self.height / 2

    @property
    def bottom(self) -> float:
        return self.y + self.height


@dataclass(frozen=True)
class RowBounds:
    x_min: float
    x_max: float
    y_min: float
    y_max: float


@dataclass(frozen=True)
class RouteAnchor:
    id: str
    pos: tuple[float, float]
    source_position: str
    target_position: str


@dataclass(frozen=True)
class EdgeRoute:
    edge: FlowEdge
    anchors: tuple[RouteAnchor, ...]


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float


Point = tuple[float, float]


def wells_grouped_by_node(wells_doc: WellsDocument) -> dict[str, list[Well]]:
    grouped: dict[str, list[Well]] = defaultdict(list)
    for well in wells_doc.wells:
        if not well.is_archived:
            grouped[well.current_node_id].append(well)
    for wells in grouped.values():
        wells.sort(key=lambda item: item.name)
    return dict(grouped)


def node_matches_filters(
    graph: FlowGraphDocument,
    node: FlowNode,
    search: str,
    responsible_filter: list[str],
    kind_filter: list[str],
    wells_here: list[Well],
) -> bool:
    if kind_filter and node.kind not in kind_filter:
        return False

    node_responsibles = node.responsible
    if responsible_filter and not set(node_responsibles).intersection(responsible_filter):
        return False

    query = search.strip().lower()
    if not query:
        return True

    haystack = " ".join(
        [
            node.id,
            node.text,
            KIND_LABELS[node.kind],
            " ".join(node_responsibles),
            " ".join(
                graph.responsibles[responsible].label
                for responsible in node_responsibles
                if responsible in graph.responsibles
            ),
            " ".join(well.id for well in wells_here),
            " ".join(well.name for well in wells_here),
        ]
    ).lower()
    return query in haystack


def build_streamlit_nodes(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument,
    search: str = "",
    responsible_filter: list[str] | None = None,
    kind_filter: list[str] | None = None,
    selected_id: str | None = None,
    layout_mode: str = "snake",
) -> tuple[list[StreamlitFlowNode], set[str]]:
    responsible_filter = responsible_filter or []
    kind_filter = kind_filter or []
    wells_by_node = wells_grouped_by_node(wells_doc)
    nodes: list[StreamlitFlowNode] = []
    active_node_ids: set[str] = set()
    render_specs = build_node_render_specs(graph, wells_by_node)
    positions = layout_positions(graph, layout_mode, render_specs)
    routes = build_edge_routes(graph, positions, render_specs, layout_mode)

    for node_index, node in enumerate(graph.nodes):
        wells_here = wells_by_node.get(node.id, [])
        is_active = node_matches_filters(
            graph,
            node,
            search,
            responsible_filter,
            kind_filter,
            wells_here,
        )
        if is_active:
            active_node_ids.add(node.id)

        position = positions[node.id]
        render_spec = render_specs[node.id]
        source_position, target_position = node_ports(node_index, layout_mode)
        nodes.append(
            StreamlitFlowNode(
                id=node.id,
                pos=position,
                data={"content": render_spec.content},
                node_type="default",
                source_position=source_position,
                target_position=target_position,
                draggable=False,
                selectable=True,
                connectable=False,
                z_index=10 if node.id == selected_id else 1,
                className=flow_node_class_name(node),
                style=node_style(
                    node,
                    graph,
                    render_spec,
                    selected=node.id == selected_id,
                    active=is_active,
                ),
            )
        )

        if node.time is not None:
            nodes.append(
                StreamlitFlowNode(
                    id=f"duration::{node.id}",
                    pos=duration_badge_position(position),
                    data={"content": duration_badge_content(node.time)},
                    node_type="default",
                    draggable=False,
                    selectable=False,
                    connectable=False,
                    z_index=35,
                    className="duration-badge-node",
                    style=duration_badge_style(
                        active=is_active,
                        time_value=node.time,
                    ),
                )
            )

        for responsible_index, responsible in enumerate(node.secondary_responsibles):
            if responsible not in graph.responsibles:
                continue
            style = graph.responsibles[responsible]
            nodes.append(
                StreamlitFlowNode(
                    id=f"responsible::{node.id}::{responsible}",
                    pos=responsible_badge_position(
                        position,
                        node,
                        graph,
                        responsible_index,
                    ),
                    data={"content": responsible_badge_content(style.label)},
                    node_type="default",
                    draggable=False,
                    selectable=False,
                    connectable=False,
                    z_index=35,
                    className="responsible-badge-node",
                    style=responsible_badge_style(
                        active=is_active,
                        label=style.label,
                        fill=style.fill,
                        border=style.border,
                        text=style.text,
                    ),
                )
            )

        for well_index, well in enumerate(wells_here[:4]):
            token_id = f"well::{well.id}"
            token_active = (
                is_active or search.strip().lower() in (well.id + " " + well.name).lower()
            )
            nodes.append(
                StreamlitFlowNode(
                    id=token_id,
                    pos=well_token_position(position, render_spec.height, well_index),
                    data={"content": well_token_content(well)},
                    node_type="default",
                    draggable=False,
                    selectable=True,
                    connectable=False,
                    z_index=30 if token_id == selected_id else 20,
                    className="well-token-node",
                    style=well_token_style(
                        selected=token_id == selected_id,
                        active=token_active,
                    ),
                )
            )

        if len(wells_here) > 4:
            extra_id = f"well-extra::{node.id}"
            nodes.append(
                StreamlitFlowNode(
                    id=extra_id,
                    pos=well_token_position(position, render_spec.height, 4),
                    data={"content": f"{FLOW_NODE_CSS}\nСкв. **+{len(wells_here) - 4}**"},
                    node_type="default",
                    draggable=False,
                    selectable=False,
                    connectable=False,
                    z_index=19,
                    className="well-token-node",
                    style=well_token_style(selected=False, active=is_active),
                )
            )

    for route in routes:
        for anchor in route.anchors:
            nodes.append(route_anchor_node(anchor))

    geometries = build_node_geometries(graph, positions, render_specs, layout_mode)
    for route in routes:
        edge = route.edge
        if edge.kind in {"yes", "no"}:
            nodes.append(
                edge_label_node(
                    route,
                    geometries[edge.source],
                    geometries[edge.target],
                    active=edge.source in active_node_ids and edge.target in active_node_ids,
                    layout_mode=layout_mode,
                )
            )

    return nodes, active_node_ids


def layout_positions(
    graph: FlowGraphDocument,
    layout_mode: str = "snake",
    render_specs: dict[str, NodeRenderSpec] | None = None,
) -> dict[str, tuple[float, float]]:
    if layout_mode == "manual":
        return {node.id: (node.position.x, node.position.y) for node in graph.nodes}
    return snake_layout_positions(graph, render_specs or build_node_render_specs(graph, {}))


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


def flow_canvas_height(
    graph: FlowGraphDocument,
    wells_doc: WellsDocument | None = None,
    layout_mode: str = "snake",
) -> int:
    wells_by_node = wells_grouped_by_node(wells_doc) if wells_doc is not None else {}
    render_specs = build_node_render_specs(graph, wells_by_node)
    positions = layout_positions(graph, layout_mode, render_specs)

    bottom = 760
    for node in graph.nodes:
        wells_here = wells_by_node.get(node.id, [])
        token_space = well_token_stack_height(len(wells_here))
        bottom = max(
            bottom,
            int(positions[node.id][1] + render_specs[node.id].height + token_space + 150),
        )
    return bottom


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


def row_bounds(geometries: dict[str, NodeGeometry]) -> dict[int, RowBounds]:
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


def build_edge_routes(
    graph: FlowGraphDocument,
    positions: dict[str, tuple[float, float]],
    render_specs: dict[str, NodeRenderSpec],
    layout_mode: str,
) -> list[EdgeRoute]:
    geometries = build_node_geometries(graph, positions, render_specs, layout_mode)
    bounds = row_bounds(geometries)
    routes: list[EdgeRoute] = []
    row_lane_counts: dict[tuple[int, str], int] = defaultdict(int)

    for edge in graph.edges:
        source = geometries[edge.source]
        target = geometries[edge.target]
        if should_use_route_anchors(source, target):
            anchors = cycle_route_anchors(
                edge,
                source,
                target,
                bounds,
                row_lane_counts,
                layout_mode,
            )
        elif direct_route_obstacles(source, target, geometries, layout_mode):
            lane_key = local_lane_key(source, target, bounds)
            lane_index = row_lane_counts[lane_key]
            row_lane_counts[lane_key] += 1
            anchors = obstacle_avoidance_route_anchors(
                edge,
                source,
                target,
                geometries,
                bounds,
                lane_index,
                layout_mode,
            )
        else:
            anchors = ()

        routes.append(EdgeRoute(edge=edge, anchors=anchors))
    return routes


def should_use_route_anchors(source: NodeGeometry, target: NodeGeometry) -> bool:
    return source.id == target.id or target.index <= source.index


def cycle_route_anchors(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    bounds: dict[int, RowBounds],
    row_lane_counts: dict[tuple[int, str], int],
    layout_mode: str,
) -> tuple[RouteAnchor, ...]:
    if source.id == target.id:
        lane_key = (source.row, "self")
        lane_index = row_lane_counts[lane_key]
        row_lane_counts[lane_key] += 1
        return self_loop_route_anchors(edge, source, lane_index)

    lane_key = local_lane_key(source, target, bounds)
    lane_index = row_lane_counts[lane_key]
    row_lane_counts[lane_key] += 1
    return local_row_route_anchors(edge, source, target, bounds, lane_index, layout_mode)


def direct_route_obstacles(
    source: NodeGeometry,
    target: NodeGeometry,
    geometries: dict[str, NodeGeometry],
    layout_mode: str,
) -> list[NodeGeometry]:
    source_side, _ = node_ports(source.index, layout_mode)
    _, target_side = node_ports(target.index, layout_mode)
    start = port_point(source, source_side)
    end = port_point(target, target_side)
    obstacles = []
    for geometry in geometries.values():
        if geometry.id in {source.id, target.id}:
            continue
        if line_intersects_rect(start, end, node_rect(geometry, ROUTE_OBSTACLE_MARGIN)):
            obstacles.append(geometry)
    return sorted(
        obstacles,
        key=lambda item: distance_to_segment((item.center_x, item.center_y), start, end),
    )


def obstacle_avoidance_route_anchors(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    geometries: dict[str, NodeGeometry],
    bounds: dict[int, RowBounds],
    lane_index: int,
    layout_mode: str,
) -> tuple[RouteAnchor, ...]:
    _ = geometries
    return local_row_route_anchors(edge, source, target, bounds, lane_index, layout_mode)


def local_row_route_anchors(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    bounds: dict[int, RowBounds],
    lane_index: int,
    layout_mode: str,
) -> tuple[RouteAnchor, ...]:
    source_side, _ = node_ports(source.index, layout_mode)
    _, target_side = node_ports(target.index, layout_mode)
    source_port = port_point(source, source_side)
    target_port = port_point(target, target_side)
    source_exit = offset_point(source_port, source_side, ROUTE_OBSTACLE_MARGIN)
    target_entry = offset_point(target_port, target_side, ROUTE_OBSTACLE_MARGIN)
    lane_y = row_route_lane_y(source, target, bounds, lane_index)
    waypoints = simplify_waypoints(
        (
            source_exit,
            (source_exit[0], lane_y),
            (target_entry[0], lane_y),
            target_entry,
        )
    )
    return route_waypoints_to_anchors(edge, waypoints, source_side, target_side)


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


def node_rect(geometry: NodeGeometry, margin: float = 0) -> Rect:
    return Rect(
        left=geometry.x - margin,
        top=geometry.y - margin,
        right=geometry.x + geometry.width + margin,
        bottom=geometry.y + geometry.height + margin,
    )


def port_point(geometry: NodeGeometry, side: str) -> Point:
    if side == "left":
        return (geometry.x, geometry.center_y)
    if side == "right":
        return (geometry.x + geometry.width, geometry.center_y)
    if side == "top":
        return (geometry.center_x, geometry.y)
    return (geometry.center_x, geometry.bottom)


def offset_point(point: Point, side: str, distance: float) -> Point:
    if side == "left":
        return (point[0] - distance, point[1])
    if side == "right":
        return (point[0] + distance, point[1])
    if side == "top":
        return (point[0], point[1] - distance)
    return (point[0], point[1] + distance)


def point_in_rect(point: Point, rect: Rect) -> bool:
    return rect.left <= point[0] <= rect.right and rect.top <= point[1] <= rect.bottom


def line_intersects_rect(start: Point, end: Point, rect: Rect) -> bool:
    if point_in_rect(start, rect) or point_in_rect(end, rect):
        return True

    dx = end[0] - start[0]
    dy = end[1] - start[1]
    near_t = 0.0
    far_t = 1.0
    checks = (
        (-dx, start[0] - rect.left),
        (dx, rect.right - start[0]),
        (-dy, start[1] - rect.top),
        (dy, rect.bottom - start[1]),
    )
    for edge_delta, distance in checks:
        if edge_delta == 0:
            if distance < 0:
                return False
            continue
        t = distance / edge_delta
        if edge_delta < 0:
            if t > far_t:
                return False
            near_t = max(near_t, t)
        else:
            if t < near_t:
                return False
            far_t = min(far_t, t)
    return near_t <= far_t


def distance_to_segment(point: Point, start: Point, end: Point) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_squared = dx * dx + dy * dy
    if length_squared == 0:
        return hypot(point[0] - start[0], point[1] - start[1])
    ratio = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_squared
    ratio = min(1.0, max(0.0, ratio))
    projection = (start[0] + ratio * dx, start[1] + ratio * dy)
    return hypot(point[0] - projection[0], point[1] - projection[1])


def simplify_waypoints(points: list[Point]) -> tuple[Point, ...]:
    if len(points) <= 2:
        return tuple(points)
    simplified = [points[0]]
    for previous, current, next_point in zip(points[:-2], points[1:-1], points[2:], strict=True):
        if is_collinear(previous, current, next_point):
            continue
        simplified.append(current)
    simplified.append(points[-1])
    return tuple(simplified)


def is_collinear(first: Point, second: Point, third: Point) -> bool:
    return (first[0] == second[0] == third[0]) or (first[1] == second[1] == third[1])


def route_waypoints_to_anchors(
    edge: FlowEdge,
    waypoints: tuple[Point, ...],
    source_side: str,
    target_side: str,
) -> tuple[RouteAnchor, ...]:
    anchors: list[RouteAnchor] = []
    for index, point in enumerate(waypoints):
        previous_side = (
            opposite_side(source_side) if index == 0 else side_towards(point, waypoints[index - 1])
        )
        next_side = (
            opposite_side(target_side)
            if index == len(waypoints) - 1
            else side_towards(point, waypoints[index + 1])
        )
        anchors.append(
            RouteAnchor(
                id=route_anchor_id(edge.id, index),
                pos=point,
                source_position=next_side,
                target_position=previous_side,
            )
        )
    return tuple(anchors)


def side_towards(origin: Point, target: Point) -> str:
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    if abs(dx) >= abs(dy):
        return "right" if dx >= 0 else "left"
    return "bottom" if dy >= 0 else "top"


def opposite_side(side: str) -> str:
    return {
        "left": "right",
        "right": "left",
        "top": "bottom",
        "bottom": "top",
    }[side]


def row_span_bounds(
    bounds: dict[int, RowBounds],
    source_row: int,
    target_row: int,
) -> RowBounds:
    start = min(source_row, target_row)
    end = max(source_row, target_row)
    selected = [bounds[row] for row in range(start, end + 1) if row in bounds]
    return RowBounds(
        x_min=min(item.x_min for item in selected),
        x_max=max(item.x_max for item in selected),
        y_min=min(item.y_min for item in selected),
        y_max=max(item.y_max for item in selected),
    )


def self_loop_route_anchors(
    edge: FlowEdge,
    source: NodeGeometry,
    lane_index: int,
) -> tuple[RouteAnchor, ...]:
    lane_offset = ROUTE_GUTTER_GAP + lane_index * ROUTE_GUTTER_STEP
    lane_y = source.y - ROUTE_ROW_LANE_GAP - lane_index * ROUTE_ROW_LANE_STEP
    if outbound_gutter_side(source) == "right":
        first_x = source.x + source.width + lane_offset
        second_x = source.x - lane_offset
        first_target = "left"
        first_source = "top"
        middle_source = "left"
        last_target = "right"
        last_source = "bottom"
    else:
        first_x = source.x - lane_offset
        second_x = source.x + source.width + lane_offset
        first_target = "right"
        first_source = "top"
        middle_source = "right"
        last_target = "left"
        last_source = "bottom"

    return (
        RouteAnchor(
            id=route_anchor_id(edge.id, 0),
            pos=(first_x, source.center_y),
            source_position=first_source,
            target_position=first_target,
        ),
        RouteAnchor(
            id=route_anchor_id(edge.id, 1),
            pos=(first_x, lane_y),
            source_position=middle_source,
            target_position="bottom",
        ),
        RouteAnchor(
            id=route_anchor_id(edge.id, 2),
            pos=(second_x, lane_y),
            source_position=last_source,
            target_position=last_target,
        ),
    )


def same_row_route_anchors(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    bounds: RowBounds,
    lane_index: int,
) -> tuple[RouteAnchor, ...]:
    lane_y = bounds.y_min - ROUTE_ROW_LANE_GAP - lane_index * ROUTE_ROW_LANE_STEP
    direction = 1 if target.center_x >= source.center_x else -1
    horizontal_source = "right" if direction > 0 else "left"
    horizontal_target = "left" if direction > 0 else "right"
    return (
        RouteAnchor(
            id=route_anchor_id(edge.id, 0),
            pos=(source.center_x, lane_y),
            source_position=horizontal_source,
            target_position="bottom",
        ),
        RouteAnchor(
            id=route_anchor_id(edge.id, 1),
            pos=(target.center_x, lane_y),
            source_position="bottom",
            target_position=horizontal_target,
        ),
    )


def cross_row_route_anchors(
    edge: FlowEdge,
    source: NodeGeometry,
    target: NodeGeometry,
    source_bounds: RowBounds,
    side: str,
    lane_index: int,
) -> tuple[RouteAnchor, ...]:
    if side == "right":
        gutter_x = source_bounds.x_max + ROUTE_GUTTER_GAP + lane_index * ROUTE_GUTTER_STEP
        horizontal_target = "left"
        horizontal_source = "left"
    else:
        gutter_x = source_bounds.x_min - ROUTE_GUTTER_GAP - lane_index * ROUTE_GUTTER_STEP
        horizontal_target = "right"
        horizontal_source = "right"

    vertical_down = target.center_y >= source.center_y
    first_source = "bottom" if vertical_down else "top"
    second_target = "top" if vertical_down else "bottom"
    return (
        RouteAnchor(
            id=route_anchor_id(edge.id, 0),
            pos=(gutter_x, source.center_y),
            source_position=first_source,
            target_position=horizontal_target,
        ),
        RouteAnchor(
            id=route_anchor_id(edge.id, 1),
            pos=(gutter_x, target.center_y),
            source_position=horizontal_source,
            target_position=second_target,
        ),
    )


def outbound_gutter_side(source: NodeGeometry) -> str:
    if source.row % 2 == 0:
        return "right"
    return "left"


def route_anchor_id(edge_id: str, index: int) -> str:
    return f"route-anchor::{edge_id}::{index}"


def route_segment_id(edge_id: str, segment_index: int, label_segment_index: int) -> str:
    if segment_index == label_segment_index:
        return edge_id
    return f"route::{edge_id}::{segment_index}"


def route_anchor_node(anchor: RouteAnchor) -> StreamlitFlowNode:
    return StreamlitFlowNode(
        id=anchor.id,
        pos=(
            anchor.pos[0] - ROUTE_ANCHOR_SIZE / 2,
            anchor.pos[1] - ROUTE_ANCHOR_SIZE / 2,
        ),
        data={"content": FLOW_NODE_CSS},
        node_type="default",
        source_position=anchor.source_position,
        target_position=anchor.target_position,
        draggable=False,
        selectable=False,
        connectable=False,
        z_index=0,
        focusable=False,
        className="route-anchor-node",
        style=route_anchor_style(),
    )


def route_anchor_style() -> dict[str, str | float]:
    return {
        "width": f"{ROUTE_ANCHOR_SIZE}px",
        "height": f"{ROUTE_ANCHOR_SIZE}px",
        "minWidth": "0",
        "minHeight": "0",
        "boxSizing": "border-box",
        "padding": "0",
        "border": "0",
        "borderRadius": "0",
        "backgroundColor": "transparent",
        "background": "transparent",
        "color": "transparent",
        "fontSize": "0",
        "lineHeight": "0",
        "boxShadow": "none",
        "outline": "0",
        "opacity": 0.0,
        "visibility": "hidden",
        "pointerEvents": "none",
    }


def edge_label_node(
    route: EdgeRoute,
    source: NodeGeometry,
    target: NodeGeometry,
    active: bool,
    layout_mode: str,
) -> StreamlitFlowNode:
    edge = route.edge
    width = edge_label_width(edge)
    return StreamlitFlowNode(
        id=f"edge-label::{edge.id}",
        pos=edge_label_position(route, source, target, width, layout_mode),
        data={"content": edge_label_content(edge)},
        node_type="default",
        draggable=False,
        selectable=False,
        connectable=False,
        z_index=34,
        focusable=False,
        className=f"edge-label-node edge-label-node-{edge.kind}",
        style=edge_label_style(edge, active, width),
    )


def edge_label_position(
    route: EdgeRoute,
    source: NodeGeometry,
    target: NodeGeometry,
    label_width: int,
    layout_mode: str,
) -> tuple[float, float]:
    source_side, _ = node_ports(source.index, layout_mode)
    _, target_side = node_ports(target.index, layout_mode)
    points = (
        port_point(source, source_side),
        *(anchor.pos for anchor in route.anchors),
        port_point(target, target_side),
    )
    start, end = label_segment(
        points,
        label_width,
        prefer_horizontal=bool(route.anchors and route.edge.kind == "no"),
    )
    segment_dx = end[0] - start[0]
    segment_dy = end[1] - start[1]
    segment_length = hypot(segment_dx, segment_dy)
    if segment_length <= 0:
        return fallback_edge_label_position(source, label_width, layout_mode, route.edge.kind)

    unit = (segment_dx / segment_length, segment_dy / segment_length)
    along = min(
        max(EDGE_LABEL_GAP + EDGE_LABEL_HEIGHT, segment_length * 0.34),
        max(EDGE_LABEL_GAP, segment_length - EDGE_LABEL_GAP),
    )
    center = (start[0] + unit[0] * along, start[1] + unit[1] * along)

    if abs(segment_dy) >= abs(segment_dx):
        x = (
            center[0] + EDGE_LABEL_ROUTE_SIDE_GAP
            if route.edge.kind == "yes"
            else center[0] - label_width - EDGE_LABEL_ROUTE_SIDE_GAP
        )
        return (x, center[1] - EDGE_LABEL_HEIGHT / 2)

    y = (
        center[1] + EDGE_LABEL_GAP
        if route.edge.kind == "yes"
        else center[1] - EDGE_LABEL_HEIGHT - EDGE_LABEL_GAP
    )
    return (center[0] - label_width / 2, y)


def label_segment(
    points: tuple[Point, ...],
    label_width: int,
    prefer_horizontal: bool = False,
) -> tuple[Point, Point]:
    segments = list(zip(points[:-1], points[1:], strict=True))
    meaningful_length = max(label_width + EDGE_LABEL_ROUTE_SIDE_GAP, EDGE_LABEL_HEIGHT * 2)
    if prefer_horizontal:
        for start, end in segments:
            length = hypot(end[0] - start[0], end[1] - start[1])
            if abs(end[0] - start[0]) >= abs(end[1] - start[1]) and length >= meaningful_length:
                return start, end
    for start, end in segments:
        if hypot(end[0] - start[0], end[1] - start[1]) >= meaningful_length:
            return start, end
    return max(
        segments,
        key=lambda item: hypot(item[1][0] - item[0][0], item[1][1] - item[0][1]),
    )


def fallback_edge_label_position(
    source: NodeGeometry,
    label_width: int,
    layout_mode: str,
    edge_kind: str,
) -> tuple[float, float]:
    source_side, _ = node_ports(source.index, layout_mode)
    branch_offset = EDGE_LABEL_HEIGHT * 0.72
    if source_side == "left":
        y = source.center_y - EDGE_LABEL_HEIGHT / 2
        if edge_kind == "yes":
            y += branch_offset
        elif edge_kind == "no":
            y -= branch_offset
        return (
            source.x - EDGE_LABEL_GAP - label_width,
            y,
        )
    if source_side == "right":
        y = source.center_y - EDGE_LABEL_HEIGHT / 2
        if edge_kind == "yes":
            y += branch_offset
        elif edge_kind == "no":
            y -= branch_offset
        return (
            source.x + source.width + EDGE_LABEL_GAP,
            y,
        )
    x = source.center_x - label_width / 2
    if edge_kind == "yes":
        x -= label_width * 0.6
    elif edge_kind == "no":
        x += label_width * 0.6
    if source_side == "top":
        return (
            x,
            source.y - EDGE_LABEL_GAP - EDGE_LABEL_HEIGHT,
        )
    return (
        x,
        source.bottom + EDGE_LABEL_GAP,
    )


def edge_label_content(edge: FlowEdge) -> str:
    return f"{FLOW_NODE_CSS}\n<strong>{escape(edge_label_text(edge))}</strong>"


def edge_label_text(edge: FlowEdge) -> str:
    return edge.label or {"yes": "Да", "no": "Нет"}[edge.kind]


def edge_label_width(edge: FlowEdge) -> int:
    text_width = len(edge_label_text(edge)) * EDGE_LABEL_CHAR_WIDTH
    return max(
        EDGE_LABEL_MIN_WIDTH,
        ceil_to_step(int(ceil(text_width + EDGE_LABEL_HORIZONTAL_PADDING)), 2),
    )


def edge_label_style(
    edge: FlowEdge,
    active: bool,
    width: int,
) -> dict[str, str | float]:
    color = edge_color(edge)
    return {
        "width": f"{width}px",
        "height": f"{EDGE_LABEL_HEIGHT}px",
        "boxSizing": "border-box",
        "padding": "4px 9px",
        "borderRadius": "999px",
        "border": f"1px solid {color}",
        "backgroundColor": "#ffffff",
        "color": color,
        "fontSize": "12px",
        "fontWeight": 780,
        "lineHeight": "1",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 7px 16px rgba(15, 23, 42, 0.10)",
        "opacity": 1.0 if active else 0.24,
        "pointerEvents": "none",
        "transition": "opacity 160ms ease",
    }


def build_streamlit_edges(
    graph: FlowGraphDocument,
    active_node_ids: set[str] | None = None,
    wells_doc: WellsDocument | None = None,
    layout_mode: str = "snake",
) -> list[StreamlitFlowEdge]:
    if active_node_ids is None:
        active_node_ids = {node.id for node in graph.nodes}
    wells_by_node = wells_grouped_by_node(wells_doc) if wells_doc is not None else {}
    render_specs = build_node_render_specs(graph, wells_by_node)
    positions = layout_positions(graph, layout_mode, render_specs)
    routes = build_edge_routes(graph, positions, render_specs, layout_mode)
    edges: list[StreamlitFlowEdge] = []
    for route in routes:
        edges.extend(route_to_streamlit_edges(route, active_node_ids))
    return edges


def route_to_streamlit_edges(
    route: EdgeRoute,
    active_node_ids: set[str],
) -> list[StreamlitFlowEdge]:
    edge = route.edge
    active = edge.source in active_node_ids and edge.target in active_node_ids
    color = edge_color(edge)
    opacity = edge_opacity(edge, active)
    points = [edge.source, *(anchor.id for anchor in route.anchors), edge.target]
    final_segment_index = len(points) - 2
    label_segment_index = edge_label_segment_index(edge, final_segment_index, bool(route.anchors))
    segment_edges: list[StreamlitFlowEdge] = []

    for segment_index, (source, target) in enumerate(zip(points[:-1], points[1:], strict=True)):
        is_final = segment_index == final_segment_index
        carries_label = segment_index == label_segment_index
        label = edge_rendered_label(edge, carries_label)
        segment_edges.append(
            StreamlitFlowEdge(
                id=route_segment_id(edge.id, segment_index, label_segment_index),
                source=source,
                target=target,
                edge_type=edge_route_type(route),
                marker_end={"type": "arrowclosed", "color": color} if is_final else {},
                label=label,
                label_show_bg=bool(label),
                label_style={
                    "fill": color,
                    "fontWeight": 760,
                    "fontSize": "12px",
                },
                label_bg_style={
                    "fill": "#ffffff",
                    "fillOpacity": 0.96,
                    "rx": 7,
                    "ry": 7,
                    "stroke": color,
                    "strokeOpacity": 0.18,
                    "strokeWidth": 1,
                },
                z_index=edge_z_index(route, segment_index),
                focusable=False,
                style=edge_style(edge, opacity, is_route_segment=bool(route.anchors)),
                pathOptions={
                    "borderRadius": 18,
                    "offset": 22 if route.anchors else 14,
                },
                data={"domainEdgeId": edge.id},
            )
        )
    return segment_edges


def edge_label_segment_index(edge: FlowEdge, final_segment_index: int, has_route: bool) -> int:
    if not has_route:
        return 0
    if edge.kind in {"yes", "no"}:
        return 0
    return max(0, final_segment_index - 1)


def edge_rendered_label(edge: FlowEdge, carries_label: bool) -> str:
    # Domain edge labels stay in JSON for admin/inspector context. On the canvas
    # they render as tiny React Flow bubbles and visually compete with route labels.
    _ = edge
    _ = carries_label
    return ""


def edge_route_type(route: EdgeRoute) -> str:
    if not route.anchors:
        return direct_edge_type(route.edge)
    return "smoothstep"


def direct_edge_type(edge: FlowEdge) -> str:
    if edge.kind == "dashed":
        return "simplebezier"
    return "smoothstep"


def edge_z_index(route: EdgeRoute, segment_index: int) -> int:
    if not route.anchors:
        return 2 if route.edge.kind in {"yes", "no"} else 1
    if segment_index == len(route.anchors):
        return 3
    return 2


def edge_style(
    edge: FlowEdge,
    opacity: float,
    is_route_segment: bool,
) -> dict[str, str | float]:
    return {
        "stroke": edge_color(edge),
        "strokeWidth": edge_stroke_width(edge, is_route_segment),
        "strokeDasharray": "8 6" if edge.kind == "dashed" else "0",
        "strokeLinecap": "round",
        "strokeLinejoin": "round",
        "opacity": opacity,
    }


def edge_opacity(edge: FlowEdge, active: bool) -> float:
    if not active:
        return 0.12
    return {
        "usual": 0.78,
        "yes": 0.9,
        "no": 0.9,
        "dashed": 0.5,
    }[edge.kind]


def edge_stroke_width(edge: FlowEdge, is_route_segment: bool) -> float:
    if edge.kind == "dashed":
        return 1.8 if not is_route_segment else 2.0
    if edge.kind in {"yes", "no"}:
        return 2.4 if not is_route_segment else 2.5
    return 2.0 if not is_route_segment else 2.2


def node_content(node: FlowNode, graph: FlowGraphDocument, wells_here: list[Well]) -> str:
    _ = wells_here
    if uses_responsible_card_content(node):
        return responsible_node_content(node, graph)
    return generic_node_content(node)


def build_node_render_specs(
    graph: FlowGraphDocument,
    wells_by_node: dict[str, list[Well]],
) -> dict[str, NodeRenderSpec]:
    return {
        node.id: node_render_spec(node, graph, wells_by_node.get(node.id, []))
        for node in graph.nodes
    }


def node_render_spec(
    node: FlowNode,
    graph: FlowGraphDocument,
    wells_here: list[Well],
) -> NodeRenderSpec:
    lines = node_content_lines(node, graph, wells_here)
    width, height = fit_node_size(node, lines)
    return NodeRenderSpec(
        content=node_content(node, graph, wells_here),
        width=width,
        height=height,
    )


def node_content_lines(
    node: FlowNode,
    graph: FlowGraphDocument,
    wells_here: list[Well],
) -> list[str]:
    _ = graph
    _ = wells_here
    return [node.text]


def content_from_lines(lines: list[str]) -> str:
    return f"{FLOW_NODE_CSS}\n" + "  \n".join(lines)


def uses_responsible_card_content(node: FlowNode) -> bool:
    return node.kind in {"process", "decision_diamond", "decision_card"} and bool(node.responsible)


def responsible_node_content(node: FlowNode, graph: FlowGraphDocument) -> str:
    _ = graph
    return (
        f"{FLOW_NODE_CSS}\n"
        '<div class="process-card-content">'
        f'<div class="process-card-text">{escape(node.text)}</div>'
        "</div>"
    )


def generic_node_content(node: FlowNode) -> str:
    return f'{FLOW_NODE_CSS}\n<div class="node-card-text">{escape(node.text)}</div>'


def fit_node_size(node: FlowNode, lines: list[str]) -> tuple[int, int]:
    width = preferred_node_width(node, lines)
    wrapped_lines = sum(
        estimated_wrapped_lines(line, width, horizontal_text_padding(node)) for line in lines
    )
    height = ceil(
        vertical_text_padding(node)
        + wrapped_lines * TEXT_LINE_HEIGHT
        + markdown_vertical_buffer(node)
    )
    return width, max(node.size.h, minimum_node_height(node), height)


def preferred_node_width(node: FlowNode, lines: list[str]) -> int:
    longest_line = max((len(plain_canvas_text(line)) for line in lines), default=0)
    desired = (
        horizontal_text_padding(node)
        + min(longest_line, max_unwrapped_chars(node)) * TEXT_CHAR_WIDTH
    )
    width = ceil_to_step(int(ceil(desired)), 10)
    return max(node.size.w, minimum_node_width(node), min(width, maximum_node_width(node)))


def minimum_node_width(node: FlowNode) -> int:
    return {
        "process": 280,
        "decision_diamond": 230,
        "decision_card": 250,
        "database": 270,
        "input_data": 260,
        "event": 240,
    }[node.kind]


def maximum_node_width(node: FlowNode) -> int:
    return {
        "process": 330,
        "decision_diamond": 300,
        "decision_card": 320,
        "database": 330,
        "input_data": 320,
        "event": 300,
    }[node.kind]


def minimum_node_height(node: FlowNode) -> int:
    return {
        "process": 104,
        "decision_diamond": 112,
        "decision_card": 98,
        "database": 158,
        "input_data": 94,
        "event": 84,
    }[node.kind]


def horizontal_text_padding(node: FlowNode) -> int:
    return {
        "decision_diamond": 104,
        "input_data": 96,
        "database": 80,
        "event": 56,
    }.get(node.kind, 28)


def vertical_text_padding(node: FlowNode) -> int:
    return {
        "process": 28,
        "decision_diamond": 52,
        "decision_card": 34,
        "database": 92,
        "input_data": 36,
        "event": 32,
    }[node.kind]


def markdown_vertical_buffer(node: FlowNode) -> int:
    return {
        "database": 12,
        "decision_diamond": 10,
        "input_data": 8,
    }.get(node.kind, 8)


def max_unwrapped_chars(node: FlowNode) -> int:
    return {
        "decision_diamond": 22,
        "input_data": 28,
        "database": 30,
    }.get(node.kind, 32)


def estimated_wrapped_lines(text: str, width: int, horizontal_padding: int) -> int:
    available_width = max(96, width - horizontal_padding)
    chars_per_line = max(12, int(available_width / TEXT_CHAR_WIDTH))
    normalized = plain_canvas_text(text)
    return max(1, (len(normalized) + chars_per_line - 1) // chars_per_line)


def plain_canvas_text(text: str) -> str:
    without_html = re.sub(r"<[^>]+>", "", text)
    return (
        without_html.replace("*", "").replace("`", "").replace("_", "").replace("TIME ", "").strip()
    )


def should_show_note_on_canvas(node: FlowNode) -> bool:
    _ = node
    return False


def ceil_to_step(value: int, step: int) -> int:
    return int(ceil(value / step) * step)


def short_well_name(well: Well) -> str:
    name = well.name.replace("Скв.", "").replace("скв.", "").strip()
    return name[:16]


def responsible_abbreviation(label: str) -> str:
    words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+", label)
    if not words:
        return label[:4].upper()
    if len(words) > 1:
        return "".join(word[0] for word in words[:4]).upper()
    word = words[0]
    if word.isupper() and len(word) <= 6:
        return word
    return word[:3].upper()


def well_token_content(well: Well) -> str:
    return f"{FLOW_NODE_CSS}\nСкв. **{short_well_name(well)}**"


def duration_label(time_value: str) -> str:
    amount, unit = parse_node_time(time_value)
    unit_label = {
        "minute": "мин",
        "hour": "ч",
        "day": "д",
    }[unit]
    return f"{amount} {unit_label}"


def duration_badge_content(time_value: str) -> str:
    return (
        f"{FLOW_NODE_CSS}\n"
        '<span class="duration-badge-content">'
        f"&#9719; <strong>{duration_label(time_value)}</strong>"
        "</span>"
    )


def responsible_badge_content(label: str) -> str:
    return (
        f"{FLOW_NODE_CSS}\n"
        f'<span class="responsible-badge-content" title="{escape(label)}">'
        f"<strong>{escape(responsible_abbreviation(label))}</strong>"
        "</span>"
    )


def flow_node_class_name(node: FlowNode) -> str:
    return f"flow-node flow-node-{node.kind.replace('_', '-')}"


def duration_badge_width(time_value: str) -> int:
    text_width = len(duration_label(time_value)) * DURATION_BADGE_CHAR_WIDTH
    width = ceil_to_step(
        int(ceil(DURATION_BADGE_HORIZONTAL_PADDING + DURATION_BADGE_ICON_WIDTH + text_width)),
        2,
    )
    return max(DURATION_BADGE_MIN_WIDTH, min(width, DURATION_BADGE_MAX_WIDTH))


def responsible_badge_width(label: str) -> int:
    text_width = len(responsible_abbreviation(label)) * RESPONSIBLE_BADGE_CHAR_WIDTH
    width = ceil_to_step(
        int(ceil(RESPONSIBLE_BADGE_HORIZONTAL_PADDING + text_width)),
        2,
    )
    return max(RESPONSIBLE_BADGE_MIN_WIDTH, min(width, RESPONSIBLE_BADGE_MAX_WIDTH))


def primary_responsible_style(node: FlowNode, graph: FlowGraphDocument):
    primary_responsible = node.primary_responsible
    if primary_responsible in graph.responsibles:
        return graph.responsibles[primary_responsible]
    return next(iter(graph.responsibles.values()))


def node_style(
    node: FlowNode,
    graph: FlowGraphDocument,
    render_spec: NodeRenderSpec,
    selected: bool,
    active: bool,
) -> dict[str, str | float]:
    style: dict[str, str | float] = {
        "width": f"{render_spec.width}px",
        "height": f"{render_spec.height}px",
        "boxSizing": "border-box",
        "padding": "10px 14px",
        "fontSize": "12px",
        "lineHeight": "1.22",
        "fontFamily": "Inter, system-ui, sans-serif",
        "textAlign": "center",
        "wordBreak": "break-word",
        "overflowWrap": "anywhere",
        "whiteSpace": "normal",
        "overflow": "hidden",
        "opacity": 1.0 if active else 0.28,
        "transition": "opacity 160ms ease, box-shadow 160ms ease, transform 160ms ease",
    }

    if node.kind == "process":
        responsible = primary_responsible_style(node, graph)
        style.update(
            {
                "backgroundColor": responsible.fill,
                "border": f"2px solid {responsible.border}",
                "borderRadius": "8px",
                "color": responsible.text,
                "overflow": "visible",
                "boxShadow": "0 12px 26px rgba(15, 23, 42, 0.12)",
            }
        )
    elif node.kind == "decision_diamond":
        responsible = primary_responsible_style(node, graph)
        style.update(
            {
                "backgroundColor": "transparent",
                "backgroundImage": polygon_background(
                    points="50,2 98,50 50,98 2,50",
                    fill=responsible.fill,
                    stroke="#000000",
                ),
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "backgroundSize": "100% 100%",
                "border": "0",
                "padding": "24px 52px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
                "textAlign": "center",
                "color": responsible.text,
                "filter": "drop-shadow(0 12px 18px rgba(51, 65, 85, 0.12))",
            }
        )
    elif node.kind == "decision_card":
        responsible = primary_responsible_style(node, graph)
        style.update(
            {
                "backgroundColor": responsible.fill,
                "border": f"2px solid {responsible.border}",
                "borderRadius": "22px",
                "color": responsible.text,
                "boxShadow": "0 12px 24px rgba(15, 23, 42, 0.10)",
            }
        )
    elif node.kind == "database":
        style.update(
            {
                "background": "transparent",
                "backgroundImage": cylinder_background(),
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "backgroundSize": "100% 100%",
                "border": "0",
                "borderRadius": "0",
                "padding": "38px 40px",
                "fontSize": "11.5px",
                "lineHeight": "1.2",
                "textAlign": "center",
                "color": "#111827",
                "filter": "drop-shadow(0 12px 18px rgba(15, 23, 42, 0.13))",
            }
        )
    elif node.kind == "input_data":
        style.update(
            {
                "backgroundColor": "transparent",
                "backgroundImage": polygon_background(
                    points="13,2 98,2 87,98 2,98",
                    fill="#f1f7ff",
                    stroke="#5477aa",
                ),
                "backgroundPosition": "center",
                "backgroundRepeat": "no-repeat",
                "backgroundSize": "100% 100%",
                "border": "0",
                "padding": "16px 48px",
                "color": "#183557",
                "filter": "drop-shadow(0 12px 18px rgba(30, 64, 175, 0.10))",
            }
        )
    elif node.kind == "event":
        style.update(
            {
                "backgroundColor": "#ffffff",
                "border": "2px solid #111827",
                "borderRadius": "32px",
                "padding": "12px 28px",
                "color": "#111827",
                "boxShadow": "0 12px 22px rgba(15, 23, 42, 0.10)",
            }
        )

    if selected:
        style.update(
            {
                "boxShadow": "0 0 0 4px rgba(20, 184, 166, 0.24), 0 18px 36px rgba(15, 23, 42, 0.18)",
                "transform": "translateY(-1px)",
            }
        )

    return style


def polygon_background(points: str, fill: str, stroke: str) -> str:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' "
        "preserveAspectRatio='none'>"
        f"<polygon points='{points}' fill='{fill}' stroke='{stroke}' "
        f"stroke-width='{SHAPE_OUTLINE_STROKE_WIDTH}' "
        "stroke-linejoin='round' vector-effect='non-scaling-stroke'/>"
        "</svg>"
    )
    return f'url("data:image/svg+xml,{quote(svg, safe="")}")'


def cylinder_background() -> str:
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100' "
        "preserveAspectRatio='none'>"
        "<defs>"
        "<linearGradient id='body' x1='0' y1='0' x2='0' y2='1'>"
        "<stop offset='0' stop-color='#f8fafc'/>"
        "<stop offset='0.48' stop-color='#e3e8ef'/>"
        "<stop offset='1' stop-color='#cfd6e1'/>"
        "</linearGradient>"
        "<linearGradient id='top' x1='0' y1='0' x2='0' y2='1'>"
        "<stop offset='0' stop-color='#ffffff'/>"
        "<stop offset='1' stop-color='#e4e9f1'/>"
        "</linearGradient>"
        "</defs>"
        "<path d='M8 20 L8 78 C8 92 92 92 92 78 L92 20 Z' "
        "fill='url(#body)'/>"
        "<path d='M8 20 L8 78 C8 92 92 92 92 78 L92 20' "
        "fill='none' stroke='#5f6877' "
        f"stroke-width='{SHAPE_OUTLINE_STROKE_WIDTH}' "
        "vector-effect='non-scaling-stroke'/>"
        "<ellipse cx='50' cy='20' rx='42' ry='13' fill='url(#top)' "
        f"stroke='#5f6877' stroke-width='{SHAPE_OUTLINE_STROKE_WIDTH}' "
        "vector-effect='non-scaling-stroke'/>"
        "<path d='M14 23 C28 31 72 31 86 23' fill='none' "
        f"stroke='#9aa4b2' stroke-width='{SHAPE_DETAIL_STROKE_WIDTH}' "
        "opacity='0.7' vector-effect='non-scaling-stroke'/>"
        "</svg>"
    )
    return f'url("data:image/svg+xml,{quote(svg, safe="")}")'


def well_token_position(
    node_position: tuple[float, float],
    node_height: int,
    index: int,
) -> tuple[float, float]:
    row = index // 2
    col = index % 2
    return (
        node_position[0] + 14 + col * (WELL_TOKEN_WIDTH + WELL_TOKEN_COLUMN_GAP),
        node_position[1] + node_height + 12 + row * WELL_TOKEN_ROW_STEP,
    )


def duration_badge_position(node_position: tuple[float, float]) -> tuple[float, float]:
    return (node_position[0] + 10, node_position[1] - 30)


def responsible_badge_position(
    node_position: tuple[float, float],
    node: FlowNode,
    graph: FlowGraphDocument,
    responsible_index: int,
) -> tuple[float, float]:
    x = node_position[0] + 10
    if node.time is not None:
        x += duration_badge_width(node.time) + RESPONSIBLE_BADGE_GAP
    for responsible in node.secondary_responsibles[:responsible_index]:
        if responsible in graph.responsibles:
            x += responsible_badge_width(graph.responsibles[responsible].label)
            x += RESPONSIBLE_BADGE_GAP
    return (x, node_position[1] - 30)


def well_token_stack_height(well_count: int) -> int:
    if well_count <= 0:
        return 0
    visible_tokens = min(well_count, 5)
    rows = (visible_tokens + 1) // 2
    return 12 + rows * WELL_TOKEN_ROW_STEP


def well_token_style(selected: bool, active: bool) -> dict[str, str | float]:
    accent = "#0f766e" if selected else "#14b8a6"
    fill = "#ccfbf1" if selected else "#f0fdfa"
    return {
        "width": f"{WELL_TOKEN_WIDTH}px",
        "height": f"{WELL_TOKEN_HEIGHT}px",
        "boxSizing": "border-box",
        "padding": "0 16px",
        "borderRadius": "999px",
        "border": f"1px solid {accent}",
        "background": (
            f"linear-gradient(90deg, {accent} 0 {WELL_TOKEN_STRIPE_WIDTH}px, "
            f"{fill} {WELL_TOKEN_STRIPE_WIDTH}px 100%)"
        ),
        "color": "#064e3b",
        "fontSize": "13px",
        "fontWeight": 750,
        "lineHeight": "1",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 10px 22px rgba(15, 118, 110, 0.16)",
        "opacity": 1.0 if active else 0.24,
        "pointerEvents": "none",
        "transition": "opacity 160ms ease, background 160ms ease, border-color 160ms ease",
    }


def duration_badge_style(
    active: bool,
    time_value: str,
) -> dict[str, str | float]:
    return {
        "width": f"{duration_badge_width(time_value)}px",
        "height": "24px",
        "boxSizing": "border-box",
        "padding": "4px 9px",
        "borderRadius": "999px",
        "border": "1px solid #fda4af",
        "backgroundColor": "#fff1f2",
        "color": "#9f1239",
        "fontSize": "11px",
        "fontWeight": 700,
        "lineHeight": "1",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 8px 18px rgba(190, 18, 60, 0.12)",
        "opacity": 1.0 if active else 0.24,
        "pointerEvents": "none",
        "transition": "opacity 160ms ease",
    }


def responsible_badge_style(
    active: bool,
    label: str,
    fill: str,
    border: str,
    text: str,
) -> dict[str, str | float]:
    return {
        "width": f"{responsible_badge_width(label)}px",
        "height": f"{RESPONSIBLE_BADGE_HEIGHT}px",
        "boxSizing": "border-box",
        "padding": "4px 9px",
        "borderRadius": "999px",
        "border": f"1px solid {border}",
        "backgroundColor": fill,
        "color": text,
        "fontSize": "10.5px",
        "fontWeight": 780,
        "lineHeight": "1",
        "textAlign": "center",
        "overflow": "hidden",
        "boxShadow": "0 8px 18px rgba(15, 23, 42, 0.12)",
        "opacity": 1.0 if active else 0.24,
        "pointerEvents": "none",
        "transition": "opacity 160ms ease",
    }


def edge_color(edge: FlowEdge) -> str:
    return {
        "usual": "#111827",
        "yes": "#16834a",
        "no": "#c2410c",
        "dashed": "#64748b",
    }[edge.kind]
