"""Rule-based Zerus vegetation and lane hazards for the built map.

Runs on the built map after footprints.build (it reads the tree blockers).
plan() is deterministic: the same map and seed give the same plants and
hazards, so check_flora() recomputes it and compares. Idempotent: a marker
file makes a second apply a no-op. See docs/specifications/SPEC-FLORA.md.

Modules: config (knobs), grid (distance, paths, noise), terrain (height,
slope, water), scene (trees, units, keep-outs), lanes (lanes and balanced
hazards), rules (where each family grows), scatter (spacing and caps), build.
"""

from __future__ import annotations

import math
import random
import re
from collections import Counter
from pathlib import Path
from typing import NamedTuple

from footprints.catalog import append_catalog

from . import config, crush, scene as scene_mod, terrain as terrain_mod, treevary
from .grid import distance_to
from .lanes import Lane, Placed, find_lanes, hazard_cells, place_hazards, settle
from .rules import context
from .scatter import Plant, scatter


class Plan(NamedTuple):
    lanes: list[Lane]
    hazards: list[Placed]
    plants: list[Plant]
    detour: list[float]
    notes: list[str]


def plan(map_dir: Path, seed: int = config.SEED) -> Plan:
    terrain = terrain_mod.load(map_dir)
    scene = scene_mod.load(map_dir)
    lanes = find_lanes(terrain, scene)
    hazards, notes = place_hazards(lanes, terrain, scene)
    hazards, detour, dropped = settle(lanes, hazards, terrain, scene)
    notes += dropped
    ctx = context(terrain, scene, random.Random(seed), [pt for lane in lanes for pt in lane.points])
    plants = scatter(ctx, hazard_cells(hazards, terrain.height.shape[0]), seed)
    return Plan(lanes, hazards, plants, detour, notes)


def balance_problems(hazards: list[Placed], lane_count: int) -> list[str]:
    """Per lane, both factions must have the same hazards at the same pairs and arc distances."""
    problems = []
    sides = list(config.FACTION_SIDES)
    for lane in range(lane_count):
        per_side = [sorted((h.pair, h.kind, h.along) for h in hazards if h.lane == lane and h.side == s) for s in sides]
        if per_side[0] != per_side[1]:
            problems.append(f"lane {lane}: {sides[0]} {per_side[0]} != {sides[1]} {per_side[1]}")
    return problems


def doodad_xml(ident: int, kind: str, x: float, y: float, z: float, rotation: float, scale: float, variation: int) -> str:
    """Absolute z (HeightOffset + HeightAbsolute), the format of the editor-placed trees.

    z is the computed ground plus config.GROUND_LIFT: operator probe 2026-11-15
    (scripts/flora/probe.py) chose row F, ground +1.0. z 0 buries props off low ground.
    """
    return (
        f'    <ObjectDoodad Id="{ident}" Variation="{variation}" Position="{x:g},{y:g},{z:.4f}" Rotation="{rotation:g}"'
        f' Scale="{scale:g},{scale:g},{scale:g}" Type="{kind}">\n'
        '        <Flag Index="HeightOffset" Value="1"/>\n'
        '        <Flag Index="HeightAbsolute" Value="1"/>\n'
        "    </ObjectDoodad>\n"
    )


def objects_xml(p: Plan, next_id: int, terrain: terrain_mod.Terrain) -> str:
    rng = random.Random(f"{config.SEED}:hazards")
    entries = []
    ident = next_id
    for h in p.hazards:
        variation = rng.randrange(config.HAZARD_VARIATIONS[h.kind])
        z = terrain_mod.ground_z(terrain, h.x, h.y) + config.GROUND_LIFT
        entries.append(doodad_xml(ident, h.kind, h.x, h.y, z, h.rotation, 1.0, variation))
        ident += 1
    for plant in p.plants:
        z = terrain_mod.ground_z(terrain, plant.x, plant.y) + config.GROUND_LIFT
        entries.append(doodad_xml(ident, plant.kind, plant.x, plant.y, z, plant.rotation, plant.scale, plant.variation))
        ident += 1
    if ident > 2**31 - 1:
        raise ValueError(f"object ids overflow: {ident}")
    return "".join(entries)


def none_footprint_xml() -> str:
    layer = '        <Layers index="{0}" Area="0,0,1,1">\n            <Rows value="."/>\n        </Layers>\n'
    return f'    <CFootprint id="{config.NONE_FOOTPRINT}">\n' + layer.format("Check") + layer.format("Place") + "    </CFootprint>\n"


def plant_actors_xml() -> str:
    return "".join(
        f'    <CActorDoodad id="{kind}">\n        <Footprint value="{config.NONE_FOOTPRINT}"/>\n    </CActorDoodad>\n'
        for kind in config.FAMILIES
    )


