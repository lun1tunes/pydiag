from __future__ import annotations

from urllib.parse import quote

SHAPE_OUTLINE_STROKE_WIDTH = 1.6
SHAPE_DETAIL_STROKE_WIDTH = 0.85

__all__ = [
    "SHAPE_DETAIL_STROKE_WIDTH",
    "SHAPE_OUTLINE_STROKE_WIDTH",
    "cylinder_background",
    "database_background",
    "decision_diamond_background",
    "input_data_background",
    "polygon_background",
]


def decision_diamond_background(fill: str) -> str:
    return polygon_background(
        points="50,2 98,50 50,98 2,50",
        fill=fill,
        stroke="#000000",
    )


def input_data_background() -> str:
    return polygon_background(
        points="13,2 98,2 87,98 2,98",
        fill="#f1f7ff",
        stroke="#5477aa",
    )


def database_background() -> str:
    return cylinder_background()


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
