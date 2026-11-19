"""A blocker from mesh outlines: its Shape polygon, its cells, and how it fits the mesh."""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

from . import config
from .catalog import footprint_id
from .raster import Polygon, close_pinches, erode, fill_subcells, largest_component, mesh_samples, trace


class Fit(NamedTuple):
    """How a generated blocker fits the (eroded) mesh, in world units."""

    mesh_area: float
    blocked_area: float
    covered_area: float
    offset: float

    @property
    def covered(self) -> float:
        return self.covered_area / self.mesh_area if self.mesh_area else 1.0

    @property
    def ratio(self) -> float:
        return self.blocked_area / self.mesh_area if self.mesh_area else math.inf


class Blocker(NamedTuple):
    section: str
    polygon: Polygon
    fit: Fit
    # Place cell rows centred on the origin; empty for doodads (they ignore cells).
    cells: tuple[str, ...] = ()

    @property
    def footprint(self) -> str:
        return footprint_id(self.polygon, self.cells)


def _centre(raw: np.ndarray, outlines: list[np.ndarray], x0: float, y0: float) -> tuple[float, float]:
    if raw.any():
        fine = config.SUB / config.SAMPLES_PER_SUB
        ys, xs = np.nonzero(raw)
        return x0 + (xs.mean() + 0.5) * fine, y0 + (ys.mean() + 0.5) * fine
    every = np.concatenate([o for o in outlines if len(o)])
    return float(np.concatenate([every[:, 0], every[:, 2]]).mean()), float(np.concatenate([every[:, 1], every[:, 3]]).mean())


def build_blocker(section: str, outlines: list[np.ndarray]) -> Blocker:
    """Shape of the eroded mesh on the 0.5 grid; a trunk thinner than 2 * ERODE gets one cell."""
    raw, x0, y0, rows, cols = mesh_samples(outlines)
    if raw.size == 0:
        raise ValueError(f"{section}: no mesh at feet height")
    samples = erode(raw, config.ERODE)
    region = largest_component(fill_subcells(samples, rows, cols) >= config.COVERAGE)
    if not region.any():
        cx, cy = _centre(raw, outlines, x0, y0)
        c = int(round((cx - x0) / config.SUB))
        r = int(round((cy - y0) / config.SUB))
        region = np.zeros_like(region)
        region[max(0, r - 1) : r + 1, max(0, c - 1) : c + 1] = True
    per = config.SAMPLES_PER_SUB
    fine_area = (config.SUB / per) ** 2
    blocked = np.repeat(np.repeat(region, per, axis=0), per, axis=1)
    offset = 0.0
    if samples.any():
        ys, xs = np.nonzero(samples)
        bys, bxs = np.nonzero(blocked)
        offset = math.hypot(xs.mean() - bxs.mean(), ys.mean() - bys.mean()) * config.SUB / per
    fit = Fit(
        mesh_area=float(samples.sum()) * fine_area,
        blocked_area=float(region.sum()) * config.SUB * config.SUB,
        covered_area=float((samples & blocked).sum()) * fine_area,
        offset=offset,
    )
    return Blocker(section, trace(region, x0, y0), fit)


def disk_cells(radius: float) -> tuple[str, ...]:
    """Whole cells inside the disk, as footprint rows centred on the origin.

    Units also block their Place cells; the Shape alone left disk edge points
    open for a spore (treepath run 20261115-133213). The rows are symmetric,
    so their order does not matter.
    """
    half = max(1, int(math.floor(radius / math.sqrt(2))) + 1)
    rows = []
    for j in range(half - 1, -half - 1, -1):
        row = ""
        for i in range(-half, half):
            corners = [(i, j), (i + 1, j), (i, j + 1), (i + 1, j + 1)]
            row += "x" if all(math.hypot(x, y) <= radius for x, y in corners) else "."
        rows.append(row)
    return tuple(rows)


def disk_blocker(section: str, outlines: list[np.ndarray]) -> Blocker:
    """Round blocker at the origin with the area of the mesh's solid core.

    Spore models are skinned units with open geometry; their slice fill is
    noisy away from the core, so the core's area sizes a disk instead.
    """
    core = build_blocker(section, outlines)
    radius = math.sqrt(core.fit.blocked_area / math.pi)
    sub = config.SUB
    half = int(math.ceil(radius / sub)) + 1
    size = 2 * half
    mask = np.zeros((size, size), dtype=bool)
    for r in range(size):
        for c in range(size):
            mask[r, c] = math.hypot((c - half + 0.5) * sub, (r - half + 0.5) * sub) <= radius
    mask[half - 1 : half + 1, half - 1 : half + 1] = True
    polygon = trace(close_pinches(mask), -half * sub, -half * sub)
    fit = Fit(core.fit.mesh_area, float(mask.sum()) * sub * sub, core.fit.covered_area, 0.0)
    return Blocker(section, polygon, fit, disk_cells(radius))


def fit_problems(blocker: Blocker) -> list[str]:
    fit = blocker.fit
    problems = []
    if fit.covered < config.MIN_MESH_COVERED and fit.mesh_area > config.MIN_CHECKED_MESH:
        problems.append(f"{blocker.section} blocker covers {fit.covered:.0%} of the mesh, want >= {config.MIN_MESH_COVERED:.0%}")
    if fit.blocked_area > config.MAX_BLOCKED_RATIO * fit.mesh_area + 1.0:
        problems.append(
            f"{blocker.section} blocks {fit.blocked_area:.2f}, mesh {fit.mesh_area:.2f}: over {config.MAX_BLOCKED_RATIO}x + 1 cell"
        )
    return problems
