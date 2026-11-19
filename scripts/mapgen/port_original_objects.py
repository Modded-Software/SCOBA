#!/usr/bin/env python3
"""Port editor changes to placed objects from original/ into src/.

Compares the Objects file of two packed maps: the base (default: original/
as committed at HEAD) and the edited map (default: original/SCOBA.SC2Map).
Objects are matched by Id. Removed objects are deleted from src/Objects and
changed Position attributes are copied. Every other kind of change, and any
src/ object that does not match the base, stops the script with no write.

Run: PYTHONPATH=scripts uv run python -m mapgen.port_original_objects
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import mpyq

from project_root import project_root

ROOT = project_root()
SRC_OBJECTS = ROOT / "src" / "SCOBA.SC2Map" / "Objects"
EDITED = ROOT / "original" / "SCOBA.SC2Map"
PORTABLE = {"Position"}


def objects_from_archive(path: Path) -> dict[str, ET.Element]:
    data = mpyq.MPQArchive(str(path)).read_file("Objects")
    if data is None:
        raise SystemExit(f"no Objects in {path}")
    return {el.get("Id"): el for el in ET.fromstring(data)}


def base_from_git(rev: str) -> Path:
    out = subprocess.run(["git", "show", f"{rev}:original/SCOBA.SC2Map"], cwd=ROOT, check=True, capture_output=True).stdout
    tmp = Path(tempfile.mkdtemp(prefix="port_objects_")) / "base.SC2Map"
    tmp.write_bytes(out)
    return tmp


def element_span(text: str, oid: str) -> tuple[int, int]:
    """Span of the element with this Id, including its indent and line end."""
    m = re.search(rf'^[ \t]*<(Object\w+) Id="{re.escape(oid)}"[^>]*?(/?)>', text, re.M)
    if not m:
        raise SystemExit(f"Id {oid} not found in {SRC_OBJECTS}")
    end = m.end()
    if not m.group(2):
        close = text.find(f"</{m.group(1)}>", end)
        if close < 0:
            raise SystemExit(f"Id {oid} has no closing tag")
        end = close + len(f"</{m.group(1)}>")
    nl = re.match(r"\r?\n", text[end:])
    return m.start(), end + (nl.end() if nl else 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, help="base packed map (default: original/ at --rev)")
    parser.add_argument("--rev", default="HEAD", help="git revision for the default base")
    parser.add_argument("--edited", type=Path, default=EDITED)
    parser.add_argument("--check", action="store_true", help="report only, write nothing")
    args = parser.parse_args()

    base = objects_from_archive(args.base or base_from_git(args.rev))
    edited = objects_from_archive(args.edited)
    src_text = SRC_OBJECTS.read_bytes().decode("utf-8")
    src = {el.get("Id"): el for el in ET.fromstring(src_text.encode("utf-8"))}

    added = sorted(set(edited) - set(base))
    if added:
        raise SystemExit(f"added objects are not supported: {added}")
    removed = sorted(set(base) - set(edited))
    moved: dict[str, str] = {}
    for oid in sorted(set(base) & set(edited)):
        a, b = base[oid], edited[oid]
        diff = {k for k in a.attrib.keys() | b.attrib.keys() if a.get(k) != b.get(k)}
        if diff - PORTABLE:
            raise SystemExit(f"Id {oid}: unsupported attribute change {sorted(diff - PORTABLE)}")
        if [ET.tostring(c) for c in a] != [ET.tostring(c) for c in b]:
            raise SystemExit(f"Id {oid}: child elements changed")
        if diff:
            moved[oid] = b.get("Position")

    for oid in removed + sorted(moved):
        if oid not in src or src[oid].attrib != base[oid].attrib:
            raise SystemExit(f"Id {oid}: src/ object differs from base, refusing to port")

    for oid in removed:
        el = base[oid]
        print(f"remove {oid} {el.tag} {el.get('UnitType') or el.get('Type')} at {el.get('Position')}")
    for oid, pos in sorted(moved.items()):
        el = base[oid]
        print(f"move   {oid} {el.tag} {el.get('UnitType') or el.get('Type')} {el.get('Position')} -> {pos}")
    print(f"removed={len(removed)} moved={len(moved)}")
    if args.check:
        return 0

    for oid, pos in moved.items():
        start, end = element_span(src_text, oid)
        head = src_text[start:end]
        new = re.sub(r'Position="[^"]*"', f'Position="{pos}"', head, count=1)
        src_text = src_text[:start] + new + src_text[end:]
    for oid in removed:
        start, end = element_span(src_text, oid)
        src_text = src_text[:start] + src_text[end:]

    result = {el.get("Id"): el for el in ET.fromstring(src_text.encode("utf-8"))}
    if set(result) != set(src) - set(removed):
        raise SystemExit("result Id set is wrong, nothing written")
    for oid, pos in moved.items():
        if result[oid].get("Position") != pos:
            raise SystemExit(f"Id {oid}: position not applied, nothing written")
    SRC_OBJECTS.write_bytes(src_text.encode("utf-8"))
    print(f"wrote {SRC_OBJECTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
