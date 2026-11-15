"""Measured mesh slices (from footprints.measure), scale and engine rotation.

fprot probe runs found: the engine turns a doodad Shape by its placed
Rotation snapped to the nearest 90 degrees, ties down (45 -> 0, 135 -> 90),
and does not scale it (runs 20261115-132159, 20261115-132312).
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from . import config


def load_slices(path: Path | None = None) -> dict:
    return json.loads((path or config.SLICES).read_text(encoding="utf-8"))


def engine_quarter_turns(rotation: float) -> int:
    """Quarter turns the engine applies for a placed rotation in radians (nearest, ties down)."""
    return math.ceil(math.degrees(rotation) / 90.0 - 0.5 - 1e-9) % 4


def residual_rotation(rotation: float) -> float:
    """Rotation in radians the engine leaves out; baked into the Shape."""
    rest = rotation - engine_quarter_turns(rotation) * math.pi / 2
    return math.atan2(math.sin(rest), math.cos(rest))


def feet_slices(data: dict, scale: float) -> list[int]:
    """Indices of the model slices at feet height for this scale."""
    step = data["slice_step"]
    count = data["slice_count"]
    picks = []
    for k in range(config.FEET_SAMPLES):
        world = config.FEET_LOW + (config.FEET_HIGH - config.FEET_LOW) * k / max(1, config.FEET_SAMPLES - 1)
        index = min(count - 1, max(0, round(world / scale / step) - 1))
        if index not in picks:
            picks.append(index)
    return picks


def segments_world(segments: list[list[float]], scale: float, angle: float) -> np.ndarray:
    """Model-space segments (M, 4) to local world space: scaled, then turned by angle."""
    if not segments:
        return np.zeros((0, 4))
    s = np.asarray(segments, dtype=float) * scale
    c, n = math.cos(angle), math.sin(angle)
    out = np.empty_like(s)
    out[:, 0] = s[:, 0] * c - s[:, 1] * n
    out[:, 1] = s[:, 0] * n + s[:, 1] * c
    out[:, 2] = s[:, 2] * c - s[:, 3] * n
    out[:, 3] = s[:, 2] * n + s[:, 3] * c
    return out
