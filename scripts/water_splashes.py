#!/usr/bin/env python3
"""Add missing water terrain squibs to map unit actors."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

from project_root import project_root

ROOT = project_root()
DEFAULT_MAP = ROOT / "out" / "SCOBA256.SC2Map"
ACTOR_DATA = Path("Base.SC2Data") / "GameData" / "ActorData.xml"
PRELOAD_DB = Path("PreloadAssetDB.txt")
MACRO = '<Macros value="TerrainSquibAnimations"/>'
SQUIBS = """        <TerrainSquibs>
            <MovementDistance value="0.150000,0.150000"/>
            <IdlePeriod value="0.100000,0.250000"/>
            <RangeUp value="0.600000"/>
            <RangeDown value="0.600000"/>
            <AttachQuery Methods="AMFilterCenter"/>
            <Visuals TerrainPhysicsMaterial="Water" ActorModel="TerrainSquibHarnessContinuous" ModelLink="WaterRippleSmall"/>
        </TerrainSquibs>"""

# Ground units without a map actor override still need a water-squib block.
EXTRA_GROUND_UNITS = {
    "HybridUltraliskShackled",
    "InfestedSiegeBreaker",
    "InfestorBurrowed",
}

# Buildings, air units, drop pods, and weapons do not need walking ripples.
NON_SPLASH_ACTORS = {
    "Armory",
    "AutoTurret",
    "Banshee",
    "Barracks",
    "BarracksTechLab",
    "Battlecruiser",
    "Bunker",
    "CommandCenter",
    "DukesRevenge",
    "EngineeringBay",
    "Factory",
    "FactoryTechLab",
    "GreaterNydusWorm",
    "Hive",
    "InfestedColonistShip",
    "KorhalPalaceTurret",
    "Kraith",
    "LaserDrillTripod",
    "MengskBC",
    "MercCompound",
    "Mothership",
    "NydusCanal",
    "Overlord",
    "Overseer",
    "PerditionTurret",
    "PerditionTurretUnderground",
    "SensorTower",
    "SpineCrawler",
    "SporeCannon",
    "SporeCrawler",
    "SupplyDepot",
    "TerranDropPod",
    "VikingFighter",
    "WarpPrismPhasing",
    "ZergDropPod",
}

ACTOR_RE = re.compile(
    r'(<CActorUnit\b[^>]*\bid="([^"]+)"[^>]*>)(.*?)(</CActorUnit>)',
    re.S,
)


def load_preload_units(path: Path) -> dict[str, dict[str, list[str] | str]]:
    units: dict[str, dict[str, list[str] | str]] = {}
    text = path.read_text(encoding="utf-8")
    for block in re.split(r"(?=^id=)", text, flags=re.M):
        if not block.startswith("id=") or "\npath=" not in block:
            continue
        unit_id = block.splitlines()[0][3:].strip()
        info: dict[str, list[str] | str] = {"actor": [], "model": ""}
        for line in block.splitlines():
            if line.startswith("Actor="):
                info["actor"] = line[6:].split(",")
            elif line.startswith("Model="):
                info["model"] = line[6:]
        units[unit_id] = info
    return units


def actor_status(map_dir: Path) -> dict[str, bool]:
    units = load_preload_units(Path(map_dir) / PRELOAD_DB)
    status: dict[str, bool] = {}
    for unit_id, info in units.items():
        actors = info["actor"]
        has_squib = "TerrainSquibHarnessContinuous" in actors
        status[unit_id] = status.get(unit_id, False) or has_squib
        for actor in actors:
            if actor == "##id##":
                actor = unit_id
            status[actor] = status.get(actor, False) or has_squib
    return status


def audit_actors(map_dir: Path) -> tuple[list[str], list[str], list[str]]:
    text = (Path(map_dir) / ACTOR_DATA).read_text(encoding="utf-8")
    inherited = actor_status(map_dir)
    ok: list[str] = []
    missing: list[str] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for match in ACTOR_RE.finditer(text):
        actor_id = match.group(2)
        seen.add(actor_id)
        body = match.group(3)
        if "<TerrainSquibs>" in body or inherited.get(actor_id, False):
            ok.append(actor_id)
        elif actor_id in NON_SPLASH_ACTORS:
            skipped.append(actor_id)
        else:
            missing.append(actor_id)
    for actor_id in sorted(EXTRA_GROUND_UNITS - seen):
        if inherited.get(actor_id, False):
            ok.append(actor_id)
        else:
            missing.append(actor_id)
    return sorted(ok), sorted(missing), sorted(skipped)


def apply(map_dir: Path) -> int:
    path = Path(map_dir) / ACTOR_DATA
    text = path.read_text(encoding="utf-8")
    inherited = actor_status(map_dir)
    changed = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal changed
        actor_id = match.group(2)
        body = match.group(3)
        if (
            actor_id in NON_SPLASH_ACTORS
            or "<TerrainSquibs>" in body
            or inherited.get(actor_id, False)
        ):
            return match.group(0)
        body = body.rstrip()
        if "TerrainSquibAnimations" not in body:
            body += "\n        " + MACRO
        body += "\n" + SQUIBS
        changed += 1
        return match.group(1) + body + "\n    " + match.group(4)

    text = ACTOR_RE.sub(repl, text)
    seen = {match.group(2) for match in ACTOR_RE.finditer(text)}
    for actor_id in sorted(EXTRA_GROUND_UNITS - seen):
        if inherited.get(actor_id, False):
            continue
        block = (
            f'\n    <CActorUnit id="{actor_id}">\n'
            f"        {MACRO}\n"
            f"{SQUIBS}\n"
            f"    </CActorUnit>"
        )
        text = text.replace("</Catalog>", block + "\n</Catalog>", 1)
        changed += 1
    if changed:
        path.write_text(text, encoding="utf-8")
    return changed


def revert() -> int:
    env = {**os.environ, "SC2_NO_WATER_SPLASHES": "1"}
    return subprocess.call([sys.executable, str(ROOT / "scripts" / "expand_map.py")], env=env)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    parser.add_argument("--revert", action="store_true")
    args = parser.parse_args(argv[1:])
    if args.revert:
        return revert()
    changed = apply(args.map)
    print(f"patched {changed} unit actors for water splashes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))