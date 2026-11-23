"""Measure the hit volumes of every unit type into scripts/data/hit_volumes.json.

Unit types: every concrete CUnit of the stock melee and campaign data the
map depends on (resolve.STACK), and every type the map itself names
(units.py). For each: actor -> model -> m3 (resolve), then the model's
hit-test shapes at rest, scaled by the data scale (shapes). Models come
from the built map's Assets first (generated models), then from the game
storage. Each m3 file is read once, in a pool of worker processes.

The result is committed, so the build never reads the game install. Each
record keeps a key of the map's inputs (fresh.py); validate-map fails when
the map no longer gives that key. Re-run after a change to units, actors,
models, or scales:

    scripts/playtest.sh build
    cd scripts && uv run python -m hitvolumes.measure
    cd scripts && uv run python -m hitvolumes.galaxy
    cd scripts && uv run python -m hitvolumes.camera_heights

The build does not publish a map whose inputs differ from the measured
ones. After such a change, measure a staged map instead:

    uv run python scripts/expand_map.py --out <folder>
    cd scripts && uv run python -m hitvolumes.measure --map <folder>

usage (from scripts/): uv run python -m hitvolumes.measure [--print] [--map FOLDER] [--jobs N]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import NamedTuple

from project_root import project_root

sys.path.insert(0, str(project_root() / "scripts" / "hdtex"))

from casc import Casc

from .fresh import MapInputs
from .resolve import GameData, Resolution, stock_entries
from .shapes import model_shapes, reach
from .units import stock_unit_types, unit_types

ROOT = project_root()
MAP = ROOT / "out" / "SCOBA256.SC2Map"
HARNESS = ROOT / "scripts" / "testkit" / "galaxy"
OUT = ROOT / "scripts" / "data" / "hit_volumes.json"
VERSION = 2
# Paths per stormex extract call: under its regex state limit.
EXTRACT_BATCH = 100
SECTION_RE = re.compile(r"'([A-Z0-9_]{4}V\d+)'")
Vec3 = tuple[float, float, float]


class Clock:
    """Wall time of each phase, printed as it ends."""

    def __init__(self) -> None:
        self.start = self.last = time.perf_counter()

    def lap(self, phase: str, note: str = "") -> None:
        now = time.perf_counter()
        print(f"time {phase}: {now - self.last:.2f} s {note}".rstrip(), flush=True)
        self.last = now

    def total(self) -> None:
        print(f"time total: {time.perf_counter() - self.start:.2f} s", flush=True)


def casc_path(entry: str) -> str:
    return entry.replace("/", "\\").lower()


def suffix_index(stored: list[str]) -> dict[str, str]:
    """Every path suffix that starts after a backslash -> the stored path.
    Where several stored paths share a suffix, the first in sort order wins."""
    out: dict[str, str] = {}
    for full in sorted(stored):
        low = full.lower()
        for i, ch in enumerate(low):
            if ch == "\\":
                out.setdefault(low[i + 1:], full)
    return out


class Unreadable(NamedTuple):
    """An m3 file the reader cannot parse, and why."""

    reason: str


def file_shapes(task: tuple[str, list[Vec3]]) -> list[tuple[str, list]] | Unreadable:
    """Worker: one m3 file at each of its scales, or why it cannot be read.
    The reason lands in the unit's record and in the printed count."""
    path, scales = task
    try:
        return [model_shapes(Path(path), scale) for scale in scales]
    except Exception as error:  # m3addon raises bare Exception for unknown sections
        text = str(error)
        tags = sorted(set(SECTION_RE.findall(text)))
        # The reader prints a set: sort it, so every run writes the same JSON.
        return Unreadable(f"unknown m3 sections {', '.join(tags)}" if tags else f"{type(error).__name__}: {text}")


def shapes_by_file(files: dict[str, list[Vec3]], jobs: int) -> dict[tuple[str, Vec3], tuple[str, list] | Unreadable]:
    """(m3 path, scale) -> (source, shapes) or Unreadable. jobs 1 runs in this process."""
    tasks = sorted(files.items())
    if jobs <= 1:
        results = [file_shapes(t) for t in tasks]
    else:
        with ProcessPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(file_shapes, tasks, chunksize=4))
    out: dict[tuple[str, Vec3], tuple[str, list] | Unreadable] = {}
    for (path, scales), got in zip(tasks, results):
        for scale in scales:
            out[(path, scale)] = got if isinstance(got, Unreadable) else got[scales.index(scale)]
    return out


def none_record(res: Resolution, entry: str, reason: str) -> dict:
    """A resolved type without a volume: the reason, and what the key needs."""
    return {"source": "none", "reason": reason, "actor": res.actor, "model": res.model, "m3": entry,
            "files": res.files(), "actors": list(res.actors), "models": list(res.models)}


