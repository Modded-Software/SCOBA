"""Measure the hit volumes of every map unit type into scripts/data/hit_volumes.json.

For each unit type: actor -> model -> m3 (resolve), then the model's
hit-test shapes at rest, scaled by the data scale (shapes). Models come
from the built map's Assets first (generated models), then from the game
storage. The result is committed, so the build never reads the game
install. Re-run after a change to units, actors, models, or scales:

    scripts/playtest.sh build
    cd scripts && uv run python -m hitvolumes.measure
    cd scripts && uv run python -m hitvolumes.galaxy

The build does not publish a map whose actor scales differ from the measured
ones. After a scale change, measure a staged map instead:

    uv run python scripts/expand_map.py --out <folder>
    cd scripts && uv run python -m hitvolumes.measure --map <folder>

usage (from scripts/): uv run python -m hitvolumes.measure [--print] [--map FOLDER]
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from project_root import project_root

sys.path.insert(0, str(project_root() / "scripts" / "hdtex"))

from casc import Casc

from .resolve import GameData, stock_entries
from .shapes import model_shapes, reach
from .units import unit_types

ROOT = project_root()
MAP = ROOT / "out" / "SCOBA256.SC2Map"
HARNESS = ROOT / "scripts" / "testkit" / "galaxy"
OUT = ROOT / "scripts" / "data" / "hit_volumes.json"
VERSION = 1


def map_model(entry: str) -> Path | None:
    """The m3 inside the built map, matched without regard to case."""
    want = entry.replace("\\", "/").lower()
    for path in MAP.rglob("*.m3"):
        if path.relative_to(MAP).as_posix().lower() == want:
            return path
    return None


def casc_path(entry: str) -> str:
    return entry.replace("/", "\\").lower()


def measure(casc: Casc, scratch: Path, stock: Path) -> dict:
    data = GameData(stock, MAP)
    units: dict[str, dict] = {}
    resolved = {}
    for unit in unit_types(MAP, HARNESS):
        res = data.resolve(unit)
        if res is None:
            units[unit] = {"source": "none", "reason": "no actor or model file"}
            continue
        resolved[unit] = res
    wanted = sorted({r.m3 for r in resolved.values() if map_model(r.m3) is None})
    stored = {p.lower(): p for p in casc.find([casc_path(m) for m in wanted])}
    found = {}
    for m in wanted:
        hits = [full for low, full in stored.items() if low.endswith(casc_path(m))]
        if hits:
            found[m] = sorted(hits)[0]
    files = casc.extract(sorted(set(found.values())), scratch / "models")
    for unit, res in sorted(resolved.items()):
        path = map_model(res.m3) or (files.get(found[res.m3]) if res.m3 in found else None)
        if path is None:
            units[unit] = {"source": "none", "reason": f"model file not found: {res.m3}", "actor": res.actor, "model": res.model}
            continue
        source, shapes = model_shapes(path, res.scale)
        xy, lo, hi = reach(shapes)
        units[unit] = {
            "actor": res.actor,
            "model": res.model,
            "m3": res.m3,
            "scale": [round(s, 4) for s in res.scale],
            "actorScale": [round(s, 4) for s in res.actor_scale],
            "modelScale": [round(s, 4) for s in res.model_scale],
            "source": source,
            "reach": xy,
            "zmin": lo,
            "zmax": hi,
            "shapes": shapes,
        }
    return {"version": VERSION, "units": units}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", action="store_true", help="print one line per unit type")
    parser.add_argument("--map", type=Path, help="measure this expanded map, not out/SCOBA256.SC2Map")
    args = parser.parse_args()
    global MAP
    if args.map is not None:
        MAP = args.map.resolve()
    if not (MAP / "Base.SC2Data").is_dir():
        print(f"built map missing: {MAP}; run scripts/playtest.sh build", file=sys.stderr)
        return 1
    casc = Casc()
    with tempfile.TemporaryDirectory(prefix="hvmeasure-") as tmp:
        scratch = Path(tmp)
        stock = scratch / "stock"
        # Not every stack member has every catalog.
        wanted = set(stock_entries())
        casc.extract([p for p in casc.find(sorted(wanted)) if p in wanted], stock)
        result = measure(casc, scratch, stock)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if args.print:
        for unit, rec in sorted(result["units"].items()):
            print(f"{unit} source={rec['source']} shapes={len(rec.get('shapes', []))} reach={rec.get('reach')} z={rec.get('zmin')}..{rec.get('zmax')} {rec.get('reason', '')}")
    print(f"{OUT} units={len(result['units'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
