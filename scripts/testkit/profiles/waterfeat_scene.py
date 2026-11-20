"""waterfeat profile: the scene read from the built map, its sample points and orbits.

Used by profiles/waterfeat.py, which holds the map spec, the host hook and the checks.
"""

from __future__ import annotations
import math
import re
import struct
import time
from pathlib import Path
from typing import NamedTuple
import numpy as np
from flora import config as flora_config
from flora import terrain as terrain_mod
from flora.terrain import bilinear
from mapgen.rimfalls import config as rim_config
from mapgen.waterfeatures import build as feature_build
from mapgen.waterfeatures import carve, config, ground as ground_mod, models as models_mod, sites as site_finder
from mapgen.waterfeatures.sites import Site
from project_root import project_root
from terrain import sync_height

ROOT = project_root()
BUILT = ROOT / "out" / "SCOBA256.SC2Map"
SRC = ROOT / "src" / "SCOBA.SC2Map"
WORK = ROOT / "out" / "testkit" / "waterfeat"
POINTS_GALAXY = WORK / "waterfeat_points.galaxy"
SAMPLES = 24  # per class and site
CELLS = 80
FAR = 8
MOVED = 0.25  # a vertex the step moved at least this far
VERTEX_TOL = 0.05  # engine against built ground on a vertex (ground run 20261119-153624: 0.002)
SPOT_TOL = 0.25  # the same under a unit, off the vertices
START_GAP = (3.0, 14.0)  # the walk starts this far from the pool
TREE_REACH = 0.6  # x scale, plus 1: a tree's trunk and roots
UNIT_REACH = 4.0
AUTHORED_FACING = 270.0
# Orbit views (operator 2026-11-20): 15 s per site, 5 screenshots 3 s apart.
ORBIT_SECONDS = 15.0  # real time
ORBIT_TURN = 180.0  # degrees over the orbit: slow, 12 degrees per second
ORBIT_DIST = 28.0
ORBIT_PITCH = 35.0
ORBIT_HEIGHT = 2.0  # camera target above the ground
SHOTS = 5
SHOT_GAP_S = 3.0
HOST_DEADLINE_S = 100.0
Point = tuple[float, float]


class Scene(NamedTuple):
    vz: np.ndarray  # built ground per vertex, [y, x]
    before: np.ndarray  # the ground before the water feature step
    painted: np.ndarray  # cells [y, x] painted no pathing by the build
    open: np.ndarray  # cells [y, x] the host takes as walkable dry ground
    levels: dict[str, float]  # water level per type, ground space
    sites: list[Site]
    pipes: list[tuple[str, float, float]]  # placed pipe units
    prior: np.ndarray | None = None  # pathing paint [y, x] of the map before the build steps; 0 = none
    things: tuple[tuple[float, float, float], ...] = ()  # (x, y, reach) of trees and units


class Samples(NamedTuple):
    pool: list[Point]  # wet vertices
    dry: list[Point]  # moved vertices over the water, at the pool
    far: list[Point]  # vertices beside the site the step left alone
    cells: list[Point]  # centres of painted pool cells
    stand: Point
    start: Point  # the walk: from open ground
    end: Point  # to the middle of the pool


def _raw(path: Path) -> np.ndarray:
    data = path.read_bytes()
    magic, _version, sx, sy = struct.unpack_from("<4sIII", data, 0)
    if magic != b"HMAP":
        raise ValueError(f"{path} is not an HMAP")
    return np.frombuffer(data, dtype="<u2", offset=32, count=sx * sy * 3).reshape(sy, sx, 3)[..., 0].astype(float)


def _paint(path: Path) -> np.ndarray:
    data = path.read_bytes()
    n = math.isqrt(len(data) - 4)
    if n * n != len(data) - 4:
        raise ValueError(f"{path} is not one byte per cell")
    return np.frombuffer(data, dtype=np.uint8, offset=4).reshape(n, n)


