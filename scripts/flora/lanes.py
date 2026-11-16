"""The map's lanes, and hazards balanced across each lane's sides.

A lane is the least-cost ground route from its Zerg spawn region through its
X region to its Terran spawn region (config.LANE_ROUTES, from the map's lane
triggers). It splits at the X region. Hazards come in pairs: the same kind
at the same arc distance from the split, one on each faction's side, on the
same hand of each faction's direction of travel toward the enemy.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

from . import config
from .grid import disk_cells, distance_to, path_length, shortest_path
from .scene import FINE, Scene
from .terrain import Terrain


class Lane(NamedTuple):
    index: int
    points: list[tuple[float, float]]  # cell centres, Zerg spawn end first
    split: int  # index of the split point
    clearance: np.ndarray  # per point: open distance to the nearest blocked cell

    @property
    def length(self) -> float:
        return path_length(self.points)


class Placed(NamedTuple):
    kind: str
    x: float
    y: float
    rotation: float
    lane: int
    side: str  # faction name
    pair: int
    along: float  # arc distance from the lane's split


def base_cost(terrain: Terrain, scene: Scene) -> np.ndarray:
    n = terrain.height.shape[0]
    trees = scene.tree_block.reshape(n, FINE, n, FINE).any(axis=(1, 3))
    blocked = ~terrain.pathable | trees
    cost = 1.0 + config.SLOPE_COST * np.clip(terrain.slope - config.FLAT_SLOPE, 0.0, None)
    cost = cost + np.where(terrain.wet, config.WATER_COST, 0.0)
    return np.where(blocked, np.inf, cost)


def nearest_open(cost: np.ndarray, x: float, y: float) -> tuple[int, int]:
    h, w = cost.shape
    best, where = math.inf, None
    for r in range(0, 20):
        for yy in range(max(0, int(y) - r), min(h, int(y) + r + 1)):
            for xx in range(max(0, int(x) - r), min(w, int(x) + r + 1)):
                if math.isfinite(cost[yy, xx]):
                    d = math.hypot(xx + 0.5 - x, yy + 0.5 - y)
                    if d < best:
                        best, where = d, (xx, yy)
        if where is not None:
            return where
    raise ValueError(f"no open cell near ({x:.1f}, {y:.1f})")


def route_cells(scene: Scene, cost: np.ndarray, route: config.LaneRoute) -> tuple[list[tuple[int, int]], int]:
    """Cells of one lane route and the index of its X region cell."""
    ends = []
    for name in (route.zerg, route.cross, route.terran):
        region = scene.regions.get(name)
        if region is None:
            raise ValueError(f"lane {route.name}: no region {name!r}")
        ends.append(nearest_open(cost, region.x, region.y))
    first = shortest_path(cost, ends[0], ends[1])
    second = shortest_path(cost, ends[1], ends[2])
    if not first or not second:
        raise ValueError(f"lane {route.name}: {route.zerg} -> {route.cross} -> {route.terran} is not connected")
    return first + second[1:], len(first) - 1


def find_lanes(terrain: Terrain, scene: Scene) -> list[Lane]:
    cost = base_cost(terrain, scene)
    open_dist = distance_to(~np.isfinite(cost))
    lanes = []
    for index, route in enumerate(config.LANE_ROUTES):
        cells, split = route_cells(scene, cost, route)
        points = [(x + 0.5, y + 0.5) for x, y in cells]
        clearance = np.array([open_dist[y, x] for x, y in cells])
        lanes.append(Lane(index, points, split, clearance))
    return lanes


def _at(lane: Lane, distance: float, direction: int) -> tuple[int, float, float, float] | None:
    """Point `distance` along the lane from the split, toward +1 the Terran or -1 the Zerg end."""
    walked = 0.0
    i = lane.split
    last = len(lane.points) - 1
    while 0 <= i + direction <= last:
        j = i + direction
        a, b = lane.points[i], lane.points[j]
        step = math.hypot(b[0] - a[0], b[1] - a[1])
        if walked + step >= distance:
            t = (distance - walked) / step
            x, y = a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])
            # Tangent over a few points for a stable normal, in the +lane direction.
            k0, k1 = max(0, j - 3), min(last, j + 3)
            tx, ty = lane.points[k1][0] - lane.points[k0][0], lane.points[k1][1] - lane.points[k0][1]
            return j, x, y, math.atan2(ty, tx)
        walked += step
        i = j
    return None


_TREE_CACHE: dict[int, tuple[np.ndarray, np.ndarray]] = {}


def _tree_cells(scene: Scene, n: int) -> np.ndarray:
    """Cells holding a tree, computed once per scene (blocker runs thousands
    of times while hazards are relocated)."""
    hit = _TREE_CACHE.get(id(scene.tree_block))
    if hit is None or hit[0] is not scene.tree_block:
        hit = (scene.tree_block, scene.tree_block.reshape(n, FINE, n, FINE).any(axis=(1, 3)))
        _TREE_CACHE.clear()
        _TREE_CACHE[id(scene.tree_block)] = hit
    return hit[1]


def blocker(x: float, y: float, half: float, terrain: Terrain, scene: Scene, kind: str = "") -> str:
    """Why a hazard cannot stand here, or "" when it can."""
    n = terrain.height.shape[0]
    rows, cols = disk_cells(x, y, half + 0.5, (n, n))
    if len(rows) == 0:
        return "off map"
    if (~terrain.pathable[rows, cols]).any():
        return "unpathable"
    if scene.keepout[rows, cols].any():
        return "keep-out"
    if _tree_cells(scene, n)[rows, cols].any():
        return "tree"
    if (terrain.slope[rows, cols] > config.WALL_SLOPE).any():
        return "wall"
    # Operator 2026-11-16: hazards looked bad on slopes; the footprint must be flat.
    heights = terrain.height[rows, cols]
    if heights.max() - heights.min() > config.HAZARD_FLAT_RANGE:
        return "slope"
    clear = config.HAZARD_WATER_CLEAR.get(kind, 0.0)
    if clear > 0.0:
        wr, wc = disk_cells(x, y, half + clear, (n, n))
        if terrain.wet[wr, wc].any():
            return "near water"
    return ""


def wiggle(x: float, y: float, half: float, terrain: Terrain, scene: Scene, kind: str) -> tuple[float, float, str]:
    """The proposed spot, or the nearest free one on rings around it.

    Returns (x, y, "") for a free spot, else the proposed spot and the
    reason it is blocked. Only the position moves; the pair keeps its arc
    distance, so the factions stay balanced.
    """
    first = blocker(x, y, half, terrain, scene, kind)
    if not first:
        return x, y, ""
    for radius in config.HAZARD_WIGGLE_RINGS:
        for k in range(config.HAZARD_WIGGLE_STEPS):
            a = 2 * math.pi * k / config.HAZARD_WIGGLE_STEPS
            wx, wy = x + radius * math.cos(a), y + radius * math.sin(a)
            if not blocker(wx, wy, half, terrain, scene, kind):
                return wx, wy, ""
    return x, y, first


def _spots(lane: Lane, hazard: config.Hazard, distance: float, side_scale: float) -> list[tuple[str, float, float, float]]:
    zerg, terran = config.FACTION_SIDES
    half = config.HAZARD_HALF[hazard.kind]
    spots = []
    for direction, side in ((-1, zerg), (1, terran)):
        at = _at(lane, distance, direction)
        if at is None:
            return []
        j, x, y, angle = at
        # Travel direction toward the enemy: Zerg walks +lane, Terran walks -lane.
        travel = angle if side == zerg else angle + math.pi
        side_off = side_scale * min(config.HAZARD_SIDE_MAX, config.HAZARD_SIDE * max(0.0, lane.clearance[j] - half - 1.0))
        left = travel + math.pi / 2
        spots.append((side, x + hazard.hand * side_off * math.cos(left), y + hazard.hand * side_off * math.sin(left), travel))
    return spots


def _apart(spots: list[tuple[str, float, float, float]], half: float, placed: list[Placed]) -> bool:
    """No overlap with the hazards placed so far (1 cell gap)."""
    return all(math.hypot(x - h.x, y - h.y) > half + config.HAZARD_HALF[h.kind] + 1.0 for _, x, y, _ in spots for h in placed)


def place_hazards(lanes: list[Lane], terrain: Terrain, scene: Scene) -> tuple[list[Placed], list[str]]:
    """Hazard pairs, round-robin over the lanes up to HAZARD_TOTAL; a blocked
    pair is relocated along the lane (HAZARD_SHIFTS) and around each spot
    (wiggle). Notes say which pairs found no spot at all."""
    placed: list[Placed] = []
    notes = []
    for pair, hazard in enumerate(config.HAZARDS):
        for lane in lanes:
            if len(placed) + 2 > config.HAZARD_TOTAL:
                return placed, notes
            half = config.HAZARD_HALF[hazard.kind]
            chosen, why, along = [], "", 0.0
            # Both sides get the same shift, so the pair stays balanced.
            for shift in config.HAZARD_SHIFTS:
                if hazard.distance + shift < config.HAZARD_MIN_ALONG:
                    continue
                for side_scale in (1.0, 0.5, 0.0):
                    spots = _spots(lane, hazard, hazard.distance + shift, side_scale)
                    if not spots:
                        why = "lane too short"
                        continue
                    found = [wiggle(x, y, half, terrain, scene, hazard.kind) for _, x, y, _ in spots]
                    reasons = [r for _, _, r in found]
                    spots = [(s[0], fx, fy, s[3]) for s, (fx, fy, _) in zip(spots, found)]
                    if not any(reasons) and not _apart(spots, half, placed):
                        reasons = ["next to another hazard"] * len(spots)
                    if not any(reasons):
                        chosen, along = spots, hazard.distance + shift
                        break
                    why = ", ".join(f"{s[0]} {r}" for s, r in zip(spots, reasons) if r)
                if chosen:
                    break
            if not chosen:
                notes.append(f"lane {lane.index} pair {pair} {hazard.kind}: dropped ({why})")
                continue
            for side, x, y, travel in chosen:
                placed.append(Placed(hazard.kind, round(x, 3), round(y, 3), round(travel % (2 * math.pi), 4), lane.index, side, pair, along))
    return placed, notes


def settle(lanes: list[Lane], placed: list[Placed], terrain: Terrain, scene: Scene) -> tuple[list[Placed], list[float], list[str]]:
    """Drop a lane's outermost pair (both sides) until its route stays within LANE_DETOUR_MAX."""
    notes = []
    detour = detours(lanes, placed, terrain, scene)
    while any(not d <= config.LANE_DETOUR_MAX for d in detour):
        lane = next(i for i, d in enumerate(detour) if not d <= config.LANE_DETOUR_MAX)
        pairs = sorted({h.pair for h in placed if h.lane == lane})
        if not pairs:
            raise ValueError(f"lane {lane}: detour {detour[lane]:.2f} without hazards")
        placed = [h for h in placed if not (h.lane == lane and h.pair == pairs[-1])]
        notes.append(f"lane {lane} pair {pairs[-1]}: dropped, detour {detour[lane]:.2f} > {config.LANE_DETOUR_MAX}")
        detour = detours(lanes, placed, terrain, scene)
    return placed, detour, notes


