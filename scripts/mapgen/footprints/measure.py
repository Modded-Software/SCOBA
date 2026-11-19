#!/usr/bin/env python3
"""Slice the models that footprints/ builds blockers for.

For each model file this cuts every mesh triangle with horizontal planes near
the ground and records the cut segments, in model space. A slice's segments
outline the mesh at that height; footprints/ fills the outline at the
height of a walking unit's feet, divided by each placed object's scale.

The result is written to scripts/data/footprint_slices.json and committed, so
the build never reads the game install. Re-run only when the models change.

usage (from scripts/): uv run python -m footprints.measure [--print]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from project_root import project_root

ROOT = project_root()
# The vendored m3addon is not a package; it is imported from its folder.
sys.path.insert(0, str(ROOT / "scripts" / "vendor" / "m3addon"))

import m3

STORMEX = ROOT / "tools" / "stormex"
SC2 = Path(
    os.environ.get(
        "SC2_INSTALL",
        str(Path.home() / "Games/battlenet-prefix/pfx/drive_c/Program Files (x86)/StarCraft II"),
    )
)
OUT = ROOT / "scripts" / "data" / "footprint_slices.json"
# Model group -> CASC path regex. The number in the file name is the variation.
MODELS = {
    "ZerusTree": r"assets.doodads.zerustree.zerustree_\d+\.m3$",
    "SporeCannon": r"assets.buildings.zerg.sporecannon.sporecannon\.m3$",
    "SporeCrawler": r"assets.buildings.zerg.sporecrawler.sporecrawler\.m3$",
}
# Model-space slice heights. Feet height (world 0.05-0.35) over the placed
# scales (2-8 trees, 3 spores) falls in 0.006-0.175.
SLICE_STEP = 0.0025
SLICE_COUNT = 80
DECIMALS = 4

Triangle = tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]


def triangles(path: Path) -> list[Triangle]:
    model = m3.loadModel(str(path))
    description = m3.structures["VertexFormat" + hex(model.vFlags)].getVersion(0)
    count = len(model.vertices) // description.size
    vertices = description.createInstances(buffer=model.vertices, count=count)
    points = [(v.position.x, v.position.y, v.position.z) for v in vertices]
    result: list[Triangle] = []
    for division in model.divisions:
        faces = division.faces
        for region in division.regions:
            start = region.firstFaceVertexIndexIndex
            for k in range(start, start + region.numberOfFaceVertexIndices, 3):
                a, b, c = (region.firstVertexIndex + faces[k + i] for i in range(3))
                result.append((points[a], points[b], points[c]))
    return result


def cut(triangle: Triangle, z: float) -> tuple[float, float, float, float] | None:
    """Segment where the plane at height z crosses the triangle, or None."""
    hits = []
    for i in range(3):
        p, q = triangle[i], triangle[(i + 1) % 3]
        if (p[2] - z) * (q[2] - z) < 0:
            t = (z - p[2]) / (q[2] - p[2])
            hits.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
    if len(hits) != 2:
        return None
    (x1, y1), (x2, y2) = hits
    return (round(x1, DECIMALS), round(y1, DECIMALS), round(x2, DECIMALS), round(y2, DECIMALS))


def slices(tris: list[Triangle]) -> list[list[list[float]]]:
    out = []
    for k in range(SLICE_COUNT):
        # Offset by a tiny amount so a plane never passes exactly through a vertex.
        z = (k + 1) * SLICE_STEP + 1e-7
        segments = [list(s) for t in tris if (s := cut(t, z)) is not None]
        out.append(segments)
    return out


def extract(pattern: str, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    cmd = [str(STORMEX), "-S", str(SC2), "-I", pattern, "-x", "-o", str(out)]
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit(f"stormex failed ({error.returncode}): {error.stderr.strip()}") from error
    return sorted(out.rglob("*.m3"), key=lambda p: p.name)


def variation_of(path: Path) -> int:
    match = re.search(r"_(\d+)\.m3$", path.name)
    return int(match.group(1)) if match else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print", action="store_true", help="print segment counts per model")
    args = parser.parse_args()
    data: dict = {"slice_step": SLICE_STEP, "slice_count": SLICE_COUNT, "models": {}}
    with tempfile.TemporaryDirectory(prefix="fpmeasure-") as scratch:
        for group, pattern in MODELS.items():
            files = extract(pattern, Path(scratch) / group)
            if not files:
                print(f"{group}: no model matched {pattern}", file=sys.stderr)
                return 1
            variations = {}
            for path in files:
                tris = triangles(path)
                cuts = slices(tris)
                variations[str(variation_of(path))] = cuts
                if args.print:
                    counts = [len(c) for c in cuts]
                    print(f"{group} {path.name} triangles={len(tris)} segments min={min(counts)} max={max(counts)}")
            data["models"][group] = variations
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
    print(f"{OUT} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
