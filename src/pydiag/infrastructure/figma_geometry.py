from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from pydiag.infrastructure.figma_schema import FigmaConnectorNode


@dataclass(frozen=True)
class Rect:
    left: float
    top: float
    right: float
    bottom: float


def infer_connector_terminal(
    connector: FigmaConnectorNode,
    node_rects: dict[str, Rect],
    *,
    end: Literal["start", "end"],
) -> str | None:
    point = connector_endpoints(connector)[0 if end == "start" else 1]
    ranked = sorted(
        ((distance_to_rect(point, rect), node_id) for node_id, rect in node_rects.items()),
        key=lambda item: item[0],
    )
    return ranked[0][1] if ranked else None


def secondary_nearest_terminal(
    connector: FigmaConnectorNode,
    node_rects: dict[str, Rect],
    *,
    excluded: str,
) -> str | None:
    point = connector_endpoints(connector)[1]
    ranked = sorted(
        (
            (distance_to_rect(point, rect), node_id)
            for node_id, rect in node_rects.items()
            if node_id != excluded
        ),
        key=lambda item: item[0],
    )
    return ranked[0][1] if ranked else None


def connector_endpoints(
    connector: FigmaConnectorNode,
) -> tuple[tuple[float, float], tuple[float, float]]:
    center_x = float(connector.x) + float(connector.width) / 2
    center_y = float(connector.y) + float(connector.height) / 2
    half_width = float(connector.width) / 2
    half_height = float(connector.height) / 2
    if abs(half_width) >= abs(half_height):
        start = (-half_width, 0.0)
        end = (half_width, 0.0)
    else:
        start = (0.0, -half_height)
        end = (0.0, half_height)

    angle = math.radians(float(connector.rotation))
    sin_angle = math.sin(angle)
    cos_angle = math.cos(angle)
    return (
        (
            round(center_x + start[0] * cos_angle - start[1] * sin_angle, 2),
            round(center_y + start[0] * sin_angle + start[1] * cos_angle, 2),
        ),
        (
            round(center_x + end[0] * cos_angle - end[1] * sin_angle, 2),
            round(center_y + end[0] * sin_angle + end[1] * cos_angle, 2),
        ),
    )


def distance_to_rect(point: tuple[float, float], rect: Rect) -> float:
    dx = max(rect.left - point[0], 0.0, point[0] - rect.right)
    dy = max(rect.top - point[1], 0.0, point[1] - rect.bottom)
    return math.hypot(dx, dy)
