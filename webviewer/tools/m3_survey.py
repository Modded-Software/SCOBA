"""Survey the model files of every catalog unit: which M3 struct versions they use.

Extracts the files into the server's cache (so the server does not extract
them again), reads each file's index table, and prints the tag/version pairs
the renderer's parser does not know, with how many units need each.

Run it through webviewer/scripts/m3-survey.sh. That script sets REPO_ROOT
and puts scripts/ on PYTHONPATH.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import re
import struct
from pathlib import Path

from hdtex.sc2.casc import Casc

if "REPO_ROOT" not in os.environ:
    raise SystemExit("m3_survey: REPO_ROOT is not set; run webviewer/scripts/m3-survey.sh")
ROOT = Path(os.environ["REPO_ROOT"])
MAP_ASSETS = ROOT / "src" / "SCOBA.SC2Map" / "Assets"
CHUNK = 80
# Tags the parser reads as plain arrays, whatever the version.
ARRAY_TAGS = {"CHAR", "SCHR", "U8__", "U16_", "U32_", "I16_", "I32_", "REAL", "VEC2", "VEC3", "SVC3", "VEC4", "QUAT", "IREF"}


def known_versions(parser_js: Path) -> dict[str, set[int]]:
    """Tag -> versions, read from the parser's own table."""
    known: dict[str, set[int]] = {}
    for tag, body in re.findall(r"^\s*(\w{4}): \[\w+(?:\.default)?, \{([^}]*)\}\]", parser_js.read_text(encoding="utf-8"), re.MULTILINE):
        known[tag] = {int(v) for v in re.findall(r"(\d+):", body)}
    return known


def index_of(path: Path) -> list[tuple[str, int, int]]:
    """(tag, version, count) of every index entry of an M3 file."""
    data = path.read_bytes()
    if data[:4] != b"43DM":
        raise ValueError(f"not an MD34 file: {data[:4]!r}")
    index_offset, index_size = struct.unpack_from("<II", data, 4)
    out = []
    for i in range(index_size):
        tag, _offset, count, version = struct.unpack_from("<4sIII", data, index_offset + i * 16)
        out.append((tag[::-1].decode("latin1"), version, count))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="the viewer data folder (catalog/ and cache/)")
    parser.add_argument("--parser", type=Path, required=True, help="the renderer's parsers/m3/indexentry.js")
    args = parser.parse_args()
    units = json.loads((args.data / "catalog" / "units.json").read_text(encoding="utf-8"))["units"]
    known = known_versions(args.parser)

    casc = Casc()
    stored: dict[str, str] = {}
    for line in casc._run(["-I", r"\.m3$", "-l"]).splitlines():
        path = line.strip()
        at = path.find("\\assets\\")
        if at < 0:
            continue
        key = path[at + 1 :]
        if key not in stored or ("\\base.sc2assets\\" in path and "\\base.sc2assets\\" not in stored[key]):
            stored[key] = path
    local = {"assets\\" + p.relative_to(MAP_ASSETS).as_posix().replace("/", "\\").lower(): p for p in MAP_ASSETS.rglob("*.m3")}

    files: dict[str, Path] = {}
    wanted: dict[str, str] = {}
    missing = 0
    for unit in units:
        key = unit["m3"].replace("/", "\\").lower()
        for candidate in (key, key[:-3] + "_00.m3"):
            if candidate in local:
                files[unit["id"]] = local[candidate]
                break
            if candidate in stored:
                wanted[unit["id"]] = stored[candidate]
                break
        else:
            missing += 1
    cache = args.data / "cache"
    todo = sorted({p for p in wanted.values() if not (cache / Path(*p.split("\\"))).is_file()})
    for i in range(0, len(todo), CHUNK):
        casc.extract(todo[i : i + CHUNK], cache)
    for unit_id, path in wanted.items():
        files[unit_id] = cache / Path(*path.split("\\"))

    # Where each unit's model file is on disk, for the parse survey.
    listing = args.data / "catalog" / "unit-files.json"
    listing.write_text(json.dumps({unit_id: str(path) for unit_id, path in sorted(files.items())}, indent=0) + "\n", encoding="utf-8")

    unknown: dict[tuple[str, int], list[str]] = collections.defaultdict(list)
    seen: dict[tuple[str, int], int] = collections.Counter()
    broken: dict[str, str] = {}
    blocked = set()
    for unit_id, path in sorted(files.items()):
        try:
            entries = index_of(path)
        except (ValueError, struct.error) as error:
            broken[unit_id] = str(error)
            continue
        for tag, version, _count in entries:
            seen[tag, version] += 1
            if tag in ARRAY_TAGS:
                continue
            if tag not in known or version not in known[tag]:
                unknown[tag, version].append(unit_id)
                blocked.add(unit_id)

    print(f"units {len(units)}  with a model file {len(files)}  without {missing}  unreadable {len(broken)}")
    print(f"units the parser rejects: {len(blocked)}")
    for (tag, version), ids in sorted(unknown.items(), key=lambda kv: -len(set(kv[1]))):
        ids = sorted(set(ids))
        state = "unknown tag" if tag not in known else f"known versions {sorted(known[tag])}"
        print(f"  {tag} v{version}: {len(ids)} units ({state}) e.g. {ids[:5]}")
    for unit_id, error in sorted(broken.items()):
        print(f"  unreadable {unit_id}: {error}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
