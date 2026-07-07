from __future__ import annotations

from math import ceil

__all__ = ["ceil_to_step"]


def ceil_to_step(value: int, step: int) -> int:
    return int(ceil(value / step) * step)
