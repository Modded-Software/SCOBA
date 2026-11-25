"""Probe: does the engine rotate a placed doodad's footprint?

The profile map gets placed doodads with lopsided test footprints at several
rotations, in open spots far from other objects, plus one control spot with
no doodad. The harness samples ground pathing on a 0.5 grid around each spot.
Raw grids are the output; the checks only assert the run is valid and that
the probe saw the footprint at all.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import workpaths
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, profile_output
from .treepath import obstacles

ROOT = project_root()


def built():
    return workpaths.path("SC2_BUILT_MAP")


# Written by a scan run (no file yet): spots whose probe grid is fully open in game.
OPEN_SPOTS = ROOT / "scripts" / "data" / "fprot_open_spots.json"
# Run 20261115-132159 found: Place cells without a Shape block nothing; the
# Shape blocks; 30 and 45 act as 0, 90 and 180 rotate. This set finds the
# snap rule, whether a concave Shape keeps its notch, and whether Scale scales it.
# Run 20261115-132312 found: rotation snaps to the nearest 90 (ties down),
# concave Shapes keep their notch, Scale does not scale the Shape.
# "offset" places the triangle at a fractional position (+0.25, +0.75).
CASES = {
    "shape": (0, 60, 100, 135, 225, 270, 315),
    "concave": (0, 90),
    "scaled": (0,),
    "offset": (0,),
}
OFFSET = (0.25, 0.75)
KINDS = tuple(CASES)
ROTATIONS = tuple(r for rs in CASES.values() for r in rs)
SCALED_SCALE = 2.0
SPOT_CLEARANCE = 8.0
GRID_HALF = 4.0
GRID_STEP = 0.5

# Concave L Shape: arm along +x (y -1..0, x -1..3) and arm along +y (x -1..0, y -1..3).
CONCAVE_FOOTPRINT = """    <CFootprint id="FpProbeConcave">
        <Layers index="Check">
            <Rows value="xx"/>
            <Rows value="xx"/>
        </Layers>
        <Layers index="Place">
            <Rows value="xx"/>
            <Rows value="xx"/>
        </Layers>
        <Shape>
            <Radius value="4.3"/>
            <Offsets value="-1,-1;-1,3;0,3;0,0;3,0;3,-1"/>
            <Borders value="5,0,2;0,1,2;1,2,2;2,3,2;3,4,2;4,5,2"/>
        </Shape>
    </CFootprint>
"""
# One centre-ish cell plus a long triangle Shape reaching to +x.
SHAPE_FOOTPRINT = """    <CFootprint id="FpProbeShape">
        <Layers index="Check">
            <Rows value="xx"/>
            <Rows value="xx"/>
        </Layers>
        <Layers index="Place">
            <Rows value="xx"/>
            <Rows value="xx"/>
        </Layers>
        <Shape>
            <Radius value="3.2"/>
            <Offsets value="-1,-1;-1,1;3,0"/>
            <Borders value="2,0,2;0,1,2;1,2,2"/>
        </Shape>
    </CFootprint>
