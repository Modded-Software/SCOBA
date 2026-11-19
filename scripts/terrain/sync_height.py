"""Engine ground height for the 256 map: t3SyncHeightMap from the render mesh.

Until now the build dropped t3SyncHeightMap, so the engine ground was flat
(SPEC-BASE-AI F, run 20261118-145950): hills were visual only, units and
flyers ignored them. This bakes a sync map whose heights are the render
ground (t3HeightMap, calibrated to absolute z as flora/terrain.py does).

Layout (measured on the editor's 129 map, HEAD src): 64-byte header
("SMAP", 102, width, height, ...), then one 4-byte record per vertex, row
by row: u16 height, u16 1. The editor's heights fit 256 x render z - 479
(corr 0.997): 1/256 units. The old expand_sync_heightmap read it as a u16
grid plus two byte grids; the engine then read garbage (ground run
20261119-140729: fit 0.14 x render).

Encoding: height = round(z * SYNC_UNITS + SYNC_BIAS); confirmed in game by
the `ground` profile.

On by default. SC2_SYNC_HEIGHT=0 at build time keeps the flat ground.
"""

from __future__ import annotations

import os
import struct
from pathlib import Path

import numpy as np

from flora import config as flora_config
from flora.terrain import _offset, _scale, _vertices, bilinear

SYNC_UNITS = 256.0
SYNC_BIAS = 0.0
NEW_VERTS = 257
ENV = "SC2_SYNC_HEIGHT"


def enabled() -> bool:
    return os.environ.get(ENV) != "0"


def vertex_z(map_dir: Path) -> np.ndarray:
    """Absolute render ground z per heightmap vertex, [y, x]."""
    map_dir = Path(map_dir)
    raw = _vertices(map_dir)
    scale = _scale(map_dir)
    lifted = flora_config.DOODAD_LIFT if (map_dir / ".doodads_lifted").exists() else 0.0
    sunk = (map_dir / ".trees_sunk").exists()
    return raw * scale + _offset(raw, scale, (map_dir / "Objects").read_text(encoding="utf-8"), sunk) - lifted


def ground_at(grid: np.ndarray, x: float, y: float) -> float:
    """Render ground at a world point: bilinear over vertices (vertex = integer coords)."""
    return bilinear(grid, x, y)


def encode(z: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(z * SYNC_UNITS + SYNC_BIAS), 0, 65535).astype("<u2")


def decode(primary: np.ndarray) -> np.ndarray:
    return (primary.astype(float) - SYNC_BIAS) / SYNC_UNITS


def heights_of(data: bytes) -> np.ndarray:
    """The u16 heights of an SMAP, [y, x]."""
    _m, _v, sx, sy = struct.unpack_from("<4sIII", data, 0)
    return np.frombuffer(data, dtype="<u2", offset=64, count=sx * sy * 2).reshape(sy, sx, 2)[..., 0]


def render(src_sync: bytes, z: np.ndarray) -> bytes:
    """The 257 SMAP: source header, one (height, 1) record per vertex."""
    magic, version, sx, sy = struct.unpack_from("<4sIII", src_sync, 0)
    if magic != b"SMAP":
        raise ValueError("source t3SyncHeightMap is not SMAP")
    if len(src_sync) != 64 + 4 * sx * sy:
        raise ValueError("source t3SyncHeightMap is not one 4-byte record per vertex")
    if z.shape != (NEW_VERTS, NEW_VERTS):
        raise ValueError(f"heights are {z.shape}, want {NEW_VERTS}x{NEW_VERTS}")
    out = bytearray(src_sync[:64])
    struct.pack_into("<4sIII", out, 0, magic, version, NEW_VERTS, NEW_VERTS)
    records = np.empty((NEW_VERTS, NEW_VERTS, 2), dtype="<u2")
    records[..., 0] = encode(z)
    records[..., 1] = 1
    return bytes(out) + records.tobytes()


def bake(src_map: Path, dst_map: Path) -> None:
    data = render((Path(src_map) / "t3SyncHeightMap").read_bytes(), vertex_z(dst_map))
    (Path(dst_map) / "t3SyncHeightMap").write_bytes(data)
    print(f"sync height baked: {dst_map / 't3SyncHeightMap'} ({len(data)} bytes)")


def problems(map_dir: Path) -> list[str]:
    """validate-map: present and equal to the render ground when enabled, absent otherwise."""
    path = Path(map_dir) / "t3SyncHeightMap"
    if not enabled():
        return ["t3SyncHeightMap must not exist for the 256 map"] if path.exists() else []
    if not path.exists():
        return ["t3SyncHeightMap is missing (real ground is on by default)"]
    data = path.read_bytes()
    magic, _v, sx, sy = struct.unpack_from("<4sIII", data, 0)
    if magic != b"SMAP" or (sx, sy) != (NEW_VERTS, NEW_VERTS) or len(data) != 64 + 4 * sx * sy:
        return [f"t3SyncHeightMap is not SMAP {NEW_VERTS}x{NEW_VERTS}"]
    if not np.array_equal(heights_of(data), encode(vertex_z(map_dir))):
        return ["t3SyncHeightMap differs from the render ground"]
    return []