def _things(objects: str) -> list[tuple[float, float, float]]:
    """(x, y, reach) of what stands on the ground: trees, units."""
    out = []
    for match in re.finditer(r"<Object(Doodad|Unit)\b[^>]*>", objects):
        head = match.group(0)
        x, y, _z = (float(v) for v in re.search(r'\bPosition="([^"]*)"', head).group(1).split(","))
        if match.group(1) == "Unit":
            out.append((x, y, UNIT_REACH))
            continue
        kind = re.search(r'\bType="([^"]*)"', head)
        if kind and kind.group(1).startswith("ZerusTree"):
            scale = re.search(r'\bScale="([^",]+)', head)
            out.append((x, y, 1.0 + TREE_REACH * float(scale.group(1) if scale else 1.0)))
    return out


def scene(built: Path = BUILT, src: Path = SRC, work: Path = WORK) -> Scene:
    import expand_map

    work.mkdir(parents=True, exist_ok=True)
    # The ground and the pathing paint as the expand step made them, before the water features.
    expand_map.expand_heightmap(src / "t3HeightMap", work / "before_t3HeightMap")
    expand_map.expand_cell_attributes(src / "CellAttribute_Pnp", work / "before_CellAttribute_Pnp")
    vz = sync_height.vertex_z(built)
    before = vz - (_raw(built / "t3HeightMap") - _raw(work / "before_t3HeightMap")) * terrain_mod._scale(built)
    paint = _paint(built / "CellAttribute_Pnp")
    prior = _paint(work / "before_CellAttribute_Pnp")
    painted = (paint == ground_mod.NO_PATH) & (prior != ground_mod.NO_PATH)
    objects = (built / "Objects").read_text(encoding="utf-8")
    models = models_mod.load()
    mouths = site_finder.pipe_mouths(objects, models, lambda x, y: bilinear(vz, x, y), feature_build.pending_unit_scale(built))
    sites = site_finder.find(terrain_mod.water_rects(built), mouths)
    if not sites:
        raise ValueError("waterfeat: the built map has no water feature site")
    levels = {name: height - flora_config.GROUND_LIFT for name, height in terrain_mod.water_levels(built).items()}
    t = terrain_mod.load(built)
    n = t.height.shape[0]
    corners = np.stack([vz[:-1, :-1], vz[1:, :-1], vz[:-1, 1:], vz[1:, 1:]])
    wet = t.depth - flora_config.GROUND_LIFT > 0
    is_open = t.pathable & (paint != ground_mod.NO_PATH) & ~wet & (np.ptp(corners, axis=0) < 1.0)
    ys, xs = np.mgrid[0:n, 0:n]
    things = tuple(_things(objects))
    for x, y, reach in things:
        is_open &= np.hypot(xs + 0.5 - x, ys + 0.5 - y) > reach
    pipes = []
    for match in re.finditer(r"<ObjectUnit\b[^>]*>", objects):
        kind = re.search(r'\bUnitType="([^"]*)"', match.group(0))
        if kind and kind.group(1) in config.PIPE_UNITS:
            x, y, _z = (float(v) for v in re.search(r'\bPosition="([^"]*)"', match.group(0)).group(1).split(","))
            pipes.append((kind.group(1), x, y))
    return Scene(vz, before, painted, is_open, levels, sites, pipes, prior, things)


def thin(points: list[Point], amount: int) -> list[Point]:
    """At most `amount` of the points, evenly over the list."""
    if len(points) <= amount:
        return points
    return [points[int(k * len(points) / amount)] for k in range(amount)]


def _vertices(mask: np.ndarray) -> list[Point]:
    ys, xs = np.nonzero(mask)
    return [(float(x), float(y)) for y, x in zip(ys, xs)]


