"""Hall footprints (R-FP-10, R-BASE-30): where the scaled hall model meets the
ground at feet height (its feet). The Shape is the outline on the 0.5 grid,
as for trees (blocker.build_blocker); the Check and Place rows are whole
cells. See docs/specifications/SPEC-SCALED-FOOTPRINTS.md 5."""

from __future__ import annotations

import hashlib
import math
import re
from typing import NamedTuple

import numpy as np

from . import config
from .raster import (
    Polygon,
    close_pinches,
    erode,
    fill_subcells,
    largest_component,
    mesh_samples,
    trace,
)
from .slices import feet_slices, segments_world


class Hall(NamedTuple):
    """cells: whole-cell rows (placement). sub: 0.5 sub-cell rows (the Shape,
    unit pathing). Both top (+y) first, on a square centred on the origin."""

    cells: tuple[str, ...]
    sub: tuple[str, ...]


def actor_scale(actor_text: str, actor: str) -> float:
    """x of the CActorUnit Scale in the map's ActorData; 1 without one."""
    entry = re.compile(r'<CActorUnit\b[^>]*\bid="' + re.escape(actor) + r'"[^>]*>(.*?)</CActorUnit>', re.DOTALL)
    found = entry.findall(actor_text)
    if len(found) > 1:
        raise ValueError(f"ActorData.xml has {len(found)} CActorUnit {actor} entries")
    # `\s*`: the HD pack step writes the catalog again with ElementTree, which spells `" />`.
    scale = re.search(r'<Scale\s+value="([^"]+)"\s*/>', found[0]) if found else None
    if scale is None:
        return 1.0
    parts = [float(v) for v in scale.group(1).split(",")]
    if len(parts) > 1 and abs(parts[0] - parts[1]) > 1e-6:
        raise ValueError(f"{actor} has an uneven xy Scale {scale.group(1)}")
    return parts[0]


def hall_scale(data: dict, actor_text: str, unit: str, model: str) -> float:
    """Drawn xy scale: actor Scale x the model's ModelData ScaleMax (measure)."""
    model_scale = data.get("model_scale", {}).get(model)
    if model_scale is None:
        raise ValueError(f"{model}: no model_scale in the slices; re-run footprints.measure")
    if abs(model_scale[0] - model_scale[1]) > 1e-6:
        raise ValueError(f"{model} has an uneven xy model scale {model_scale}")
    return actor_scale(actor_text, unit) * model_scale[0]


def hall_angle(model: str) -> float:
    """Turn of the drawn model in radians: unit Facing - MODEL_FORWARD."""
    return math.radians(config.HALL_FACING[model] - config.MODEL_FORWARD)


def hall_subcells(data: dict, model: str, scale: float, angle: float | None = None) -> tuple[np.ndarray, float, float]:
    """Blocked 0.5 sub-cells of the eroded feet slices, and the grid origin.

    Each part (a foot bone, measure.MODEL_BONES) is filled apart, clipped
    to its own box: one foot's open contour filled across the middle as
    bars (operator 2026-11-19: "weird flying strip patterns"). angle: the
    model's turn in radians; None: hall_angle(model).
    """
    parts = data["models"][model]
    turn = hall_angle(model) if angle is None else angle
    outlines = [segments_world(parts[name][i], scale, turn) for name in sorted(parts) for i in feet_slices(data, scale)]
    raw, x0, y0, rows, cols = mesh_samples(outlines, clip=True)
    if raw.size == 0:
        raise ValueError(f"{model}: no mesh at feet height at scale {scale}")
    samples = erode(raw, config.ERODE)
    return fill_subcells(samples, rows, cols) >= config.COVERAGE, x0, y0


def hall_cells(data: dict, model: str, scale: float, angle: float | None = None) -> tuple[str, ...]:
    """Engine cell rows, top (+y) first, on an odd square centred on the origin.

    Cell (i, j) covers [i - 0.5, i + 0.5] x [j - 0.5, j + 0.5]; it blocks when
    at least HALL_SUBCELLS of its four 0.5 sub-cells block.
    """
    sub, x0, y0 = hall_subcells(data, model, scale, angle)
    counts: dict[tuple[int, int], int] = {}
    for r, c in zip(*np.nonzero(sub), strict=True):
        i = math.floor(x0 + (c + 0.5) * config.SUB + 0.5)
        j = math.floor(y0 + (r + 0.5) * config.SUB + 0.5)
        counts[(i, j)] = counts.get((i, j), 0) + 1
    cells = {k for k, n in counts.items() if n >= config.HALL_SUBCELLS}
    if not cells:
        raise ValueError(f"{model}: no cell blocks at scale {scale}")
    half = max(max(abs(i), abs(j)) for i, j in cells)
    size = 2 * half + 1
    # Bottom row first, as the raster helpers; a corner pinch gets one cell,
    # so every piece traces to one simple outline.
    mask = np.array([[(i, j) in cells for i in range(-half, half + 1)] for j in range(-half, half + 1)], dtype=bool)
    mask = close_pinches(mask)
    return tuple("".join("x" if mask[r, c] else "." for c in range(size)) for r in range(size - 1, -1, -1))


