#!/usr/bin/env python3
"""Print placed trees' feet-height mesh against their generated blocker, as text.

Each character is one 0.25 world unit square: '#' mesh and blocked, 'o' mesh
not blocked (clipping), '+' blocked without mesh, '.' open. 'X' marks the
placed origin. Rows run from +y (top) to -y.

usage (from scripts/): uv run python -m footprints.preview [--objects PATH] ID [ID ...]
                       uv run python -m footprints.preview --worst 10
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import numpy as np

from project_root import project_root
from mapgen.footprints.blocker import build_blocker
from mapgen.footprints.config import SAMPLES_PER_SUB, SUB
from mapgen.footprints.placement import tree_outlines
from mapgen.footprints.raster import mesh_samples
from mapgen.footprints.slices import feet_slices, load_slices, segments_world

ROOT = project_root()
DEFAULT_OBJECTS = ROOT / "out" / "SCOBA256.SC2Map" / "Objects"
TREE_BLOCK = re.compile(r'<ObjectDoodad\b[^>]*\bType="ZerusTree[^"]*"[^>]*>')


def blocks(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    found = {}
    for match in TREE_BLOCK.finditer(text):
        ident = re.search(r'\bId="(\d+)"', match.group(0))
        if ident:
            found[ident.group(1)] = match.group(0)
    return found


def spore_outlines(data: dict, objects: Path, unit: str) -> list:
    text = objects.read_text(encoding="utf-8")
    picked = re.sub(r'<ObjectUnit\b(?![^>]*UnitType="' + unit + r'")[^>]*>', "", text)
    outlines = []
    for match in re.finditer(r'<ObjectUnit\b[^>]*UnitType="' + unit + r'"[^>]*>', picked):
        block = match.group(0)
        scale = float(re.search(r'Scale="([^,]+)', block).group(1))
        angle = float(re.search(r'Rotation="([^"]+)"', block).group(1))
        for index in feet_slices(data, scale):
            outlines.append(segments_world(data["models"][unit]["0"][index], scale, angle))
    return outlines


def render(block: str, data: dict, outlines: list | None = None) -> str:
    outlines = outlines if outlines is not None else tree_outlines(data, block)
    blocker = build_blocker("preview", outlines)
    samples, x0, y0, rows, cols = mesh_samples(outlines)
    # Downsample samples to 0.25 squares (2x2 samples each).
    half = SAMPLES_PER_SUB // 2
    mesh = samples.reshape(rows * 2, half, cols * 2, half).mean(axis=(1, 3)) >= 0.5
    blocked = np.zeros_like(mesh)
    poly = np.asarray(blocker.polygon)
    step = SUB / 2
    for r in range(mesh.shape[0]):
        for c in range(mesh.shape[1]):
            px = x0 + (c + 0.5) * step
            py = y0 + (r + 0.5) * step
            blocked[r, c] = _inside(px, py, poly)
    lines = []
    ox = int((0 - x0) / step)
    oy = int((0 - y0) / step)
    for r in range(mesh.shape[0] - 1, -1, -1):
        row = ""
        for c in range(mesh.shape[1]):
            if r == oy and c == ox:
                row += "X"
            elif mesh[r, c] and blocked[r, c]:
                row += "#"
            elif mesh[r, c]:
                row += "o"
            elif blocked[r, c]:
                row += "+"
            else:
                row += "."
        lines.append(row)
    f = blocker.fit
    head = (
        f"mesh={f.mesh_area:.2f} blocked={f.blocked_area:.2f} covered={f.covered:.0%}"
        f" ratio={f.ratio:.2f} offset={f.offset:.2f} vertices={len(blocker.polygon)}"
    )
    return head + "\n" + "\n".join(lines)


def _inside(px: float, py: float, poly: np.ndarray) -> bool:
    hit = False
    count = len(poly)
    for i in range(count):
        x1, y1 = poly[i - 1]
        x2, y2 = poly[i]
        if (y1 > py) != (y2 > py) and px < x1 + (py - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--objects", type=Path, default=DEFAULT_OBJECTS)
    parser.add_argument("--worst", type=int, default=0, help="show the N trees with the lowest coverage")
    parser.add_argument("--unit", action="append", default=[], help="show a spore unit type's union blocker")
    parser.add_argument("ids", nargs="*")
    args = parser.parse_args()
    data = load_slices()
    for unit in args.unit:
        print(f"== {unit}")
        print(render("", data, spore_outlines(data, args.objects, unit)))
    if args.unit and not args.ids and not args.worst:
        return 0
    every = blocks(args.objects)
    ids = list(args.ids)
    if args.worst:
        scored = []
        for ident, block in every.items():
            fit = build_blocker(ident, tree_outlines(data, block)).fit
            scored.append((fit.covered, -fit.ratio, ident))
        ids += [ident for _, _, ident in sorted(scored)[: args.worst]]
        ratios = sorted(scored, key=lambda t: t[1])[: args.worst]
        ids += [ident for _, _, ident in ratios]
    if not ids:
        parser.error("give tree ids or --worst N")
    for ident in ids:
        if ident not in every:
            print(f"tree {ident}: not in {args.objects}", file=sys.stderr)
            return 1
        block = every[ident]
        print(f"== tree {ident} {re.search(r'Variation=\"(\d+)\"', block) and re.search(r'Variation=\"(\d+)\"', block).group(1)}"
              f" scale={re.search(r'Scale=\"([^,]+)', block).group(1)} rot={re.search(r'Rotation=\"([^\"]+)', block).group(1)}")
        print(render(block, data))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