def hazard_cells(placed: list[Placed], n: int) -> np.ndarray:
    blocked = np.zeros((n, n), dtype=bool)
    for h in placed:
        rows, cols = disk_cells(h.x, h.y, config.HAZARD_HALF[h.kind] + 0.5, (n, n))
        blocked[rows, cols] = True
    return blocked


def detours(lanes: list[Lane], placed: list[Placed], terrain: Terrain, scene: Scene) -> list[float]:
    """Per lane: route length inside its corridor with hazards blocking, over the same without."""
    base = base_cost(terrain, scene)
    hazards = hazard_cells(placed, base.shape[0])
    out = []
    for lane in lanes:
        on_lane = np.zeros(base.shape, dtype=bool)
        for x, y in lane.points:
            on_lane[int(y), int(x)] = True
        corridor = distance_to(on_lane) <= config.LANE_CORRIDOR
        cost = np.where(corridor, base, np.inf)
        with_hazards = np.where(hazards, np.inf, cost)
        start = (int(lane.points[0][0]), int(lane.points[0][1]))
        goal = (int(lane.points[-1][0]), int(lane.points[-1][1]))
        plain = shortest_path(cost, start, goal)
        route = shortest_path(with_hazards, start, goal)
        if not route:
            out.append(math.inf)
            continue
        out.append(path_length([(x, y) for x, y in route]) / path_length([(x, y) for x, y in plain]))
    return out
