"""Pathing blockers of scaled trees and spores, measured in game.

Targets come from the built map: the largest tree, the tree whose blocker sits
farthest from its origin (lean), a thin tree, a tree whose rotation is far from
a quarter turn, one SporeCannon, one SporeCrawler, and the caged ultralisk
(HybridUltraliskShackled, 12x12 square blocker).

Per target, from its generated Shape placed the way the fprot probe found
(quarter-turn snap, position rounded to 0.5):

- inner probes: sub-cell centres deep inside the Shape. Must be blocked.
- outer probes: points about one unit outside the Shape, not inside any
  other object's blocker. Must be passable (the negative case).
- walk: the hero walks across the target. Its sampled path must stay out of
  the Shape (with the hero's radius as slack) and reach the far side.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import NamedTuple

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
BUILT = ROOT / "out" / "SCOBA256.SC2Map"
TARGETS_GALAXY = ROOT / "out" / "testkit" / "treepath" / "treepath_targets.galaxy"
MAP_CELLS = 256
# Targets keep this far from the map edge, which is unpathable terrain
# (run 20261115-133213: a tree at x = 9 had no open ground around it).
EDGE = 16.0
SUB = 0.5
# Probes sit this far outside the Shape.
OUTER = 1.0
# Inner probes sit at least this far inside the Shape edge.
INNER_DEPTH = 0.3
# Objects without a known blocker count as a disk of this radius.
OTHER_RADIUS = 1.0
# How far the hero centre may get inside the Shape: its own collision and the
# 0.5 grid rounding of the placed position.
HERO_SLACK = 0.6
WALK_MARGIN = 3.0
MAX_PROBES = 16
SECTIONS = ("tree_large", "tree_lean", "tree_thin", "tree_turned", "spore_cannon", "spore_crawler", "cage_ultralisk")

Polygon = tuple[tuple[float, float], ...]


class Obstacle(NamedTuple):
    kind: str
    ident: str
    polygon: Polygon  # world space

    @property
    def centre(self) -> tuple[float, float]:
        xs = [x for x, _ in self.polygon]
        ys = [y for _, y in self.polygon]
        return (sum(xs) / len(xs), sum(ys) / len(ys))

    @property
    def area(self) -> float:
        return abs(signed_area(self.polygon))


def signed_area(poly: Polygon) -> float:
    return sum(poly[i - 1][0] * poly[i][1] - poly[i][0] * poly[i - 1][1] for i in range(len(poly))) / 2


def inside(poly: Polygon, x: float, y: float) -> bool:
    hit = False
    for i in range(len(poly)):
        x1, y1 = poly[i - 1]
        x2, y2 = poly[i]
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def edge_distance(poly: Polygon, x: float, y: float) -> float:
    best = math.inf
    for i in range(len(poly)):
        x1, y1 = poly[i - 1]
        x2, y2 = poly[i]
        dx, dy = x2 - x1, y2 - y1
        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
        best = min(best, math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)))
    return best


def engine_quarter_turns(rotation: float) -> int:
    return math.ceil(math.degrees(rotation) / 90.0 - 0.5 - 1e-9) % 4


def place(poly: Polygon, x: float, y: float, rotation: float) -> Polygon:
    """Shape in world space as the engine places it (fprot runs 20261115-132312, -132422)."""
    turns = engine_quarter_turns(rotation)
    px = math.floor(x / SUB + 0.5) * SUB
    py = math.floor(y / SUB + 0.5) * SUB
    out = []
    for vx, vy in poly:
        for _ in range(turns):
            vx, vy = -vy, vx
        out.append((px + vx, py + vy))
    return tuple(out)


def _attr(block: str, name: str) -> str | None:
    match = re.search(rf'\b{name}="([^"]*)"', block)
    return match.group(1) if match else None


def _shapes(map_dir: Path) -> dict[str, Polygon]:
    text = (map_dir / "Base.SC2Data" / "GameData" / "FootprintData.xml").read_text(encoding="utf-8")
    shapes = {}
    for match in re.finditer(r'<CFootprint\b[^>]*\bid="(FootprintScoba[0-9a-f]+)"[^>]*>(.*?)</CFootprint>', text, re.S):
        offsets = re.search(r'<Offsets value="([^"]+)"/>', match.group(2))
        if offsets:
            shapes[match.group(1)] = tuple(
                (float(a), float(b)) for a, b in (pair.split(",") for pair in offsets.group(1).split(";"))
            )
    return shapes


def _links(path: Path, tag: str) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    links = {}
    for match in re.finditer(r"<" + tag + r'\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</' + tag + ">", text, re.S):
        fp = re.search(r'<Footprint value="(FootprintScoba[0-9a-f]+)"/>', match.group(2))
        if fp:
            links[match.group(1)] = fp.group(1)
    return links


def disk(x: float, y: float, r: float) -> Polygon:
    return tuple((x + r * math.cos(a * math.pi / 8), y + r * math.sin(a * math.pi / 8)) for a in range(16))


def obstacles(map_dir: Path) -> list[Obstacle]:
    shapes = _shapes(map_dir)
    game = map_dir / "Base.SC2Data" / "GameData"
    actors = _links(game / "ActorData.xml", "CActorDoodad")
    units = _links(game / "UnitData.xml", "CUnit")
    text = (map_dir / "Objects").read_text(encoding="utf-8")
    found = []
    for match in re.finditer(r"<Object(Doodad|Unit)\b[^>]*>", text):
        block = match.group(0)
        position = _attr(block, "Position")
        if position is None:
            continue
        x, y = (float(v) for v in position.split(",")[:2])
        rotation = float(_attr(block, "Rotation") or 0.0)
        kind = _attr(block, "Type") or _attr(block, "UnitType") or ""
        ident = _attr(block, "Id") or ""
        if kind in actors:
            found.append(Obstacle("tree", ident, place(shapes[actors[kind]], x, y, rotation)))
        elif kind in units:
            # Structures do not turn their footprint; spore blockers are round anyway.
            found.append(Obstacle(kind, ident, place(shapes[units[kind]], x, y, 0.0)))
        else:
            found.append(Obstacle("other", ident, disk(x, y, OTHER_RADIUS)))
    return found


def blocked_by_other(target: Obstacle, every: list[Obstacle], x: float, y: float, slack: float = 0.5) -> bool:
    for other in every:
        if other is target:
            continue
        if inside(other.polygon, x, y) or edge_distance(other.polygon, x, y) < slack:
            return True
    return False


def in_bounds(o: Obstacle) -> bool:
    xs = [x for x, _ in o.polygon]
    ys = [y for _, y in o.polygon]
    return min(xs) > EDGE and min(ys) > EDGE and max(xs) < MAP_CELLS - EDGE and max(ys) < MAP_CELLS - EDGE


def inner_probes(target: Obstacle) -> list[tuple[float, float]]:
    xs = [x for x, _ in target.polygon]
    ys = [y for _, y in target.polygon]
    points = []
    y = math.floor(min(ys) / SUB) * SUB + SUB / 2
    while y < max(ys):
        x = math.floor(min(xs) / SUB) * SUB + SUB / 2
        while x < max(xs):
            if inside(target.polygon, x, y) and edge_distance(target.polygon, x, y) >= INNER_DEPTH:
                points.append((x, y))
            x += SUB
        y += SUB
    if not points:
        points = [target.centre] if inside(target.polygon, *target.centre) else []
    stride = max(1, len(points) // MAX_PROBES)
    return points[::stride][:MAX_PROBES]


def outer_probes(target: Obstacle, every: list[Obstacle]) -> list[tuple[float, float]]:
    cx, cy = target.centre
    points = []
    for k in range(MAX_PROBES):
        angle = 2 * math.pi * k / MAX_PROBES
        dx, dy = math.cos(angle), math.sin(angle)
        # March out from the centre until OUTER past the Shape edge.
        d = 0.0
        while d < 40.0:
            x, y = cx + dx * d, cy + dy * d
            if not inside(target.polygon, x, y) and edge_distance(target.polygon, x, y) >= OUTER:
                break
            d += 0.05
        if not blocked_by_other(target, every, x, y):
            points.append((round(x, 3), round(y, 3)))
    return points


def walk(target: Obstacle, every: list[Obstacle]) -> tuple[tuple[float, float], tuple[float, float]] | None:
    cx, cy = target.centre
    reach = max(math.hypot(x - cx, y - cy) for x, y in target.polygon) + WALK_MARGIN
    for k in range(8):
        a = math.pi * k / 8
        start = (cx + reach * math.cos(a), cy + reach * math.sin(a))
        end = (cx - reach * math.cos(a), cy - reach * math.sin(a))
        if not any(blocked_by_other(target, every, *p, slack=1.0) for p in (start, end)):
            return start, end
    return None


def pick_targets(every: list[Obstacle], map_dir: Path = BUILT) -> dict[str, Obstacle]:
    text = (map_dir / "Objects").read_text(encoding="utf-8")
    rotations = {
        _attr(m.group(0), "Id"): float(_attr(m.group(0), "Rotation") or 0.0)
        for m in re.finditer(r"<ObjectDoodad\b[^>]*>", text)
    }
    origins = {
        _attr(m.group(0), "Id"): tuple(float(v) for v in (_attr(m.group(0), "Position") or "0,0").split(",")[:2])
        for m in re.finditer(r"<ObjectDoodad\b[^>]*>", text)
    }
    usable = [
        o for o in every
        if o.kind != "other" and in_bounds(o) and walk(o, every) is not None and len(outer_probes(o, every)) >= 4
    ]
    trees = [o for o in usable if o.kind == "tree"]
    if not trees:
        raise SystemExit("treepath: no usable tree")

    def lean(o: Obstacle) -> float:
        ox, oy = origins[o.ident]
        cx, cy = o.centre
        return math.hypot(cx - ox, cy - oy)

    def off_quarter(o: Obstacle) -> float:
        degrees = math.degrees(rotations[o.ident]) % 90
        return -abs(degrees - 45)

    picks = {"tree_large": max(trees, key=lambda o: (o.area, o.ident))}
    for name, key in (("tree_lean", lean), ("tree_thin", lambda o: -o.area), ("tree_turned", off_quarter)):
        rest = [o for o in trees if o not in picks.values()]
        picks[name] = max(rest, key=lambda o: (key(o), o.ident))
    for unit, section in (("SporeCannon", "spore_cannon"), ("SporeCrawler", "spore_crawler"), ("HybridUltraliskShackled", "cage_ultralisk")):
        candidates = [o for o in usable if o.kind == unit]
        if not candidates:
            raise SystemExit(f"treepath: no usable {unit}")
        picks[section] = max(candidates, key=lambda o: (len(outer_probes(o, every)), o.ident))
    return picks


def targets_galaxy(picks: dict[str, Obstacle], every: list[Obstacle]) -> str:
    lines = ["// Generated by scripts/testkit/profiles/treepath.py from the built map.", "void gf_TreePathTargets () {"]
    for section, target in picks.items():
        lines.append(f'    gf_TpBegin("{section}", "{target.ident}");')
        for i, (x, y) in enumerate(inner_probes(target)):
            lines.append(f'    gf_TpProbe("{section}", "in", {i}, {x:.3f}, {y:.3f});')
        for i, (x, y) in enumerate(outer_probes(target, every)):
            lines.append(f'    gf_TpProbe("{section}", "out", {i}, {x:.3f}, {y:.3f});')
        (sx, sy), (ex, ey) = walk(target, every)
        lines.append(f'    gf_TpWalk("{section}", {sx:.3f}, {sy:.3f}, {ex:.3f}, {ey:.3f});')
    lines.append("}")
    return "\n".join(lines) + "\n"


def map_spec() -> TestMapSpec:
    every = obstacles(BUILT)
    picks = pick_targets(every)
    for section, target in picks.items():
        print(
            f"treepath target {section}: {target.kind} id={target.ident} area={target.area:.2f}"
            f" centre=({target.centre[0]:.2f},{target.centre[1]:.2f})"
            f" in={len(inner_probes(target))} out={len(outer_probes(target, every))}"
        )
    TARGETS_GALAXY.parent.mkdir(parents=True, exist_ok=True)
    TARGETS_GALAXY.write_text(targets_galaxy(picks, every), encoding="utf-8")
    return TestMapSpec(
        profile="treepath",
        source=BUILT,
        output=PROFILE_OUTPUTS["treepath"],
        bank_names=PROFILE_BANKS["treepath"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "treepath.galaxy",
            TARGETS_GALAXY,
        ),
        galaxy_includes=(
            "scripts/test/treepath/common",
            "scripts/test/treepath/treepath",
            "scripts/test/treepath/treepath_targets",
        ),
        init_calls=("gt_TreePath_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    return


def parse_path(raw: dict) -> list[tuple[float, float]]:
    points = []
    for i in range(int(raw.get("pathCount") or 0)):
        value = raw.get(f"path{i:03d}")
        if isinstance(value, str) and "," in value:
            x, y = value.split(",")
            points.append((int(x) / 100, int(y) / 100))
    return points


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    checks.eq("meta", "", "realClicks", 0)
    every = obstacles(BUILT)
    by_id = {o.ident: o for o in every}
    for section in SECTIONS:
        raw = data.setdefault(section, {})
        target = by_id.get(str(raw.get("ident")))
        print(f"{section} raw: { {k: v for k, v in sorted(raw.items()) if not k.startswith('path')} }")
        if target is None:
            print(f"{section} target: missing FAIL")
            checks.failures += 1
            continue
        inner = [k for k in raw if k.startswith("in_")]
        outer = [k for k in raw if k.startswith("out_")]
        raw["innerCount"] = len(inner)
        raw["innerOpen"] = sum(1 for k in inner if raw[k])
        raw["outerCount"] = len(outer)
        raw["outerBlocked"] = sum(1 for k in outer if not raw[k])
        checks.gt(section, "", "innerCount", 0)
        checks.eq(section, "", "innerOpen", 0)
        checks.gt(section, "", "outerCount", 3)
        checks.eq(section, "", "outerBlocked", 0)
        checks.true(section, "", "moveIssued")
        checks.lt(section, "", "endDist10", 15)
        path = parse_path(raw)
        raw["pathPoints"] = len(path)
        depth = 0.0
        for x, y in path:
            if inside(target.polygon, x, y):
                depth = max(depth, edge_distance(target.polygon, x, y))
        raw["pathDepth100"] = round(depth * 100)
        checks.gt(section, "", "pathPoints", 10)
        checks.lt(section, "", "pathDepth100", round(HERO_SLACK * 100) + 1)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="treepath",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["treepath"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["treepath"],
        ready_section="meta",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