def add_preload(path: Path, kinds: list[str], variations: dict[str, int]) -> None:
    text = path.read_text(encoding="utf-8")
    if "</Preload>" not in text:
        raise ValueError(f"{path} has no </Preload>")
    lines = "".join(
        f'<Actor id="{k}" Variations="{",".join(str(v) for v in range(variations[k]))}"/>\n' for k in kinds
    )
    path.write_text(text.replace("</Preload>", lines + "</Preload>", 1), encoding="utf-8")


def report_lines(p: Plan) -> list[str]:
    lines = [f"plants {len(p.plants)} hazards {len(p.hazards)} lanes {len(p.lanes)}"]
    for kind, count in sorted(Counter(pl.kind for pl in p.plants).items()):
        lines.append(f"family {kind} {count}")
    for lane in p.lanes:
        a, b, s = lane.points[0], lane.points[-1], lane.points[lane.split]
        lines.append(
            f"lane {lane.index} length {lane.length:.1f} detour {p.detour[lane.index]:.3f}"
            f" from ({a[0]:.1f},{a[1]:.1f}) split ({s[0]:.1f},{s[1]:.1f}) to ({b[0]:.1f},{b[1]:.1f})"
        )
    for h in p.hazards:
        lines.append(f"hazard lane {h.lane} pair {h.pair} {h.side} {h.kind} ({h.x:.2f},{h.y:.2f})")
    lines.extend(f"note {n}" for n in p.notes)
    return lines


def apply_flora(map_dir: Path) -> bool:
    map_dir = Path(map_dir)
    marker = map_dir / config.MARKER
    if marker.exists():
        return False
    p = plan(map_dir)
    problems = balance_problems(p.hazards, len(p.lanes)) + family_problems(p)
    (map_dir / config.REPORT).write_text("\n".join(report_lines(p)) + "\n", encoding="utf-8")
    if problems:
        raise ValueError("flora plan failed:\n" + "\n".join(problems))
    objects = map_dir / "Objects"
    text = objects.read_text(encoding="utf-8")
    if "</PlacedObjects>" not in text:
        raise ValueError(f"{objects} has no </PlacedObjects>")
    next_id = scene_mod.load(map_dir).next_id
    objects.write_text(text.replace("</PlacedObjects>", objects_xml(p, next_id, terrain_mod.load(map_dir)) + "</PlacedObjects>", 1), encoding="utf-8")
    data = map_dir / "Base.SC2Data" / "GameData"
    append_catalog(data / "FootprintData.xml", none_footprint_xml())
    append_catalog(data / "ActorData.xml", plant_actors_xml())
    (map_dir / crush.DATA_FILE).write_text(crush.galaxy(crush_rows(p, terrain_mod.load(map_dir))), encoding="utf-8")
    variations = {k: f.variations for k, f in config.FAMILIES.items()} | config.HAZARD_VARIATIONS
    add_preload(map_dir / "Preload.xml", sorted({h.kind for h in p.hazards} | {pl.kind for pl in p.plants}), variations)
    marker.write_text(f"plants={len(p.plants)} hazards={len(p.hazards)} lanes={len(p.lanes)}\n", encoding="utf-8")
    return True


def family_problems(p: Plan) -> list[str]:
    counts = Counter(pl.kind for pl in p.plants)
    return [f"family {kind} has no instance" for kind in config.FAMILIES if counts[kind] == 0]


def placed_doodads(map_dir: Path) -> list[tuple[str, float, float, float, bool]]:
    """(kind, x, y, z, absolute height flag) of every placed flora or hazard doodad."""
    text = (Path(map_dir) / "Objects").read_text(encoding="utf-8")
    kinds = set(config.FAMILIES) | set(config.HAZARD_VARIATIONS)
    out = []
    pattern = r'<ObjectDoodad\b[^>]*\bPosition="([^"]+)"[^>]*\bType="([^"]+)"[^>]*?(/>|>(.*?)</ObjectDoodad>)'
    for match in re.finditer(pattern, text, re.S):
        if match.group(2) in kinds:
            x, y, z = (float(v) for v in match.group(1).split(",")[:3])
            absolute = 'Index="HeightAbsolute" Value="1"' in (match.group(4) or "")
            out.append((match.group(2), x, y, z, absolute))
    return out


GROUND_TOLERANCE = 0.25


