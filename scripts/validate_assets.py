"""Control icon and build stamp checks for scripts/validate-map.py."""

from __future__ import annotations

import sys
from pathlib import Path

CONTROL_ICONS = [
    "SCOBAModeRPG.dds",
    "SCOBAModeActions.dds",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def check_control_icons(map_dir: Path) -> None:
    icon_dir = map_dir / "Assets" / "Textures"
    hashes = []
    for name in CONTROL_ICONS:
        path = icon_dir / name
        if not path.is_file():
            fail(f"missing control icon: {name}")
        data = path.read_bytes()
        if len(data) < 128 or data[:4] != b"DDS ":
            fail(f"invalid control icon: {name}")
        hashes.append(data)
    if hashes[0] == hashes[1]:
        fail("control mode icons must differ")


def check_stamp(map_dir: Path) -> None:
    stamp_path = map_dir / "BuildStamp.txt"
    if not stamp_path.is_file():
        fail("missing BuildStamp.txt")
    stamp = stamp_path.read_text(encoding="utf-8").strip()
    if not stamp:
        fail("empty BuildStamp.txt")
    stamp_file = (map_dir / "scripts" / "app" / "core" / "build_stamp.galaxy").read_text(encoding="utf-8", errors="replace")
    if f'const string c_SCOBA_BUILD_STAMP = "{stamp}";' not in stamp_file:
        fail("build_stamp.galaxy build stamp does not match BuildStamp.txt")