def hall_sub_rows(data: dict, model: str, scale: float, angle: float | None = None) -> tuple[str, ...]:
    """Blocked 0.5 sub-cell rows, top (+y) first, on an even square centred on
    the origin. Each piece has its holes filled and pinches closed, so it
    traces to one simple outline (as a tree's largest component)."""
    sub, x0, y0 = hall_subcells(data, model, scale, angle)
    at = [(round(x0 / config.SUB) + int(c), round(y0 / config.SUB) + int(r)) for r, c in zip(*np.nonzero(sub), strict=True)]
    if not at:
        raise ValueError(f"{model}: no sub-cell blocks at scale {scale}")
    half = max(max(-x, x + 1, -y, y + 1) for x, y in at)
    mask = np.zeros((2 * half, 2 * half), dtype=bool)
    for x, y in at:
        mask[y + half, x + half] = True
    solid = np.zeros_like(mask)
    for piece in pieces(mask):
        solid |= largest_component(piece)
    return tuple("".join("x" if v else "." for v in row) for row in solid[::-1])


def hall_shape(data: dict, model: str, scale: float, angle: float | None = None) -> Hall:
    return Hall(hall_cells(data, model, scale, angle), hall_sub_rows(data, model, scale, angle))


def pieces(mask: np.ndarray) -> list[np.ndarray]:
    """4-connected components of mask, in scan order."""
    seen = np.zeros_like(mask)
    out = []
    for r, c in zip(*np.nonzero(mask), strict=True):
        if seen[r, c]:
            continue
        piece = np.zeros_like(mask)
        stack = [(r, c)]
        seen[r, c] = True
        while stack:
            y, x = stack.pop()
            piece[y, x] = True
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < mask.shape[0] and 0 <= nx < mask.shape[1] and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    stack.append((ny, nx))
        out.append(piece)
    return out


def hall_polygons(sub: tuple[str, ...]) -> list[Polygon]:
    """One clockwise outline per piece of the sub-cell rows, in world units from the origin.

    The engine blocks unit pathing by the footprint Shape, not by Place cells
    (baseai hall run 20261119-134456: Place cells only, no cell blocked).
    """
    mask = np.array([[ch == "x" for ch in row] for row in reversed(sub)], dtype=bool)
    corner = -len(sub) / 2 * config.SUB
    return [trace(piece, corner, corner) for piece in pieces(mask)]


def hall_footprint_id(hall: Hall) -> str:
    digest = hashlib.sha1(repr(tuple(hall)).encode("ascii")).hexdigest()[:10]
    return f"{config.FOOTPRINT_PREFIX}Hall{digest}"


def hall_footprint_xml(hall: Hall) -> str:
    """Check and Place rows on the odd square (Area like the stock 3x3, so the
    origin is a cell centre) and a Shape with one closed loop per sub-cell piece."""
    cells = hall.cells
    h = len(cells) // 2
    rows = "".join(f'            <Rows value="{row}"/>\n' for row in cells)
    layers = "".join(f'        <Layers index="{name}" Area="{-h},{-h},{h + 1},{h + 1}">\n{rows}        </Layers>\n' for name in ("Check", "Place"))
    points: list[tuple[float, float]] = []
    borders: list[str] = []
    for polygon in hall_polygons(hall.sub):
        start, count = len(points), len(polygon)
        points.extend(polygon)
        borders.extend(f"{start + (k - 1) % count},{start + k},2" for k in range(count))
    radius = max(math.hypot(x, y) for x, y in points)
    shape = (
        "        <Shape>\n"
        f'            <Radius value="{radius:.4f}"/>\n'
        f'            <Offsets value="{";".join(f"{x:g},{y:g}" for x, y in points)}"/>\n'
        f'            <Borders value="{";".join(borders)}"/>\n'
        "        </Shape>\n"
    )
    return f'    <CFootprint id="{hall_footprint_id(hall)}">\n' + layers + shape + "    </CFootprint>\n"


def hall_footprints(data: dict, actor_text: str) -> dict[str, Hall]:
    """Unit -> its rows, at the unit's drawn scale (hall_scale)."""
    if not config.HALL_FOOTPRINTS_ON:
        return {}
    return {unit: hall_shape(data, model, hall_scale(data, actor_text, unit, model))
            for unit, model in sorted(config.HALL_UNITS.items())}


def check_halls(footprints: dict[str, str], units: dict[str, str], data: dict, actor_text: str) -> list[str]:
    """Every hall unit links its measured footprint, with the measured rows."""
    problems = []
    if config.HALL_FOOTPRINTS_ON:
        scales = {unit: actor_scale(actor_text, unit) for unit in sorted(config.HALL_UNITS)}
        if len(set(scales.values())) > 1:
            return [f"town halls are drawn at different actor scales: {scales}"]
    for unit, hall in hall_footprints(data, actor_text).items():
        want = hall_footprint_id(hall)
        fp = re.search(r'<Footprint value="([^"]+)"/>', units.get(unit, ""))
        if fp is None or fp.group(1) != want or want not in footprints:
            problems.append(f"{unit} has no measured hall footprint")
        elif footprints[want].count(f'<Rows value="{hall.cells[0]}"/>') < 2:
            problems.append(f"{unit} hall footprint rows differ from the measured model")
    return problems
