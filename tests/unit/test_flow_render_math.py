from __future__ import annotations

from pydiag.rendering.flow_render_math import ceil_to_step


def test_ceil_to_step_rounds_up_to_requested_grid() -> None:
    assert ceil_to_step(0, 10) == 0
    assert ceil_to_step(21, 10) == 30
    assert ceil_to_step(64, 2) == 64
