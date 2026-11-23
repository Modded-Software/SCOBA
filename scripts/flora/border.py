"""Tree and bramble border on the outer rim (operator 2026-11-16).

The ring outside the playable bounds (MapInfo: x 2..254, y 3..254 of 256)
gets two sparse rows of the trees already in the map and brambles
throughout. Rows run BORDER_IN cells inside and BORDER_OUT cells outside the
map edge (beyond it if the engine draws doodads there). Heights follow the
terrain bowl: the lowest ground under the plant (clamped at the map edge).
Each placed scale is multiplied by BORDER_SCALE at the end.
"""

from __future__ import annotations

import math
import random
import re

from . import config
from . import terrain as terrain_mod

MAP = float(config.MAP_CELLS)
ROWS = (1.0, -1.0)  # tree rows: cells inside (+) / outside (-) the map edge
TREE_STEP = 9.0  # sparse: mean tree spacing along a row (operator: less dense, was 5)
BRAMBLE_STEP = 8.0  # operator: way less dense (was 2.5)
# No border plant near these placed units (operator 2026-11-16): the
# Overmind (was the Hive, same extent) and the 2x scaled Psi Decimator on the
# two opposite corners. Radius in cells.
KEEPOUT_UNITS = {"SCOBAOvermind": 14.0, "PsiDecimator": 18.0}


def keepouts(objects: str) -> list[tuple[float, float, float]]:
    out = []
    for m in re.finditer(r'<ObjectUnit\b[^>]*\bPosition="([^",]+),([^",]+)[^"]*"[^>]*\bUnitType="([^"]+)"', objects):
        if m.group(3) in KEEPOUT_UNITS:
            out.append((float(m.group(1)), float(m.group(2)), KEEPOUT_UNITS[m.group(3)]))
    if len(out) < len(KEEPOUT_UNITS):
        raise ValueError(f"border: keep-out units missing, found {out}")
    return out


def clear(x: float, y: float, zones: list[tuple[float, float, float]]) -> bool:
    return all(math.hypot(x - zx, y - zy) > r for zx, zy, r in zones)
BRAMBLE_BAND = (-2.0, 2.0)  # brambles across the whole strip
JITTER = 0.4  # fraction of the step
BORDER_SCALE = 1.5
BRAMBLE = "ZerusBrambles"
BORDER_TREE = "ZerusTreeScobaBorder"  # ZerusTree model, no footprint (actor_xml)


def actor_xml(none_footprint: str) -> str:
    return (
        f'    <CActorDoodad id="{BORDER_TREE}" parent="ZerusTree">\n'
        '        <Model value="ZerusTree"/>\n'
        f'        <Footprint value="{none_footprint}"/>\n'
        "    </CActorDoodad>\n"
    )
GROUND_REACH = 1.5  # lowest ground within this radius: no floating edge on the rim slope


def tree_pool(objects: str) -> list[tuple[str, int, float]]:
    """(type, variation, scale) of every placed tree: the border reuses them."""
    pool = []
    for m in re.finditer(r'<ObjectDoodad\b[^>]*>', objects):
        tag = m.group(0)
        kind = re.search(r'\bType="(ZerusTree[^"]*)"', tag)
        if kind is None or kind.group(1) == BORDER_TREE:
            continue
        var = re.search(r'\bVariation="(\d+)"', tag)
        scale = re.search(r'\bScale="([^",]+)', tag)
        # The ZerusTreeFp* actors carry footprints fitted to their placed
        # scale; border trees are rescaled and sit off the playable area,
        # so they use the stock ZerusTree (same model and variations).
        pool.append((BORDER_TREE, int(var.group(1)) if var else 0, float(scale.group(1)) if scale else 1.0))
    if not pool:
        raise ValueError("border: no placed tree to copy")
    return pool


def perimeter(band: tuple[float, float], step: float, rng: random.Random) -> list[tuple[float, float]]:
    """Points along all four edges, each a random inset within `band`
    (cells inside the edge; negative is outside the map)."""
    n = max(1, int(MAP / step))
    pts = []
    for edge in range(4):
        for i in range(n):
            t = (i + 0.5 + rng.uniform(-JITTER, JITTER)) * MAP / n
            d = rng.uniform(*band)
            pts.append(((t, d), (MAP - d, t), (t, MAP - d), (d, t))[edge])
    return pts


def ground(t, x: float, y: float) -> float:
    zs = [terrain_mod.ground_z(t, x, y)]
    for k in range(8):
        a = k * math.pi / 4
        zs.append(terrain_mod.ground_z(t, x + GROUND_REACH * math.cos(a), y + GROUND_REACH * math.sin(a)))
    return min(zs)


def plan(t, objects: str) -> list[tuple[str, int, float, float, float, float, float]]:
    """(type, variation, x, y, z, rotation, scale) of the border plants.

    Trees: z on the fitted ground (lift_doodads adds DOODAD_LIFT later, as
    for the editor trees). Brambles: z = ground + the flora lift by scale
    (SMALL_LIFT under SMALL_SCALE, else GROUND_LIFT)."""
    rng = random.Random(f"{config.SEED}:border")
    pool = tree_pool(objects)
    zones = keepouts(objects)
    out = []
    for row in ROWS:
        for x, y in perimeter((row - 0.3, row + 0.3), TREE_STEP, rng):
            kind, var, scale = rng.choice(pool)
            if not clear(x, y, zones):
                continue
            out.append((kind, var, x, y, ground(t, x, y), rng.uniform(0, 2 * math.pi), scale * BORDER_SCALE))
    low, high = config.FAMILIES[BRAMBLE].scale
    for x, y in perimeter(BRAMBLE_BAND, BRAMBLE_STEP, rng):
        var = rng.randrange(config.FAMILIES[BRAMBLE].variations)
        if not clear(x, y, zones):
            continue
        rotation = rng.uniform(0, 2 * math.pi)
        scale = rng.uniform(low, high) * BORDER_SCALE
        z = ground(t, x, y) + (config.SMALL_LIFT if scale < config.SMALL_SCALE else config.GROUND_LIFT)
        out.append((BRAMBLE, var, x, y, z, rotation, scale))
    return out
