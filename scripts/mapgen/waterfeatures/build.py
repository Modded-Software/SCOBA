"""Build step: water features of the built map (REQ-WATER-FEATURES).

Runs on the built map after the props are placed, so positions are in
256-map units, and before resources, footprints and flora, so they see the
final ground. The engine ground (terrain/sync_height.py) is baked later
from the same height map.

Writes: t3HeightMap (carved ground), Objects (placed water doodads of the
sites dropped, the feature's falls and rocks added, trees on moved ground
moved with it), WaterData.xml (pool height), CellAttribute_Pnp (pool
unpathable), t3TextureMasks (dirt texture on the pool walls), Preload.xml,
and a marker with the report.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from flora import config as flora_config
from flora import lift
from flora.terrain import bilinear, water_rects
from mapgen import spore_scale

from . import compose, config, ground, paint, plan as planner, sites as site_finder
from .compose import Placement
from .models import Models, load

MARKER = ".water_features"
BLOCK_RE = re.compile(r"([ \t]*)<ObjectDoodad\b[^>]*?(?:/>|>.*?</ObjectDoodad>)[ \t]*\r?\n", re.S)


def _attr(block: str, name: str) -> str | None:
    m = re.search(rf'\b{name}="([^"]*)"', block.split(">", 1)[0])
    return m.group(1) if m else None


def pending_unit_scale(map_dir: Path) -> dict[str, float]:
    """Scale a later build step still applies to placed pipe units."""
    if (Path(map_dir) / spore_scale.PSI_DESTROYER_MARKER).exists():
        return {}
    return {unit: spore_scale.PSI_DESTROYER_SCALE for unit in spore_scale.PSI_DESTROYER_UNITS}


def drop_placed(text: str, sites: list[site_finder.Site]) -> tuple[str, int]:
    """Objects without the placed water doodads at the sites: the feature replaces them."""
    dropped = 0

    def repl(m: re.Match) -> str:
        nonlocal dropped
        block = m.group(0)
        if _attr(block, "Type") not in config.WATER_TYPES:
            return block
        x, y, _z = (float(v) for v in _attr(block, "Position").split(","))
        if any(site_finder.rect_distance((x, y), site.rect) <= config.CLEAR_MARGIN for site in sites):
            dropped += 1
            return ""
        return block

    return BLOCK_RE.sub(repl, text), dropped


def move_trees(text: str, old: np.ndarray, new: np.ndarray) -> tuple[str, int]:
    """Trees with an absolute height follow the ground they stand on."""
    moved = 0

    def repl(m: re.Match) -> str:
        nonlocal moved
        block = m.group(0)
        if not (_attr(block, "Type") or "").startswith("ZerusTree") or 'Index="HeightAbsolute" Value="1"' not in block:
            return block
        x, y, z = _attr(block, "Position").split(",")
        delta = bilinear(new, float(x), float(y)) - bilinear(old, float(x), float(y))
        if abs(delta) < 0.01:
            return block
        moved += 1
        head, sep, rest = block.partition(">")
        return re.sub(r'\bPosition="[^"]*"', f'Position="{x},{y},{float(z) + delta:.4f}"', head, count=1) + sep + rest

    return BLOCK_RE.sub(repl, text), moved


def doodad_rise(map_dir: Path) -> float:
    """Planned z to the z written to Objects.

    The plan is in ground space: the computed ground of flora/terrain.py.
    A doodad with an absolute height sits on the visible ground at computed
    ground + GROUND_LIFT (flora, tuned by the operator 2026-11-16). The
    water height is in that same space. flora.lift later raises every
    non-flora absolute doodad by DOODAD_LIFT, so that part is left out here
    while the lift is still to come.
    """
    pending = 0.0 if (Path(map_dir) / lift.MARKER).exists() else flora_config.DOODAD_LIFT
    return flora_config.GROUND_LIFT - pending


def doodad_xml(oid: int, p: Placement, rise: float, newline: str) -> str:
    variation = f' Variation="{p.variation}"' if p.variation else ""
    flags = "".join(f'        <Flag Index="{flag}" Value="1"/>{newline}' for flag in config.FLAGS)
    return (
        f'    <ObjectDoodad Id="{oid}"{variation} Position="{p.x:.4f},{p.y:.4f},{p.z + rise:.4f}" Rotation="{p.rotation:.4f}"'
        f' Scale="{p.flat:.4f},{p.flat:.4f},{p.scale:.4f}" Type="{p.kind}">{newline}{flags}    </ObjectDoodad>{newline}'
    )


def rock_xml(oid: int, r: compose.RockPlacement, rise: float, newline: str) -> str:
    flags = "".join(f'        <Flag Index="{flag}" Value="1"/>{newline}' for flag in config.FLAGS)
    return (
        f'    <ObjectDoodad Id="{oid}" Variation="{r.variation}" Position="{r.x:.4f},{r.y:.4f},{r.z + rise:.4f}" Rotation="{r.rotation:.4f}"'
        f' Scale="{r.scale:.4f},{r.scale:.4f},{r.scale:.4f}" Type="{r.kind}">{newline}{flags}    </ObjectDoodad>{newline}'
    )


def add_doodads(text: str, placements: list[Placement], rise: float, rocks: tuple[compose.RockPlacement, ...] = ()) -> str:
    close = text.rfind("</PlacedObjects>")
    if close < 0:
        raise ValueError("no </PlacedObjects> in Objects")
    newline = "\r\n" if "\r\n" in text else "\n"
    next_id = max((int(v) for v in re.findall(r'\bId="(\d+)"', text)), default=0) + 1
    body = "".join(doodad_xml(next_id + k, p, rise, newline) for k, p in enumerate(placements))
    body += "".join(rock_xml(next_id + len(placements) + k, r, rise, newline) for k, r in enumerate(rocks))
    return text[:close] + body + text[close:]


def update_preload(path: Path, objects: str) -> None:
    """Preload every placed water doodad type, with the variations placed."""
    if not path.is_file():
        return
    pre = path.read_bytes().decode("utf-8")
    newline = "\r\n" if "\r\n" in pre else "\n"
    placed: dict[str, set[int]] = {}
    for m in BLOCK_RE.finditer(objects):
        kind = _attr(m.group(0), "Type")
        if kind in config.WATER_TYPES or kind == config.ROCK_TYPE:
            placed.setdefault(kind, set()).add(int(_attr(m.group(0), "Variation") or 0))
    for kind, used in sorted(placed.items()):
        varied = kind in ("RockWaterfall", config.ROCK_TYPE)  # models with variations
        line = f'<Actor id="{kind}" Variations="{",".join(map(str, sorted(used)))}"/>' if varied else f'<Actor id="{kind}"/>'
        entry = re.compile(rf'<Actor id="{kind}"( Variations="[^"]*")?/>')
        if entry.search(pre):
            pre = entry.sub(line, pre, count=1)
            continue
        actors = list(re.finditer(r'<Actor id="[^"]*"[^>]*/>', pre))
        at = actors[-1].end() if actors else pre.rfind("</Preload>")
        if at < 0:
            raise ValueError(f"no place for {kind} in {path}")
        pre = pre[:at] + (newline + line if actors else line + newline) + pre[at:]
    path.write_bytes(pre.encode("utf-8"))


def no_path_cells(plan: planner.Plan, models: Models | None = None) -> np.ndarray:
    """Cells of the pools deep enough to block, and the cells under the rocks."""
    n = plan.ground.shape[0] - 1
    cells = np.zeros((n, n), dtype=bool)
    vz = plan.ground
    for i, site in enumerate(plan.sites):
        level = plan.levels[site.water]
        deep = plan.pools[i] & (vz < level - config.NO_PATH_DEPTH)
        # A cell is blocked when any of its four vertices is deep water.
        cells |= deep[:-1, :-1] | deep[1:, :-1] | deep[:-1, 1:] | deep[1:, 1:]
    for r in plan.rocks:
        reach = models.rocks[r.kind][r.variation].radius * r.scale if models else 0.0
        for cy in range(max(0, int(r.y - reach)), min(n, int(r.y + reach) + 1)):
            for cx in range(max(0, int(r.x - reach)), min(n, int(r.x + reach) + 1)):
                # The cell's nearest point to the rock is within its reach.
                if np.hypot(min(max(r.x, cx), cx + 1) - r.x, min(max(r.y, cy), cy + 1) - r.y) <= reach:
                    cells[cy, cx] = True
    return cells


def report(plan: planner.Plan, models: Models, old: np.ndarray, dropped: int, trees: int, vertices: int, painted: int, rock: int) -> str:
    lines = [f"sites={len(plan.sites)} dropped_placed={dropped} trees_moved={trees} vertices_moved={vertices} cells_painted={painted}"]
    lines.append(f"wall texture {config.WALL_TEXTURE}: {rock} mask cells gained dirt on the pool walls")
    lines.append("heights below are in ground space (computed ground); doodads and water are written GROUND_LIFT higher")
    delta = plan.ground - old
    lines.append(f"ground change: lowest {delta.min():.2f} highest {delta.max():.2f}")
    for i, site in enumerate(plan.sites):
        level = plan.levels[site.water]
        lines.append(
            f"site {i}: water {site.water} rect {site.rect} level {level:.3f} (WaterData height {level + flora_config.GROUND_LIFT:.3f})"
            f" pool_vertices {int(plan.pools[i].sum())}"
        )
        for k, m in enumerate(site.mouths):
            lines.append(f"  mouth {k}: at {m.x:.2f},{m.y:.2f} lip {m.lip_z:.2f} top {m.top_z:.2f} radius {m.radius:.2f} drop {m.lip_z - level:.2f}")
        for p in plan.placements:
            if p.site == i:
                lines.append(
                    f"  fall {p.kind} v{p.variation}: at {p.x:.2f},{p.y:.2f},{p.z:.2f} turn {p.rotation:.3f} scale {p.flat:.3f}x{p.scale:.3f}"
                    f" top {compose.top_z(models, p):.2f} surface {compose.surface_z(models, p):.2f}"
                )
        for r in plan.rocks:
            if r.site == i:
                top = r.z + models.rocks[r.kind][r.variation].hi[2] * r.scale
                lines.append(f"  rock {r.kind} v{r.variation}: at {r.x:.2f},{r.y:.2f},{r.z:.2f} turn {r.rotation:.3f} scale {r.scale:.3f} top {top:.2f} (water {level:.2f})")
    return "\n".join(lines) + "\n"


def apply_water_features(map_dir: Path, models: Models | None = None) -> str:
    map_dir = Path(map_dir)
    marker = map_dir / MARKER
    if marker.exists():
        return ""
    models = models or load()
    objects_path = map_dir / "Objects"
    objects = objects_path.read_bytes().decode("utf-8")
    old = ground.vertex_z(map_dir)
    mouths = site_finder.pipe_mouths(objects, models, lambda x, y: bilinear(old, x, y), pending_unit_scale(map_dir))
    found = site_finder.find(water_rects(map_dir), mouths)
    if not found:
        raise ValueError(f"water features: no {config.SITE_WATER} water under a pipe of {sorted(config.PIPE_UNITS)}")
    plan = planner.make(old, found, models)
    wrong = planner.problems(old, plan, models) + paint.problems(map_dir)
    if wrong:
        raise ValueError("water features failed:\n" + "\n".join(wrong))

    objects, dropped = drop_placed(objects, found)
    objects, trees = move_trees(objects, old, plan.ground)
    objects = add_doodads(objects, plan.placements, doodad_rise(map_dir), plan.rocks)
    objects_path.write_bytes(objects.encode("utf-8"))
    vertices = ground.write_vertex_z(map_dir, old, plan.ground)
    water = map_dir / "Base.SC2Data" / "GameData" / "WaterData.xml"
    text = water.read_bytes().decode("utf-8")
    for name, level in sorted(plan.levels.items()):
        # Water height is in doodad space: ground space + GROUND_LIFT.
        text = ground.set_water_height(text, name, level + flora_config.GROUND_LIFT)
    water.write_bytes(text.encode("utf-8"))
    painted = ground.paint_no_path(map_dir, no_path_cells(plan, models))
    update_preload(map_dir / "Preload.xml", objects)
    rock = paint.apply(map_dir, plan.ground, plan.sites)

    # What was written is what was planned: the ground is read back.
    back = ground.vertex_z(map_dir)
    off = float(np.abs(back - plan.ground).max())
    if off > 0.01:
        raise ValueError(f"water features: written ground is {off:.3f} off the plan")
    text = report(plan, models, old, dropped, trees, vertices, painted, rock)
    marker.write_text(text, encoding="utf-8")
    return text