def check_flora(map_dir: Path) -> list[str]:
    """Problems with the built map's flora. Empty when all pass."""
    map_dir = Path(map_dir)
    p = plan(map_dir)
    want = sorted([(h.kind, h.x, h.y) for h in p.hazards] + [(pl.kind, pl.x, pl.y) for pl in p.plants])
    placed = placed_doodads(map_dir)
    have = sorted((kind, x, y) for kind, x, y, _z, _a in placed)
    problems = balance_problems(p.hazards, len(p.lanes)) + family_problems(p)
    if want != have:
        problems.append(f"placed flora differs from the plan: {len(have)} placed, {len(want)} planned")
    terrain = terrain_mod.load(map_dir)
    off_ground = [
        (k, x, y, z) for k, x, y, z, a in placed
        if not a or abs(z - terrain_mod.ground_z(terrain, x, y) - config.GROUND_LIFT) > GROUND_TOLERANCE
    ]
    if off_ground:
        problems.append(f"{len(off_ground)} flora doodads are not at ground + {config.GROUND_LIFT}, e.g. {off_ground[:3]}")
    actors = (map_dir / "Base.SC2Data" / "GameData" / "ActorData.xml").read_text(encoding="utf-8")
    for kind in config.FAMILIES:
        block = re.search(r'<CActorDoodad id="' + kind + r'">\s*<Footprint value="([^"]+)"/>', actors)
        if block is None or block.group(1) != config.NONE_FOOTPRINT:
            problems.append(f"{kind} keeps a blocking footprint")
    models = (map_dir / "Base.SC2Data" / "GameData" / "ModelData.xml").read_text(encoding="utf-8")
    lane_points = [pt for lane in p.lanes for pt in lane.points]
    to_wet = distance_to(terrain.wet)
    for k, x, y, _z, _a in placed:
        if k != "ZerusBrambles":
            continue
        to_lane = min(math.hypot(x - lx, y - ly) for lx, ly in lane_points)
        if to_wet[int(y), int(x)] <= config.BRAMBLE_WATER_CLEAR or to_lane <= config.BRAMBLE_LANE_CLEAR - 1:
            problems.append(f"bramble at ({x:.1f},{y:.1f}) is near water or on a lane (lane {to_lane:.1f})")
    for h in p.hazards:
        clear = config.HAZARD_WATER_CLEAR.get(h.kind, 0.0)
        if clear > 0.0 and to_wet[int(h.y), int(h.x)] < config.HAZARD_HALF[h.kind] + clear - 1.0:
            problems.append(f"{h.kind} at ({h.x:.1f},{h.y:.1f}) is {to_wet[int(h.y), int(h.x)]:.1f} from water")
    wet = terrain.depth > 0
    in_river = sum(1 for _k, x, y, _z, _a in placed if wet[int(y), int(x)])
    if 100 * in_river < config.RIVER_MIN_PER_100 * int(wet.sum()):
        problems.append(f"river holds {in_river} props, under {config.RIVER_MIN_PER_100} per 100 of {int(wet.sum())} water cells")
    if len(placed) > config.FLORA_CAP:
        problems.append(f"{len(placed)} flora props exceed the cap {config.FLORA_CAP}")
    for k, x, y, _z, _a in placed:
        if k in ("ZerusTallGrassCluster", "ZerusWaterPlant") and min(math.hypot(x - lx, y - ly) for lx, ly in lane_points) <= config.GRASS_LANE_CLEAR - 1:
            problems.append(f"{k} at ({x:.1f},{y:.1f}) is on a lane")
    want_crush = crush.galaxy(crush_rows(p, terrain))
    crush_path = map_dir / crush.DATA_FILE
    have_crush = crush_path.read_text(encoding="utf-8").replace("\r\n", "\n") if crush_path.exists() else ""
    if have_crush != want_crush:
        problems.append(f"{crush.DATA_FILE} does not match the placed crushable flora")
    lookalikes = treevary.conflicts([t for _m, t in treevary.parse((map_dir / "Objects").read_text(encoding="utf-8"))])
    if lookalikes:
        problems.append(f"{len(lookalikes)} neighbouring tree pairs look alike (scale, rotation and variation)")
    # Placed flora must never fade: doodad_occlusion sets Occlusion None; it must run after apply_flora.
    for kind in sorted({k for k, *_ in placed}):
        block = re.search(r'<CModel id="' + kind + r'">(.*?)</CModel>', models, re.S)
        if block is None or not re.search(r'<Occlusion value="None"\s*/>', block.group(1)):
            problems.append(f"model {kind} can fade (no Occlusion None)")
    problems.extend(f"lane {i} detour {d:.2f} over {config.LANE_DETOUR_MAX}" for i, d in enumerate(p.detour) if d > config.LANE_DETOUR_MAX or not math.isfinite(d))
    return problems


def crush_rows(p: Plan, terrain: terrain_mod.Terrain) -> list[tuple[str, float, float, float, float]]:
    """(kind, x, y, z, scale) per plant; z is the placed doodad height."""
    return [(pl.kind, pl.x, pl.y, round(terrain_mod.ground_z(terrain, pl.x, pl.y) + config.GROUND_LIFT, 3), pl.scale) for pl in p.plants]
