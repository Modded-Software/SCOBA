"""Bring a texture store of layout 2 to layout 3 (SPEC-HD-TEXTURES 4.1).

Layout 3 adds one key to each variant entry: `tiles`, whether the upscaler
matched the variant's edges across the border (results.TILES). Every upscale
before the key asked for matched edges (`arc-upscale submit --tiling`), so
an entry of layout 2 without the key gets `tiles: true`. The last tooling of
layout 2 wrote the key into the entries it made; such an entry keeps its
value. Nothing else changes.

It refuses a store with a request open: a request writes its entry when it
ends. Every entry is checked before the first is written. Each entry is
rewritten whole, under a temporary name first; the layout file is written
last. A run that stops halfway leaves a store this module finishes when run
again.

usage: make texture-store-migrate [ARGS=--dry-run]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import progress
from .results import TILES
from .store import ENTRY, FORMAT, FORMAT_FILE, StoreError, read_json, store_root, write_atomic, write_json

FROM = 2


def entries(root: Path) -> list[Path]:
    """Every variant entry of every game, in path order."""
    return sorted(root.glob(f"*/variants/*/*/{ENTRY}"))


def open_requests(root: Path) -> list[Path]:
    return sorted(root.glob(f"*/variants/*/*/{progress.FILE}"))


def migrated(entry: object, path: Path) -> dict:
    """The entry in layout 3. An entry already of 3 comes back as it is."""
    if not isinstance(entry, dict) or entry.get("format") not in (FROM, FORMAT):
        raise StoreError(f"{path} is not an entry of layout {FROM} or {FORMAT}")
    if entry["format"] == FORMAT:
        if not isinstance(entry.get(TILES), bool):
            raise StoreError(f"{path} is of layout {FORMAT} and has no {TILES!r}")
        return entry
    # The last tooling of layout 2 wrote the key into the entries it made: such an entry keeps its value.
    if TILES in entry and not isinstance(entry[TILES], bool):
        raise StoreError(f"{path} is of layout {FROM} and its {TILES!r} is not true or false")
    return {**entry, "format": FORMAT, TILES: entry.get(TILES, True)}


def migrate(root: Path, dry_run: bool) -> dict:
    """Rewrite each entry of layout 2, then the layout file. Returns what was found and done."""
    marker = root / FORMAT_FILE
    if not marker.is_file():
        raise StoreError(f"{root} has no {FORMAT_FILE} file; it is not a texture store")
    layout = marker.read_text().strip()
    if layout not in (str(FROM), str(FORMAT)):
        raise StoreError(f"{root} has layout {layout!r}; this brings {FROM} to {FORMAT}")
    if busy := open_requests(root):
        raise StoreError(f"{len(busy)} request(s) are open, such as {busy[0].parent}; let them end first")
    # Every entry is read and checked before the first is written: a wrong one stops the run with nothing changed.
    found = entries(root)
    changed = []
    for path in found:
        entry = read_json(path)
        after = migrated(entry, path)
        if after is not entry:
            changed.append((path, after))
    if not dry_run:
        for path, after in changed:
            write_json(path, after)
        if layout != str(FORMAT):
            write_atomic(marker, f"{FORMAT}\n".encode())
    return {"store": str(root), "layout": layout, "entries": len(found), "changed": len(changed), "dryRun": dry_run}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="say what would change; write nothing")
    args = parser.parse_args(argv)
    try:
        found = migrate(store_root(), args.dry_run)
    except StoreError as error:
        print(f"texture-store-migrate: {error}", file=sys.stderr)
        return 1
    print(" ".join(f"{key}={value}" for key, value in found.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
