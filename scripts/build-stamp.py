#!/usr/bin/env python3
"""Write a deterministic build stamp into an expanded map folder."""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

PLACEHOLDER = 'const string c_SCOBA_BUILD_STAMP = "dev";'


def source_digest(source: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(p for p in source.rglob("*") if p.is_file()):
        digest.update(path.relative_to(source).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def git_revision(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short=12", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "nogit"
    value = result.stdout.strip()
    return value or "nogit"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("map_dir", type=Path)
    args = parser.parse_args()

    source = args.source
    map_dir = args.map_dir
    if not source.is_dir():
        print(f"ERROR: source not found: {source}", file=sys.stderr)
        return 2
    if not map_dir.is_dir():
        print(f"ERROR: map folder not found: {map_dir}", file=sys.stderr)
        return 2

    stamp = f"{git_revision(source.parent.parent)}-{source_digest(source)}"
    (map_dir / "BuildStamp.txt").write_text(stamp + "\n", encoding="utf-8")

    combat = map_dir / "scripts" / "combat.galaxy"
    text = combat.read_text(encoding="utf-8")
    replacement = f'const string c_SCOBA_BUILD_STAMP = "{stamp}";'
    if PLACEHOLDER in text:
        text = text.replace(PLACEHOLDER, replacement, 1)
    else:
        lines = text.splitlines()
        replaced = False
        for index, line in enumerate(lines):
            if line.startswith("const string c_SCOBA_BUILD_STAMP = "):
                lines[index] = replacement
                replaced = True
                break
        if not replaced:
            print("ERROR: build stamp constant not found in combat.galaxy", file=sys.stderr)
            return 1
        text = "\n".join(lines) + "\n"
    combat.write_text(text, encoding="utf-8", newline="\n")
    print(stamp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())