def record(res: Resolution, entry: str, source: str, shapes: list) -> dict:
    """entry: the m3 the shapes come from (the model path, or its first variation)."""
    xy, lo, hi = reach(shapes)
    return {
        "actor": res.actor,
        "model": res.model,
        "m3": entry,
        "files": res.files(),
        "actors": list(res.actors),
        "models": list(res.models),
        "scale": [round(s, 4) for s in res.scale],
        "actorScale": [round(s, 4) for s in res.actor_scale],
        "modelScale": [round(s, 4) for s in res.model_scale],
        "source": source,
        "reach": xy,
        "zmin": lo,
        "zmax": hi,
        "shapes": shapes,
    }


def measure(casc: Casc, scratch: Path, stock: Path, jobs: int, clock: Clock) -> dict:
    data = GameData(stock, MAP)
    inputs = MapInputs(MAP)
    names = sorted(set(unit_types(MAP, HARNESS)) | set(stock_unit_types(stock)))
    units: dict[str, dict] = {}
    resolved: dict[str, Resolution] = {}
    for unit in names:
        res = data.resolve(unit)
        if res is None:
            actor = data.actor_for(unit)
            if actor is None and unit in data.by_morph:
                reason = f"morph state drawn by actor {data.by_morph[unit]} in another pose"
            else:
                reason = "no actor or model file"
            units[unit] = {"source": "none", "reason": reason, "actors": list(data.actors.chain(actor)) if actor else []}
            continue
        resolved[unit] = res
    clock.lap("resolve", f"types={len(names)} resolved={len(resolved)}")
    # One listing of every stored m3: a pattern naming thousands of files
    # passes stormex's regex state limit.
    index = suffix_index(casc.find([".m3"]))
    chosen: dict[str, str] = {}  # unit -> the m3 entry it uses
    found: dict[str, str] = {}  # stock entry -> stored path
    for unit, res in resolved.items():
        for entry in res.files():
            if inputs.map_m3(entry) is not None:
                chosen[unit] = entry
                break
            if casc_path(entry) in index:
                chosen[unit] = entry
                found[entry] = index[casc_path(entry)]
                break
    clock.lap("find", f"types={len(resolved)} found={len(chosen)} stock files={len(found)}")
    extracted = casc.extract(sorted(set(found.values())), scratch / "models", batch=EXTRACT_BATCH, jobs=jobs)
    clock.lap("extract", f"files={len(extracted)}")
    paths: dict[str, Path] = {}
    files: dict[str, list[Vec3]] = {}
    for unit, res in sorted(resolved.items()):
        entry = chosen.get(unit)
        path = None if entry is None else (inputs.map_m3(entry) or extracted[found[entry]])
        if path is None:
            units[unit] = none_record(res, res.m3, f"model file not found: {' or '.join(res.files())}")
            continue
        paths[unit] = path
        scales = files.setdefault(str(path), [])
        if res.scale not in scales:
            scales.append(res.scale)
    shapes = shapes_by_file(files, jobs)
    clock.lap("shapes", f"files={len(files)} jobs={jobs}")
    unreadable = set()
    for unit, path in paths.items():
        res = resolved[unit]
        got = shapes[(str(path), res.scale)]
        if isinstance(got, Unreadable):
            unreadable.add(str(path))
            units[unit] = none_record(res, chosen[unit], f"m3 not readable: {got.reason}")
            continue
        units[unit] = record(res, chosen[unit], got[0], got[1])
    if unreadable:
        print(f"m3 not readable: {len(unreadable)} files; their unit types have source none", flush=True)
    for unit, rec in units.items():
        rec["inputs"] = inputs.key(unit, rec)
    clock.lap("keys")
    return {"version": VERSION, "units": dict(sorted(units.items()))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", action="store_true", help="print one line per unit type")
    parser.add_argument("--map", type=Path, help="measure this expanded map, not out/SCOBA256.SC2Map")
    parser.add_argument("--jobs", type=int, default=os.cpu_count() or 1, help="worker processes for the m3 files (1: none)")
    args = parser.parse_args()
    global MAP
    if args.map is not None:
        MAP = args.map.resolve()
    if not (MAP / "Base.SC2Data").is_dir():
        print(f"built map missing: {MAP}; run scripts/playtest.sh build", file=sys.stderr)
        return 1
    clock = Clock()
    casc = Casc()
    with tempfile.TemporaryDirectory(prefix="hvmeasure-") as tmp:
        scratch = Path(tmp)
        stock = scratch / "stock"
        # Not every stack member has every catalog.
        wanted = set(stock_entries())
        casc.extract([p for p in casc.find(sorted(wanted)) if p in wanted], stock)
        clock.lap("catalogs")
        result = measure(casc, scratch, stock, args.jobs, clock)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    clock.lap("write")
    if args.print:
        for unit, rec in sorted(result["units"].items()):
            print(f"{unit} source={rec['source']} shapes={len(rec.get('shapes', []))} reach={rec.get('reach')} z={rec.get('zmin')}..{rec.get('zmax')} {rec.get('reason', '')}")
    counts: dict[str, int] = {}
    for rec in result["units"].values():
        counts[rec["source"]] = counts.get(rec["source"], 0) + 1
    print(f"{OUT} units={len(result['units'])} sources={dict(sorted(counts.items()))}")
    clock.total()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
