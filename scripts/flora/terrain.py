"""Terrain of a built map as cell grids: ground height, slope, relief, pathing, water.

Ground height per heightmap vertex is (r0 + r1) * quantizeScale + offset
(t3HeightMap HMAP records, t3Terrain.xml vertData). The offset is fitted to
the absolute z of the placed trees, which the editor put on the ground.
Water is every t3Water rectangle cell whose ground is below its water's
height (map WaterData, else 0).
"""

from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import NamedTuple

import numpy as np

from . import config


class Terrain(NamedTuple):
    height: np.ndarray  # cell centre ground z
    slope: np.ndarray  # height change per unit
    downhill: np.ndarray  # angle (radians) of steepest descent
    relief: np.ndarray  # max - min height within RELIEF_RADIUS
    pathable: np.ndarray  # bool, t3CellFlags
    depth: np.ndarray  # water surface - ground; <= 0 dry
    water_level: float
    pool: np.ndarray | None = None  # bool: drawn water of a POOL_WATER rectangle (water features)

    @property
    def wet(self) -> np.ndarray:
        return self.depth > 0


def _vertices(map_dir: Path) -> np.ndarray:
    data = (map_dir / "t3HeightMap").read_bytes()
    magic, _version, sx, sy = struct.unpack_from("<4sIII", data, 0)
    if magic != b"HMAP":
        raise ValueError(f"{map_dir / 't3HeightMap'} is not HMAP")
    records = np.frombuffer(data, dtype="<u2", offset=32, count=sx * sy * 3).reshape(sy, sx, 3)
    return records[..., 0].astype(float) + records[..., 1].astype(float)


def _scale(map_dir: Path) -> float:
    xml = (map_dir / "t3Terrain.xml").read_text(encoding="utf-8")
    match = re.search(r'quantizeScale="([^"]+)"', xml)
    if match is None:
        raise ValueError(f"{map_dir / 't3Terrain.xml'} has no quantizeScale")
    return float(match.group(1))


def _offset(raw: np.ndarray, scale: float, objects: str, sunk: bool = False) -> float:
    """Median of placed-tree z minus raw ground at the tree.

    sunk: the trees were lowered by flora.lift.sink_trees; add the sink back."""
    from .lift import tree_sink

    rests = []
    pattern = r'<ObjectDoodad\b[^>]*\bPosition="([^"]+)"[^>]*\bScale="([^",]+)[^>]*\bType="ZerusTree(?!ScobaBorder)[^"]*"[^>]*>'
    for match in re.finditer(pattern, objects):
        # Border trees (flora/border.py) are placed from this calibration; they never feed it.
        x, y, z = (float(v) for v in match.group(1).split(","))
        if sunk:
            z += tree_sink(float(match.group(2)))
        rests.append(z - bilinear(raw, x, y) * scale)
    if not rests:
        raise ValueError("no placed ZerusTree to calibrate ground height")
    return float(np.median(rests))


def bilinear(grid: np.ndarray, x: float, y: float) -> float:
    h, w = grid.shape
    x = min(max(x, 0.0), w - 1.001)
    y = min(max(y, 0.0), h - 1.001)
    x0, y0 = int(x), int(y)
    fx, fy = x - x0, y - y0
    top = grid[y0, x0] * (1 - fx) + grid[y0, x0 + 1] * fx
    bottom = grid[y0 + 1, x0] * (1 - fx) + grid[y0 + 1, x0 + 1] * fx
    return float(top * (1 - fy) + bottom * fy)


def ground_z(t: "Terrain", x: float, y: float) -> float:
    """Ground height at a world point: bilinear over cell centres."""
    return bilinear(t.height, x - 0.5, y - 0.5)


def water_levels(map_dir: Path) -> dict[str, float]:
    path = map_dir / "Base.SC2Data" / "GameData" / "WaterData.xml"
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    levels = {}
    for match in re.finditer(r'<CWater id="([^"]+)">(.*?)</CWater>', text, re.S):
        # The editor writes the State height as a child element or, since
        # 2026-11-20, as an attribute: <State index="0" Height="7.15" .../>.
        height = re.search(r'<Height value="([^"]+)"/>', match.group(2)) or re.search(r'<State\b[^>]*\bHeight="([^"]+)"', match.group(2))
        if height:
            levels[match.group(1)] = float(height.group(1))
    return levels


def water_rects(map_dir: Path) -> list[tuple[str, tuple[float, float, float, float]]]:
    data = (map_dir / "t3Water").read_bytes()
    magic, _version, amount = struct.unpack_from("<4sII", data, 0)
    if magic != b"WATR" or len(data) != 32 + amount * 56:
        raise ValueError(f"{map_dir / 't3Water'} is not a WATR file of {amount} records")
    rects = []
    for i in range(amount):
        off = 32 + i * 56
        name = data[off : off + 8].split(b"\0", 1)[0].decode("ascii")
        rects.append((name, struct.unpack_from("<4f", data, off + 40)))
    return rects


def load(map_dir: Path) -> Terrain:
    map_dir = Path(map_dir)
    raw = _vertices(map_dir)
    scale = _scale(map_dir)
    # Trees raised by flora.lift (marker present) sit DOODAD_LIFT above the ground they were fitted to.
    lifted = config.DOODAD_LIFT if (map_dir / ".doodads_lifted").exists() else 0.0
    sunk = (map_dir / ".trees_sunk").exists()
    vertices = raw * scale + _offset(raw, scale, (map_dir / "Objects").read_text(encoding="utf-8"), sunk) - lifted
    height = (vertices[:-1, :-1] + vertices[1:, :-1] + vertices[:-1, 1:] + vertices[1:, 1:]) / 4
    n = height.shape[0]
    gy, gx = np.gradient(height)
    slope = np.hypot(gx, gy)
    downhill = np.arctan2(-gy, -gx)
    r = config.RELIEF_RADIUS
    padded_hi = np.pad(height, r, mode="edge")
    hi = np.full_like(height, -np.inf)
    lo = np.full_like(height, np.inf)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            window = padded_hi[r + dy : r + dy + n, r + dx : r + dx + n]
            hi = np.maximum(hi, window)
            lo = np.minimum(lo, window)
    flags = (map_dir / "t3CellFlags").read_bytes()
    pathable = np.frombuffer(flags, dtype=np.uint8, offset=32, count=n * n).reshape(n, n) != 0
    levels = water_levels(map_dir)
    surface = np.full_like(height, -np.inf)
    pool = np.zeros(height.shape, dtype=bool)
    level = 0.0
    for name, (x0, y0, x1, y1) in water_rects(map_dir):
        level = levels.get(name, 0.0)
        sl = (slice(max(0, int(y0)), min(n, int(np.ceil(y1)))), slice(max(0, int(x0)), min(n, int(np.ceil(x1)))))
        surface[sl] = np.maximum(surface[sl], level)
        if name in config.POOL_WATER and name in levels:
            # The water height is in doodad space, GROUND_LIFT over this ground
            # (mapgen/waterfeatures): the drawn water is where the ground is below it.
            pool[sl] |= height[sl] < level - config.GROUND_LIFT
    depth = np.where(np.isfinite(surface), surface - height, -np.inf)
    return Terrain(height, slope, downhill, hi - lo, pathable, depth, level, pool)