def samples(sc: Scene, index: int) -> Samples:
    site = sc.sites[index]
    level = sc.levels[site.water]
    delta = sc.vz - sc.before
    moved = np.abs(delta) >= MOVED
    rect = carve.inside(sc.vz.shape, site.rect, -1.0)  # strictly inside: where the pool is
    pool = rect & (sc.vz < level - 0.05)
    # Dry is what the plan calls dry: not below the level. A vertex 0.01 under
    # water is a shallow pool edge, not shore (run 20261120-125100 had two).
    shore = carve.inside(sc.vz.shape, site.rect, config.SHORE_MARGIN) & ~(rect & (sc.vz < level))
    reach = config.SHORE_MARGIN + config.BLEND_PASSES + 2
    ring = carve.inside(sc.vz.shape, site.rect, reach + 4) & ~carve.inside(sc.vz.shape, site.rect, reach)
    if not pool.any() or not (shore & moved).any():
        raise ValueError(f"waterfeat: site {index} has no pool or no moved shore")
    n = sc.painted.shape[0]
    deep = pool & (sc.vz < level - config.NO_PATH_DEPTH)
    cells = sc.painted & deep[:-1, :-1] & deep[1:, :-1] & deep[:-1, 1:] & deep[1:, 1:]
    cys, cxs = np.nonzero(cells)
    pys, pxs = np.nonzero(pool)
    middle = (float(pxs.mean()), float(pys.mean()))
    # The Marine stands on the vertex the step moved most.
    my, mx = np.unravel_index(np.argmax(np.where(shore | pool, np.abs(delta), 0.0)), delta.shape)
    # The walk starts on open ground near the pool, with open ground toward it.
    best = None
    for y in range(n):
        for x in range(n):
            if not sc.open[y, x]:
                continue
            p = (x + 0.5, y + 0.5)
            gap = float(np.hypot(pxs - p[0], pys - p[1]).min())
            if not START_GAP[0] <= gap <= START_GAP[1]:
                continue
            away = math.dist(p, middle)
            step = ((middle[0] - p[0]) / away, (middle[1] - p[1]) / away)
            ahead = [(int(p[0] + step[0] * k), int(p[1] + step[1] * k)) for k in (1, 2)]
            if all(0 <= ax < n and 0 <= ay < n and sc.open[ay, ax] for ax, ay in ahead) and (best is None or away < best[0]):
                best = (away, p)
    if best is None:
        raise ValueError(f"waterfeat: no open ground {START_GAP[0]}..{START_GAP[1]} from the pool of site {index}")
    return Samples(
        thin(_vertices(pool), SAMPLES),
        thin(_vertices(shore & moved), SAMPLES),
        thin(_vertices(ring & (delta == 0.0)), FAR),
        thin([(x + 0.5, y + 0.5) for y, x in zip(cys, cxs)], CELLS),
        (float(mx), float(my)),
        best[1],
        middle,
    )


def orbit(sc: Scene, index: int) -> tuple[Point, float]:
    """(target, first yaw) of a site's orbit. The camera yaw is the way it looks.

    The middle screenshot looks against the flow: at the pipe mouths, from
    the pool side. The others are spread evenly to both flanks."""
    site = sc.sites[index]
    flow = (sum(m.dx for m in site.mouths), sum(m.dy for m in site.mouths))
    look = math.degrees(math.atan2(-flow[1], -flow[0]))
    rate = ORBIT_TURN / ORBIT_SECONDS
    return samples(sc, index).end, (look - rate * (SHOTS - 1) * SHOT_GAP_S / 2) % 360.0


class Rim(NamedTuple):
    """One rim fall group of the built map (REQ-RIM-FALLS)."""

    basin: Point  # the vertex nearest the basin centre
    rocks: list[Point]


def rim_groups(built: Path = BUILT) -> list[Rim]:
    """The groups the build reports in its marker: what it wrote."""
    marker = built / rim_config.MARKER
    if not marker.is_file():
        return []
    out: list[Rim] = []
    for line in marker.read_text(encoding="utf-8").splitlines():
        basin = re.match(r"group \d+: .* basin ([-\d.]+),([-\d.]+) ", line)
        rock = re.match(rf"  rock {rim_config.ROCK} v\d+: at ([-\d.]+),([-\d.]+),", line)
        if basin:
            out.append(Rim((float(round(float(basin.group(1)))), float(round(float(basin.group(2))))), []))
        elif rock and out:
            out[-1].rocks.append((float(rock.group(1)), float(rock.group(2))))
    return out
