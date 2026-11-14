#!/usr/bin/env python3
"""Put the shared hero attack cooldown link on the hero weapons."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from project_root import project_root

ROOT = project_root()
DEFAULT_MAP = ROOT / "out" / "SCOBA256.SC2Map"
GAMEDATA = Path("Base.SC2Data") / "GameData"

COOLDOWN_LINK = "SCOBA/Attack"
HERO_WEAPONS = ("Tosh", "RazorTalons", "QueenOfBladesPsiBlast")


def newline(text: str) -> str:
    return "\r\n" if "\r\n" in text else "\n"


def add_child(text: str, tag: str, entry_id: str, marker: str, lines: tuple[str, ...]) -> str:
    """Append child lines to an existing entry unless the marker is present."""
    pattern = re.compile(
        rf'(<{tag}\b[^>]*\bid="{re.escape(entry_id)}"[^>]*>)(.*?)([ \t]*</{tag}>)',
        re.S,
    )
    match = pattern.search(text)
    if match is None:
        raise SystemExit(f"{tag} {entry_id} not found")
    if marker in match.group(2):
        return text
    eol = newline(text)
    body = match.group(2).rstrip() + eol + eol.join(lines) + eol
    return text[: match.start()] + match.group(1) + body + match.group(3) + text[match.end() :]


def patch_weapons(text: str) -> str:
    lines = (
        "        <Cost>",
        f'            <Cooldown Link="{COOLDOWN_LINK}" Location="Unit"/>',
        "        </Cost>",
    )
    for weapon in HERO_WEAPONS:
        text = add_child(text, "CWeaponLegacy", weapon, COOLDOWN_LINK, lines)
    return text


def apply(map_dir: Path) -> int:
    path = Path(map_dir) / GAMEDATA / "WeaponData.xml"
    with path.open(encoding="utf-8", newline="") as handle:
        before = handle.read()
    after = patch_weapons(before)
    if after == before:
        return 0
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(after)
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=DEFAULT_MAP)
    args = parser.parse_args(argv[1:])
    changed = apply(args.map)
    print(f"patched {changed} data files for the hero attack cooldown link")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
