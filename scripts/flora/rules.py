"""Where each family may grow: one rule per family, returning weighted candidates.

A rule returns candidates (x, y, weight, rotation). Rotation None means a
random turn. Every rule leaves out keep-out cells; scatter.py enforces
spacing, tree blockers and hazards.
"""

from __future__ import annotations

import math
import random
from typing import Callable, NamedTuple

import numpy as np

from . import config
from .grid import distance_to, value_noise
from .scene import Scene, Tree
from .terrain import Terrain


class Candidate(NamedTuple):
    x: float
    y: float
    weight: float
    rotation: float | None


class Context(NamedTuple):
    terrain: Terrain
    scene: Scene
    land: np.ndarray  # dry, flat, pathable, not kept out
    wall: np.ndarray  # steep, dry, not kept out
    to_wet: np.ndarray  # distance to water
    to_wall: np.ndarray  # distance to a wall
    to_tree: np.ndarray  # distance to a trunk
    neighbours: dict[str, int]  # trees within CLUSTER_RADIUS, by tree id
    density: np.ndarray  # trees within CLUSTER_RADIUS of each cell
    noise: np.ndarray
    noise_fine: np.ndarray
    to_zerg: np.ndarray  # distance to a Zerg accent structure
    to_lane: np.ndarray  # distance to a lane route cell


def context(terrain: Terrain, scene: Scene, rng: random.Random, lane_points: list[tuple[float, float]] = ()) -> Context:
    n = terrain.height.shape[0]
    dry = ~terrain.wet
    land = dry & terrain.pathable & ~scene.keepout & (terrain.slope < config.FLAT_SLOPE)
    wall = dry & ~scene.keepout & (terrain.slope > config.WALL_SLOPE)
    trunks = np.zeros((n, n), dtype=bool)
    for tree in scene.trees:
        trunks[min(n - 1, int(tree.y)), min(n - 1, int(tree.x))] = True
    zerg = np.zeros((n, n), dtype=bool)
    for unit in scene.units:
        if unit.player == config.ZERG_PLAYER and unit.kind in config.ZERG_ACCENT_UNITS:
            zerg[min(n - 1, int(unit.y)), min(n - 1, int(unit.x))] = True
    neighbours = {
        t.ident: sum(1 for o in scene.trees if o is not t and math.hypot(o.x - t.x, o.y - t.y) <= config.CLUSTER_RADIUS)
        for t in scene.trees
    }
    density = np.zeros((n, n))
    r = int(config.CLUSTER_RADIUS)
    ys, xs = np.mgrid[-r : r + 1, -r : r + 1]
    kernel = (np.hypot(xs, ys) <= config.CLUSTER_RADIUS).astype(float)
    for tree in scene.trees:
        cx, cy = int(tree.x), int(tree.y)
        y0, y1, x0, x1 = max(0, cy - r), min(n, cy + r + 1), max(0, cx - r), min(n, cx + r + 1)
        density[y0:y1, x0:x1] += kernel[y0 - (cy - r) : y1 - (cy - r), x0 - (cx - r) : x1 - (cx - r)]
    on_lane = np.zeros((n, n), dtype=bool)
    for x, y in lane_points:
        on_lane[min(n - 1, int(y)), min(n - 1, int(x))] = True
    to_lane = distance_to(on_lane) if on_lane.any() else np.full((n, n), np.inf)
    return Context(
        terrain, scene, land, wall, distance_to(terrain.wet), distance_to(wall), distance_to(trunks),
        neighbours, density, value_noise((n, n), 24, rng), value_noise((n, n), 9, rng), distance_to(zerg), to_lane,
    )


def cells(mask: np.ndarray, weight: np.ndarray | float, rng: random.Random, rotation: np.ndarray | None = None) -> list[Candidate]:
    ys, xs = np.nonzero(mask)
    w = np.broadcast_to(weight, mask.shape)
    out = []
    for y, x in zip(ys.tolist(), xs.tolist()):
        rot = None if rotation is None else float(rotation[y, x])
        out.append(Candidate(x + rng.random(), y + rng.random(), float(w[y, x]), rot))
    return out


def cliff_vines(c: Context, rng: random.Random) -> list[Candidate]:
    return cells(c.wall, c.terrain.slope, rng, c.terrain.downhill)


def curtain(c: Context, rng: random.Random) -> list[Candidate]:
    return cells(c.wall & (c.terrain.relief > config.RELIEF), c.terrain.relief, rng, c.terrain.downhill)


def large_vines(c: Context, rng: random.Random) -> list[Candidate]:
    out = []
    clustered = [t for t in c.scene.trees if c.neighbours[t.ident] >= config.CLUSTER_MIN]
    for i, a in enumerate(clustered):
        for b in clustered[i + 1 :]:
            d = math.hypot(b.x - a.x, b.y - a.y)
            if a.radius + b.radius + 1.0 < d < 14.0:
                x, y = (a.x + b.x) / 2, (a.y + b.y) / 2
                if _cell(c.land, x, y):
                    out.append(Candidate(x, y, 1.0 / d, math.atan2(b.y - a.y, b.x - a.x)))
    return out


