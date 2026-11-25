#!/usr/bin/env python3
"""Audit map unit actors for missing water terrain squibs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from water_splashes import NON_SPLASH_ACTORS, audit_actors, default_map


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=Path, default=None)
    args = parser.parse_args(argv[1:])
    if args.map is None:
        args.map = default_map()
    ok, missing, skipped = audit_actors(args.map)
    print(f"map: {args.map}")
    print(f"ok: {len(ok)} missing: {len(missing)} skipped: {len(skipped)}")
    print("missing:")
    for actor_id in missing:
        print(f"  {actor_id}")
    print("skipped:")
    for actor_id in skipped:
        print(f"  {actor_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))