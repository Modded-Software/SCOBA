"""Build step: waterfalls at the inner rim of the map (REQ-RIM-FALLS).

Runs on the built map right after the water features, before resources,
footprints and flora, so they see the cut ground.

Writes: t3HeightMap (basins), Objects (falls and rocks added, trees on
moved ground moved with it), ActorData.xml and FootprintData.xml (the rock
without a footprint), Preload.xml, and a marker with the report. Pathing is
not painted: the rim stays walkable.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import NamedTuple

import numpy as np

from flora.terrain import water_rects
from mapgen.footprints.catalog import append_catalog
from mapgen.waterfeatures import build as water_build
from mapgen.waterfeatures import ground
from mapgen.waterfeatures.models import Models, rotation_facing

from . import carve, compose, config, sites as site_finder
from .models import load


class Plan(NamedTuple):
    ground: np.ndarray
    groups: tuple[compose.Group, ...]


def make(vz: np.ndarray, sites: list[site_finder.Site], models: Models) -> Plan:
    """Cut every basin, then stand the groups on the cut ground."""
    cut = vz
    edges = [carve.basin_edge(vz, site) for site in sites]
    for site, edge in zip(sites, edges):
        cut = carve.cut(cut, site, edge)
    return Plan(cut, tuple(compose.make(i, site, cut, edge, models) for i, (site, edge) in enumerate(zip(sites, edges))))


def turn_gap(a: float, b: float) -> float:
    d = abs(a - b) % math.tau
    return min(d, math.tau - d)


def problems(old: np.ndarray, plan: Plan, models: Models | None = None) -> list[str]:
    out = site_finder.problems([g.site for g in plan.groups])
    delta = plan.ground - old
    if delta.max() > 1e-9:
        out.append(f"rim falls: the ground is raised by {delta.max():.2f}")
    if -delta.min() > config.MAX_CUT:
        out.append(f"rim falls: the ground is cut by {-delta.min():.2f}, over {config.MAX_CUT}")
    n = old.shape[0] - 1
    for i, g in enumerate(plan.groups):
        want = rotation_facing(g.site.dir)
        kinds = [p.kind for p in g.falls]
        if config.ROCK_FALL not in kinds or config.FALL not in kinds:
            out.append(f"rim falls: group {i} lacks a rock or a normal waterfall")
        if not g.rocks:
            out.append(f"rim falls: group {i} has no rock in its basin")
        for p in g.falls:
            if turn_gap(p.rotation, want) > config.TURN_JITTER + 1e-6:
                out.append(f"rim falls: group {i} {p.kind} is turned {turn_gap(p.rotation, want):.2f} off the wall normal")
            if p.kind == config.ROCK_FALL and models is not None:
                share = compose.embedded(plan.ground, models, p, g.surface)
                if share < config.EMBED_MIN:
                    out.append(f"rim falls: group {i} {p.kind} at {p.x:.1f},{p.y:.1f} is embedded {share:.2f} of its height, under {config.EMBED_MIN}")
            if not (1.0 <= p.x <= n - 1.0 and 1.0 <= p.y <= n - 1.0):
                out.append(f"rim falls: group {i} {p.kind} is off the map")
    return out


def catalog_xml() -> tuple[str, str]:
    """(footprint, actor): the basin rock is the stock rock without a footprint."""
    layer = '        <Layers index="{0}" Area="0,0,1,1">\n            <Rows value="."/>\n        </Layers>\n'
    footprint = f'    <CFootprint id="{config.NONE_FOOTPRINT}">\n' + layer.format("Check") + layer.format("Place") + "    </CFootprint>\n"
    actor = (
        f'    <CActorDoodad id="{config.ROCK}" parent="{config.ROCK_SOURCE}">\n'
        f'        <Model value="{config.ROCK_SOURCE}"/>\n'
        f'        <Footprint value="{config.NONE_FOOTPRINT}"/>\n'
        "    </CActorDoodad>\n"
    )
    return footprint, actor


def preload_rocks(path: Path, used: set[int]) -> None:
    if not path.is_file() or not used:
        return
    text = path.read_bytes().decode("utf-8")
    if "</Preload>" not in text:
        raise ValueError(f"{path} has no </Preload>")
    newline = "\r\n" if "\r\n" in text else "\n"
    line = f'<Actor id="{config.ROCK}" Variations="{",".join(map(str, sorted(used)))}"/>{newline}'
    path.write_bytes(text.replace("</Preload>", line + "</Preload>", 1).encode("utf-8"))


def report(plan: Plan, models: Models, old: np.ndarray, trees: int, vertices: int) -> str:
    falls = sum(len(g.falls) for g in plan.groups)
    rocks = sum(len(g.rocks) for g in plan.groups)
    delta = plan.ground - old
    lines = [
        f"groups={len(plan.groups)} falls={falls} rocks={rocks} trees_moved={trees} vertices_moved={vertices}",
        "heights below are in ground space (computed ground); doodads are written higher (waterfeatures doodad_rise)",
        f"ground change: lowest {delta.min():.2f} highest {delta.max():.2f}",
    ]
    for i, g in enumerate(plan.groups):
        s = g.site
        lines.append(
            f"group {i}: sector {s.sector} at {s.x:.0f},{s.y:.0f} normal {s.dir[0]:+.2f},{s.dir[1]:+.2f} (turn {rotation_facing(s.dir):.3f})"
            f" slope {s.slope:.2f} clear {s.clear:.1f} basin {g.basin[0]:.1f},{g.basin[1]:.1f} edge {g.edge:.2f} surface {g.surface:.2f}"
        )
        for p in g.falls:
            top = p.z + models.falls[p.kind][p.variation].hi[2] * p.scale
            lines.append(f"  fall {p.kind} v{p.variation}: at {p.x:.2f},{p.y:.2f},{p.z:.2f} turn {p.rotation:.3f} scale {p.flat:.3f}x{p.scale:.3f} top {top:.2f}" + (f" embedded {compose.embedded(plan.ground, models, p, g.surface):.2f}" if p.kind == config.ROCK_FALL else ""))
        for r in g.rocks:
            lines.append(f"  rock {r.kind} v{r.variation}: at {r.x:.2f},{r.y:.2f},{r.z:.2f} turn {r.rotation:.3f} scale {r.scale:.3f}")
    return "\n".join(lines) + "\n"


def apply_rim_falls(map_dir: Path, models: Models | None = None) -> str:
    map_dir = Path(map_dir)
    marker = map_dir / config.MARKER
    if marker.exists():
        return ""
    models = models or load()
    objects_path = map_dir / "Objects"
    objects = objects_path.read_bytes().decode("utf-8")
    old = ground.vertex_z(map_dir)
    found = site_finder.find(old, site_finder.placed_points(objects), [rect for _name, rect in water_rects(map_dir)])
    plan = make(old, found, models)
    wrong = problems(old, plan, models)
    if wrong:
        raise ValueError("rim falls failed:\n" + "\n".join(wrong))

    objects, trees = water_build.move_trees(objects, old, plan.ground)
    falls = [p for g in plan.groups for p in g.falls]
    rocks = tuple(r for g in plan.groups for r in g.rocks)
    objects = water_build.add_doodads(objects, falls, water_build.doodad_rise(map_dir), rocks)
    objects_path.write_bytes(objects.encode("utf-8"))
    vertices = ground.write_vertex_z(map_dir, old, plan.ground)
    data = map_dir / "Base.SC2Data" / "GameData"
    footprint, actor = catalog_xml()
    append_catalog(data / "FootprintData.xml", footprint)
    append_catalog(data / "ActorData.xml", actor)
    water_build.update_preload(map_dir / "Preload.xml", objects)
    preload_rocks(map_dir / "Preload.xml", {r.variation for r in rocks})

    back = ground.vertex_z(map_dir)
    off = float(np.abs(back - plan.ground).max())
    if off > 0.01:
        raise ValueError(f"rim falls: written ground is {off:.3f} off the plan")
    text = report(plan, models, old, trees, vertices)
    marker.write_text(text, encoding="utf-8")
    return text