def _cell(mask: np.ndarray, x: float, y: float) -> bool:
    n = mask.shape[0]
    return 0 <= x < n and 0 <= y < n and bool(mask[int(y), int(x)])


def _tree_size(tree: Tree) -> str:
    if tree.scale < config.SMALL_TREE:
        return "ZerusPlantClusterSmall"
    if tree.scale < config.LARGE_TREE:
        return "ZerusPlantClusterMedium"
    return "ZerusPlantClusterLarge"


def tree_base(kind: str) -> Callable[[Context, random.Random], list[Candidate]]:
    def rule(c: Context, rng: random.Random) -> list[Candidate]:
        out = []
        spacing = config.FAMILIES[kind].spacing
        for tree in c.scene.trees:
            if _tree_size(tree) != kind:
                continue
            ring = tree.radius + config.TREE_MARGIN + spacing / 2
            start = rng.random() * 2 * math.pi
            for k in range(8):
                a = start + k * math.pi / 4
                x, y = tree.x + ring * math.cos(a), tree.y + ring * math.sin(a)
                if _cell(c.land, x, y):
                    out.append(Candidate(x, y, 1.0, None))
        return out

    return rule


def ground_vines(c: Context, rng: random.Random) -> list[Candidate]:
    edge = (c.density >= 1) & (c.density <= 3)
    foot = (c.to_wall >= 1) & (c.to_wall <= 4)
    return cells(c.land & (edge | foot) & (c.to_tree > 2), 1.0, rng)


def brambles(c: Context, rng: random.Random) -> list[Candidate]:
    """Forest floor, away from water and lanes (operator, 2026-11-15). Spawns and starts are in the keep-out."""
    forest = (c.density >= config.BRAMBLE_FOREST) & (c.to_tree > 1.5)
    dry = c.to_wet > config.BRAMBLE_WATER_CLEAR
    return cells(c.land & forest & dry & (c.to_lane > config.BRAMBLE_LANE_CLEAR), c.density, rng)


def tall_grass(c: Context, rng: random.Random) -> list[Candidate]:
    """Open ground and the whole river at any depth (operator, 2026-11-15: river FULL of grass).

    Submerged grass is wanted. Lanes stay clear.
    """
    t = c.terrain
    clear = c.to_lane > config.GRASS_LANE_CLEAR
    open_ground = c.land & (c.noise > config.GRASS_LAND_NOISE) & (c.to_tree > 6) & clear
    river = t.wet & ~c.scene.keepout & clear
    weight = np.where(river, config.GRASS_RIVER_WEIGHT, c.noise)
    return cells(open_ground | river, weight, rng)


def swamp(c: Context, rng: random.Random) -> list[Candidate]:
    t = c.terrain
    shore = c.land & (c.to_wet <= config.SHORE_BAND)
    shallow = t.wet & (t.depth < config.SHALLOW) & t.pathable & ~c.scene.keepout
    return cells(shore | shallow, 1.0, rng)


def swamp_large(c: Context, rng: random.Random) -> list[Candidate]:
    t = c.terrain
    shallow = t.wet & (t.depth > 0.1) & (t.depth < config.SHALLOW) & t.pathable & ~c.scene.keepout
    bank = c.land & (c.to_wet <= 1.5)
    return cells(shallow | bank, 1.0, rng)


def water_plant(c: Context, rng: random.Random) -> list[Candidate]:
    t = c.terrain
    wet = t.wet & (t.depth > config.WATER_PLANT_MIN) & ~c.scene.keepout & (c.to_lane > config.GRASS_LANE_CLEAR)
    return cells(wet, 1.0, rng)


def deadly(c: Context, rng: random.Random) -> list[Candidate]:
    return cells(c.land & (c.to_zerg <= config.ZERG_ACCENT_RADIUS), 1.0, rng)


def filler(threshold: float) -> Callable[[Context, random.Random], list[Candidate]]:
    def rule(c: Context, rng: random.Random) -> list[Candidate]:
        return cells(c.land & (c.noise_fine > threshold) & (c.to_wet > 1), 1.0, rng)

    return rule


RULES: dict[str, Callable[[Context, random.Random], list[Candidate]]] = {
    "ZerusCliffVines": cliff_vines,
    "ZerusCurtain": curtain,
    "ZerusLargeVines": large_vines,
    "ZerusPlantClusterLarge": tree_base("ZerusPlantClusterLarge"),
    "ZerusPlantClusterMedium": tree_base("ZerusPlantClusterMedium"),
    "ZerusPlantClusterSmall": tree_base("ZerusPlantClusterSmall"),
    "ZerusWaterPlant": water_plant,
    "ZerusSwampPlantsLarge": swamp_large,
    "ZerusSwampPlants": swamp,
    "ZerusGroundVines": ground_vines,
    "ZerusBrambles": brambles,
    "ZerusTallGrassCluster": tall_grass,
    "ZerusDeadlyPlant": deadly,
    "ZerusPlant": filler(0.55),
    "ZerusPlantlife": filler(0.7),
}