"""


ACTOR_OF = {"shape": "Shape", "concave": "Concave", "scaled": "Shape", "offset": "Shape"}


def actor_xml(name: str) -> str:
    return (
        f'    <CActorDoodad id="FpProbe{name}Doodad" parent="ZerusTree">\n'
        f'        <Model value="ZerusTree"/>\n'
        f'        <Footprint value="FpProbe{name}"/>\n'
        f"    </CActorDoodad>\n"
    )


def candidate_spots(map_dir: Path | None = None) -> list[tuple[float, float]]:
    """Spots far from every placed object. Terrain may still block them."""
    map_dir = map_dir or built()
    every = obstacles(map_dir)
    spots: list[tuple[float, float]] = []
    for y in range(24, 233, 4):
        for x in range(24, 233, 4):
            near = any(math.hypot(o.x - x, o.y - y) - o.radius < SPOT_CLEARANCE for o in every)
            near = near or any(math.hypot(sx - x, sy - y) < SPOT_CLEARANCE for sx, sy in spots)
            if not near:
                spots.append((float(x), float(y)))
    return spots


def scan_mode() -> bool:
    """Scan run: no doodads; find candidate spots whose grid is fully open in game."""
    return not OPEN_SPOTS.exists()


def cases() -> list[tuple[str, str | None, int, tuple[float, float]]]:
    if scan_mode():
        return [(f"scan{i:03d}", None, 0, spot) for i, spot in enumerate(candidate_spots())]
    spots = [tuple(s) for s in json.loads(OPEN_SPOTS.read_text(encoding="utf-8"))["spots"]]
    names = [(f"{k}_r{r:03d}", k, r) for k, rotations in CASES.items() for r in rotations] + [("control", None, 0)]
    if len(spots) < len(names):
        raise SystemExit(f"fprot: {OPEN_SPOTS} has {len(spots)} open spots, need {len(names)}")
    return [(n, k, r, s) for (n, k, r), s in zip(names, spots)]


def patch(map_dir: Path) -> None:
    game = map_dir / "Base.SC2Data" / "GameData"
    fp = game / "FootprintData.xml"
    text = fp.read_text(encoding="utf-8")
    fp.write_text(text.replace("</Catalog>", CONCAVE_FOOTPRINT + SHAPE_FOOTPRINT + "</Catalog>", 1), encoding="utf-8")
    actors = game / "ActorData.xml"
    text = actors.read_text(encoding="utf-8")
    actors.write_text(text.replace("</Catalog>", actor_xml("Shape") + actor_xml("Concave") + "</Catalog>", 1), encoding="utf-8")
    objects = map_dir / "Objects"
    text = objects.read_text(encoding="utf-8")
    if "</PlacedObjects>" not in text:
        raise SystemExit("fprot: Objects has no </PlacedObjects>")
    entries = []
    lines = ["// Generated by scripts/testkit/profiles/fprot.py.", "void gf_FpRotSpots () {"]
    for index, (section, kind, rotation, (x, y)) in enumerate(cases()):
        if kind is not None:
            scale = SCALED_SCALE if kind == "scaled" else 1.0
            px, py = (x + OFFSET[0], y + OFFSET[1]) if kind == "offset" else (x, y)
            entries.append(
                f'    <ObjectDoodad Id="{2100000000 + index}" Position="{px:g},{py:g},0"'
                f' Rotation="{math.radians(rotation):.6f}" Scale="{scale:g},{scale:g},{scale:g}"'
                f' Type="FpProbe{ACTOR_OF[kind]}Doodad"/>\n'
            )
        lines.append(f'    gf_FpRotCase("{section}", {x:.1f}, {y:.1f}, {rotation});')
    lines.append("}")
    objects.write_text(text.replace("</PlacedObjects>", "".join(entries) + "</PlacedObjects>", 1), encoding="utf-8")
    harness = map_dir / "scripts" / "test" / "fprot"
    harness.mkdir(parents=True, exist_ok=True)
    (harness / "fprot_spots.galaxy").write_text("\n".join(lines) + "\n", encoding="utf-8")


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="fprot",
        source=built(),
        output=profile_output("fprot"),
        bank_names=PROFILE_BANKS["fprot"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "fprot.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/fprot/common",
            "scripts/test/fprot/fprot",
            "scripts/test/fprot/fprot_spots",
        ),
        init_calls=("gt_FpRot_Init();",),
        patch=patch,
    )


def on_ready(ctx, data: dict) -> None:
    return


def grid(raw: dict) -> list[str]:
    rows = []
    for j in range(int(GRID_HALF * 2 / GRID_STEP) + 1):
        rows.append(raw.get(f"row{j:02d}", "?"))
    return rows


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    checks.eq("meta", "", "realClicks", 0)
    if scan_mode():
        open_spots = []
        for section, _, _, spot in cases():
            rows = grid(data.get(section, {}))
            if all(set(row) == {"."} for row in rows):
                open_spots.append(list(spot))
        print(f"fprot scan: {len(open_spots)} fully open spots of {len(cases())}")
        OPEN_SPOTS.parent.mkdir(parents=True, exist_ok=True)
        OPEN_SPOTS.write_text(json.dumps({"spots": open_spots}, indent=1) + "\n", encoding="utf-8")
        data.setdefault("meta", {})["openSpots"] = len(open_spots)
        checks.gt("meta", "", "openSpots", len(ROTATIONS) * len(KINDS))
        return
    for section, kind, rotation, _ in cases():
        raw = data.get(section, {})
        rows = grid(raw)
        blocked = sum(row.count("#") for row in rows)
        print(f"{section} kind={kind} rot={rotation} blocked={blocked} (rows top=+y, cols left=-x, step {GRID_STEP})")
        for row in rows:
            print(f"    {row}")
        raw["blocked"] = blocked
        if kind is None:
            checks.eq(section, "", "blocked", 0)
        else:
            checks.gt(section, "", "blocked", 0)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="fprot",
        map_name="SCOBA.SC2Map",
        map_source=profile_output("fprot"),
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["fprot"],
        ready_section="meta",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
