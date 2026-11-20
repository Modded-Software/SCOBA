#!/usr/bin/env python3
"""Measure the models the water features are built from.

Reads the models the built map shows (its ModelData and Assets) and writes
scripts/data/water_models.json, in model space:

- falls: per water doodad type and variation, the mesh bounds, the height
  of the water surface the model was made for (its splash emitters), and
  where its streams land.
- rocks: per rock doodad type and variation, the mesh bounds. These models
  are read from the game storage (stormex): the map has no copy of a
  doodad it does not place yet.
- pipes: per pipe unit, every tube of the mesh: the mouth (outer end of the
  axis, x and y), the lip and the top of the mouth opening (lowest and
  highest mesh point of the outer end), the outward direction on the ground
  plane, the radius and the length.

The result is committed, so the build never reads the models. Re-run after
a change to these models or to their ModelData scale.

usage: PYTHONPATH=scripts uv run python -m mapgen.waterfeatures.measure [--print]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TypedDict

import numpy as np

from project_root import project_root

ROOT = project_root()
sys.path.insert(0, str(ROOT / "scripts" / "vendor" / "m3addon"))

import m3

from hitvolumes.dump_m3_bounds import bone_rest
from mapgen.footprints.measure import triangles

from . import config

BUILT = ROOT / "out" / "SCOBA256.SC2Map"
OUT = ROOT / "scripts" / "data" / "water_models.json"
DECIMALS = 4
# A tube: a welded mesh part that is long, thin and close to level.
TUBE_MIN_LENGTH = 4.0
TUBE_MAX_SPREAD = 0.5  # standard deviation across the axis
TUBE_MAX_TILT = 0.2  # |axis z|
TUBE_END_SHARE = 0.1  # this share of the length, at the outer end, is the mouth


def model_entry(map_dir: Path, ident: str) -> tuple[Path, float]:
    """(model file in the map, ModelData scale) of one CModel of the built map."""
    text = (map_dir / "Base.SC2Data" / "GameData" / "ModelData.xml").read_text(encoding="utf-8")
    match = re.search(rf'<CModel id="{re.escape(ident)}"[^>]*>(.*?)</CModel>', text, re.S)
    if match is None:
        raise SystemExit(f"{ident}: no CModel in the built map")
    model = re.search(r'<Model value="([^"]+)"', match.group(1))
    if model is None:
        raise SystemExit(f"{ident}: the CModel of the built map names no model file")
    path = map_dir / model.group(1).replace("\\", "/")
    scale = re.search(r'<ScaleMax value="([^",]+)', match.group(1))
    return path, float(scale.group(1)) if scale else 1.0


def variation_files(path: Path) -> dict[int, Path]:
    """The model file, or its numbered variations (name_00.m3, name_01.m3, ...)."""
    if path.is_file():
        return {0: path}
    found = sorted(path.parent.glob(f"{path.stem}_[0-9][0-9]{path.suffix}"))
    if not found:
        raise SystemExit(f"{path}: no model file and no numbered variation")
    return {int(p.stem.rsplit("_", 1)[1]): p for p in found}


def fall(path: Path) -> dict:
    """Bounds, design water surface and stream landing points of one fall model."""
    points = np.array(triangles(path)).reshape(-1, 3)
    model = m3.loadModel(str(path))
    splashes = [bone_rest(model, i) for i, bone in enumerate(model.bones) if "splash" in bone.name.lower()]
    if not splashes:
        raise SystemExit(f"{path.name}: no splash emitter, the water surface is unknown")
    return {
        "min": [round(float(v), DECIMALS) for v in points.min(axis=0)],
        "max": [round(float(v), DECIMALS) for v in points.max(axis=0)],
        "base_z": round(float(np.mean([p[2] for p in splashes])), DECIMALS),
        "splashes": [[round(p[0], DECIMALS), round(p[1], DECIMALS)] for p in splashes],
    }


def parts(tris: np.ndarray) -> list[np.ndarray]:
    """Unique points of every welded part of a triangle soup."""
    keys: dict[tuple, int] = {}
    ids = np.empty((len(tris), 3), dtype=int)
    for i, tri in enumerate(tris):
        for j, p in enumerate(tri):
            ids[i, j] = keys.setdefault(tuple(np.round(p, 3)), len(keys))
    parent = list(range(len(keys)))

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for a, b, c in ids:
        parent[find(b)] = find(a)
        parent[find(c)] = find(a)
    groups: dict[int, list[int]] = {}
    for i, (a, _, _) in enumerate(ids):
        groups.setdefault(find(a), []).append(i)
    return [np.unique(tris[members].reshape(-1, 3), axis=0) for members in groups.values()]


class TubeRow(TypedDict):
    """One measured tube, as written to the models file."""

    mouth: list[float]
    lip_z: float
    top_z: float
    dir: list[float]
    radius: float
    length: float


def tube(points: np.ndarray) -> TubeRow | None:
    """Mouth, outward direction, radius and length of a part, or None when it is no tube."""
    centre = points.mean(axis=0)
    values, vectors = np.linalg.eigh(np.cov((points - centre).T))
    axis = vectors[:, 2]
    along = (points - centre) @ axis
    length = float(along.max() - along.min())
    if length < TUBE_MIN_LENGTH or abs(axis[2]) > TUBE_MAX_TILT or np.sqrt(values[1]) > TUBE_MAX_SPREAD:
        return None
    # Outward: away from the model origin, on the ground plane.
    if np.linalg.norm(centre[:2] + axis[:2]) < np.linalg.norm(centre[:2]):
        axis, along = -axis, -along
    mouth = centre + axis * along.max()
    # The mouth opening: the mesh points of the outer end. Its lowest point
    # is the lip the water leaves over, its highest the top of the opening.
    end = points[along > along.max() - TUBE_END_SHARE * length]
    lip, top = float(end[:, 2].min()), float(end[:, 2].max())
    flat = axis[:2] / np.linalg.norm(axis[:2])
    return {
        "mouth": [round(float(v), DECIMALS) for v in mouth[:2]],
        "lip_z": round(lip, DECIMALS),
        "top_z": round(top, DECIMALS),
        "dir": [round(float(v), DECIMALS) for v in flat],
        "radius": round((top - lip) / 2, DECIMALS),
        "length": round(length, DECIMALS),
    }


def tubes(path: Path) -> list[TubeRow]:
    found = [t for t in (tube(p) for p in parts(np.array(triangles(path)))) if t is not None]
    return sorted(found, key=lambda t: (t["mouth"][0], t["mouth"][1]))


def stock_files(kind: str, work: Path) -> dict[int, Path]:
    """The numbered variations of a stock doodad model, from the game storage.

    A doodad the map does not place yet has no CModel in the built map. Its
    model is the game's: Assets\\Doodads\\<id>\\<id>_NN.m3.
    """
    from hdtex.casc import Casc

    casc = Casc()
    stem = kind.lower()
    stored = [p for p in casc.find([f"\\assets\\doodads\\{stem}\\{stem}_{v:02d}.m3" for v in range(100)])]
    if not stored:
        raise SystemExit(f"{kind}: no model in the game storage")
    files = casc.extract(stored, work)
    return {int(Path(p.replace("\\", "/")).stem.rsplit("_", 1)[1]): f for p, f in files.items()}


def rock(path: Path) -> dict:
    """Bounds of one rock model."""
    points = np.array(triangles(path)).reshape(-1, 3)
    return {
        "min": [round(float(v), DECIMALS) for v in points.min(axis=0)],
        "max": [round(float(v), DECIMALS) for v in points.max(axis=0)],
    }


def measure(map_dir: Path, work: Path | None = None) -> dict:
    data: dict = {"falls": {}, "pipes": {}, "rocks": {}}
    files = stock_files(config.ROCK_TYPE, work or ROOT / "out" / "testkit" / "water_models")
    data["rocks"][config.ROCK_TYPE] = {str(v): rock(p) for v, p in sorted(files.items())}
    for kind in (config.FALL_TYPE,):
        path, scale = model_entry(map_dir, kind)
        if scale != 1.0:
            raise SystemExit(f"{kind}: ModelData scale {scale}; the placement rules assume 1")
        data["falls"][kind] = {str(v): fall(p) for v, p in sorted(variation_files(path).items())}
    for unit, ident in sorted(config.PIPE_UNITS.items()):
        path, scale = model_entry(map_dir, ident)
        found = tubes(path)
        if not found:
            raise SystemExit(f"{unit}: no tube found in {path.name}")
        data["pipes"][ident] = {"model_scale": scale, "tubes": found}
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=BUILT, help="built map folder")
    parser.add_argument("--print", action="store_true", help="print what was measured")
    args = parser.parse_args()
    data = measure(args.map)
    if args.print:
        for kind, variations in data["falls"].items():
            for v, f in variations.items():
                print(f"{kind} {v}: min={f['min']} max={f['max']} base_z={f['base_z']} splashes={len(f['splashes'])}")
        for kind, variations in data["rocks"].items():
            for v, r in variations.items():
                print(f"{kind} {v}: min={r['min']} max={r['max']}")
        for ident, pipe in data["pipes"].items():
            for t in pipe["tubes"]:
                print(f"{ident} x{pipe['model_scale']}: mouth={t['mouth']} lip_z={t['lip_z']} top_z={t['top_z']} dir={t['dir']} radius={t['radius']} length={t['length']}")
    OUT.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{OUT} bytes={OUT.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
