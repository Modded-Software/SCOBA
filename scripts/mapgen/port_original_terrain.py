#!/usr/bin/env python3
"""Port editor terrain geometry from original/ into src/.

Copies t3HeightMap, t3SyncHeightMap, CellAttribute_Pnp (painted
pathing), t3Water (water bodies) and WaterData.xml (water types) from the
edited packed map and sets
the t3HeightMap vertData attributes (quantizeBias, quantizeScale,
standardHeight) in src/t3Terrain.xml. Nothing else in t3Terrain.xml changes.

Safety: the src/ copied files must equal the base map (original/ at
--base-rev), so no src/ terrain work is overwritten. The vertData line of
src/ must equal the base too. Otherwise the script stops with no write.
t3Water is compared by content: the editor rewrites stale pointer bytes
(record bytes 12-39) on every save, so only the header, the type name, the
flags and the rectangle count.

Run: PYTHONPATH=scripts uv run python -m mapgen.port_original_terrain --base-rev REV
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import mpyq

from project_root import project_root

ROOT = project_root()
SRC = ROOT / "src" / "SCOBA.SC2Map"
EDITED = ROOT / "original" / "SCOBA.SC2Map"
# Height mesh, plus the editor's painted pathing layer.
HEIGHT_FILES = ("t3HeightMap", "t3SyncHeightMap", "CellAttribute_Pnp")
# Water bodies and water types (operator, 2026-11-20).
WATER_FILES = ("t3Water", "Base.SC2Data/GameData/WaterData.xml")
COPY_FILES = HEIGHT_FILES + WATER_FILES
WATER_RECORD = 56
VERT_RE = re.compile(r'<vertData [^>]*name="t3HeightMap"[^>]*/>')


class Folder:
    """An unpacked map folder with the archive read_file interface."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def read_file(self, name: str) -> bytes | None:
        file = self.path / name.replace("\\", "/")
        return file.read_bytes() if file.is_file() else None


def open_map(path: Path) -> mpyq.MPQArchive | Folder:
    return Folder(path) if path.is_dir() else mpyq.MPQArchive(str(path))


def read(archive: mpyq.MPQArchive | Folder, name: str) -> bytes:
    data = archive.read_file(name if isinstance(archive, Folder) else name.replace("/", "\\"))
    if data is None:
        raise SystemExit(f"{name} missing from archive")
    return data


def water_key(data: bytes) -> tuple:
    """t3Water without the stale pointer bytes the editor writes."""
    if data[:4] != b"WATR":
        raise SystemExit("t3Water: bad magic")
    count = int.from_bytes(data[8:12], "little")
    if len(data) != 32 + count * WATER_RECORD:
        raise SystemExit(f"t3Water: size {len(data)} does not fit {count} records")
    recs = [data[32 + i * WATER_RECORD: 32 + (i + 1) * WATER_RECORD] for i in range(count)]
    return (data[:32],) + tuple(r[:12] + r[40:] for r in recs)


def same(name: str, a: bytes, b: bytes) -> bool:
    return water_key(a) == water_key(b) if name == "t3Water" else a == b


def vert_line(text: str, where: str) -> str:
    found = VERT_RE.findall(text)
    if len(found) != 1:
        raise SystemExit(f"{where}: expected one t3HeightMap vertData, found {len(found)}")
    return found[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--base-rev", help="git revision of original/ that src/ terrain was taken from")
    group.add_argument("--base", type=Path, help="base packed map or unpacked folder")
    parser.add_argument("--edited", type=Path, default=EDITED)
    parser.add_argument("--check", action="store_true", help="report only, write nothing")
    args = parser.parse_args()

    if args.base:
        base = open_map(args.base)
        args.base_rev = str(args.base)
    else:
        raw = subprocess.run(["git", "show", f"{args.base_rev}:original/SCOBA.SC2Map"], cwd=ROOT, check=True, capture_output=True).stdout
        base_path = Path("/tmp") / f"port_terrain_base_{args.base_rev}.SC2Map"
        base_path.write_bytes(raw)
        base = mpyq.MPQArchive(str(base_path))
    edited = open_map(args.edited)

    for name in COPY_FILES:
        have = (SRC / name).read_bytes()
        if not (same(name, have, read(base, name)) or same(name, have, read(edited, name))):
            raise SystemExit(f"src/{name} differs from base {args.base_rev} and from the edited map, refusing to overwrite")

    src_xml = (SRC / "t3Terrain.xml").read_bytes().decode("utf-8")
    src_vert = vert_line(src_xml, "src")
    base_vert = vert_line(read(base, "t3Terrain.xml").decode("utf-8"), "base")
    new_vert = vert_line(read(edited, "t3Terrain.xml").decode("utf-8"), "edited")
    if src_vert not in (base_vert, new_vert):
        raise SystemExit(f"src vertData differs from base:\n  src  {src_vert}\n  base {base_vert}")

    changed = [name for name in COPY_FILES if not same(name, read(edited, name), read(base, name))]
    print(f"files changed: {changed or 'none'}")
    print(f"vertData: {src_vert}\n      -> {new_vert}")
    if args.check:
        return 0

    for name in COPY_FILES:
        (SRC / name).write_bytes(read(edited, name))
    (SRC / "t3Terrain.xml").write_bytes(src_xml.replace(src_vert, new_vert, 1).encode("utf-8"))

    for name in COPY_FILES:
        if (SRC / name).read_bytes() != read(edited, name):
            raise SystemExit(f"src/{name} write check failed")
    if vert_line((SRC / "t3Terrain.xml").read_text(encoding="utf-8"), "result") != new_vert:
        raise SystemExit("vertData write check failed")
    print("wrote src/ terrain geometry, pathing and water")
    return 0


if __name__ == "__main__":
    sys.exit(main())
