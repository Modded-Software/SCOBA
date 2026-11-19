#!/usr/bin/env python3
"""Port editor changes to placed objects from original/ into src/.

Compares the Objects file of two packed maps: the base (default: original/
as committed at HEAD) and the edited map (default: original/SCOBA.SC2Map).
Objects are matched by Id. Removed objects are deleted from src/Objects,
changed Position attributes are copied, objects whose Flag children changed
are replaced by the edited element, and added objects are appended as the
editor wrote them. --skip ID leaves one object's change out. Every other
kind of change, any src/ object that does not match the base, and any added
Id already in src/ stops the script with no write.

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


def objects_text(path: Path) -> str:
    """Objects of a packed map, or of an unpacked map folder."""
    if path.is_dir():
        return (path / "Objects").read_bytes().decode("utf-8")
    data = mpyq.MPQArchive(str(path)).read_file("Objects")
    if data is None:
        raise SystemExit(f"no Objects in {path}")
    return data.decode("utf-8")


def parse_objects(text: str) -> dict[str, ET.Element]:
    return {el.get("Id"): el for el in ET.fromstring(text.encode("utf-8"))}


def objects_from_archive(path: Path) -> dict[str, ET.Element]:
    return parse_objects(objects_text(path))


def kids(el: ET.Element) -> list[tuple[str, dict[str, str]]]:
    return [(c.tag, dict(c.attrib)) for c in el]


def base_from_git(rev: str) -> Path:
    out = subprocess.run(["git", "show", f"{rev}:original/SCOBA.SC2Map"], cwd=ROOT, check=True, capture_output=True).stdout
    tmp = Path(tempfile.mkdtemp(prefix="port_objects_")) / "base.SC2Map"
    tmp.write_bytes(out)
    return tmp


def element_span(text: str, oid: str) -> tuple[int, int]:
    """Span of the element with this Id, including its indent and line end."""
    m = re.search(rf'^[ \t]*<(\w+) [^>]*?\bId="{re.escape(oid)}"[^>]*?(/?)>', text, re.M)
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
    parser.add_argument("--base", type=Path, help="base packed map or unpacked folder (default: original/ at --rev)")
    parser.add_argument("--rev", default="HEAD", help="git revision for the default base")
    parser.add_argument("--edited", type=Path, default=EDITED)
    parser.add_argument("--check", action="store_true", help="report only, write nothing")
    parser.add_argument("--skip", action="append", default=[], metavar="ID", help="leave this object's change out (repeatable)")
    args = parser.parse_args()

    base = objects_from_archive(args.base or base_from_git(args.rev))
    edited_text = objects_text(args.edited)
    edited = parse_objects(edited_text)
    src_text = SRC_OBJECTS.read_bytes().decode("utf-8")
    src = parse_objects(src_text)
    skip = set(args.skip)
    unknown = skip - (set(base) | set(edited))
    if unknown:
        raise SystemExit(f"--skip Ids not in base or edited map: {sorted(unknown)}")

    added = sorted(set(edited) - set(base) - skip)
    taken = [oid for oid in added if oid in src]
    if taken:
        raise SystemExit(f"added Ids already in src/: {taken}")
    removed = sorted(set(base) - set(edited) - skip)
    moved: dict[str, str] = {}
    reflagged: list[str] = []
    for oid in sorted((set(base) & set(edited)) - skip):
        a, b = base[oid], edited[oid]
        diff = {k for k in a.attrib.keys() | b.attrib.keys() if a.get(k) != b.get(k)}
        if diff - PORTABLE:
            raise SystemExit(f"Id {oid}: unsupported attribute change {sorted(diff - PORTABLE)}")
        if kids(a) != kids(b):
            if {tag for tag, _ in kids(a) + kids(b)} - {"Flag"}:
                raise SystemExit(f"Id {oid}: non-Flag child elements changed")
            reflagged.append(oid)
        elif diff:
            moved[oid] = b.get("Position")

    for oid in removed + sorted(moved) + reflagged:
        if oid not in src or src[oid].attrib != base[oid].attrib or kids(src[oid]) != kids(base[oid]):
            raise SystemExit(f"Id {oid}: src/ object differs from base, refusing to port")

    for oid in removed:
        el = base[oid]
        print(f"remove {oid} {el.tag} {el.get('UnitType') or el.get('Type')} at {el.get('Position')}")
    for oid, pos in sorted(moved.items()):
        el = base[oid]
        print(f"move   {oid} {el.tag} {el.get('UnitType') or el.get('Type')} {el.get('Position')} -> {pos}")
    for oid in reflagged:
        el = edited[oid]
        print(f"flags  {oid} {el.tag} {el.get('Type')} {[c.get('Index') for c in el]} at {el.get('Position')}")
    for oid in added:
        el = edited[oid]
        print(f"add    {oid} {el.tag} {el.get('UnitType') or el.get('Type')} at {el.get('Position')}")
    for oid in sorted(skip):
        print(f"skip   {oid}")
    print(f"removed={len(removed)} moved={len(moved)} reflagged={len(reflagged)} added={len(added)} skipped={len(skip)}")
    if args.check:
        return 0

    for oid, pos in moved.items():
        start, end = element_span(src_text, oid)
        head = src_text[start:end]
        new = re.sub(r'Position="[^"]*"', f'Position="{pos}"', head, count=1)
        src_text = src_text[:start] + new + src_text[end:]
    newline = "\r\n" if "\r\n" in src_text else "\n"
    for oid in reflagged:
        start, end = element_span(src_text, oid)
        e_start, e_end = element_span(edited_text, oid)
        block = edited_text[e_start:e_end].replace("\r\n", "\n").rstrip("\n") + "\n"
        src_text = src_text[:start] + block.replace("\n", newline) + src_text[end:]
    for oid in removed:
        start, end = element_span(src_text, oid)
        src_text = src_text[:start] + src_text[end:]
    if added:
        blocks = []
        for oid in added:
            start, end = element_span(edited_text, oid)
            block = edited_text[start:end].replace("\r\n", "\n").rstrip("\n") + "\n"
            blocks.append(block.replace("\n", newline))
        close = src_text.rfind("</PlacedObjects>")
        if close < 0:
            raise SystemExit("no </PlacedObjects> in src/ Objects")
        src_text = src_text[:close] + "".join(blocks) + src_text[close:]

    result = parse_objects(src_text)
    if set(result) != (set(src) - set(removed)) | set(added):
        raise SystemExit("result Id set is wrong, nothing written")
    for oid, pos in moved.items():
        if result[oid].get("Position") != pos:
            raise SystemExit(f"Id {oid}: position not applied, nothing written")
    for oid in reflagged:
        if result[oid].attrib != edited[oid].attrib or kids(result[oid]) != kids(edited[oid]):
            raise SystemExit(f"Id {oid}: flags not applied, nothing written")
    for oid in added:
        if ET.tostring(result[oid]).strip() != ET.tostring(edited[oid]).strip():
            raise SystemExit(f"Id {oid}: added object differs from the edited map, nothing written")
    SRC_OBJECTS.write_bytes(src_text.encode("utf-8"))
    print(f"wrote {SRC_OBJECTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
