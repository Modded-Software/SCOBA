#!/usr/bin/env python3
"""List or extract files from an SC2Map/SC2Mod MPQ archive."""

from __future__ import annotations

import argparse
import os
import sys

import mpyq


def read_names(archive: mpyq.MPQArchive) -> list[str]:
    raw = archive.read_file("(listfile)")
    if not raw:
        return []
    return [line for line in raw.decode("utf-8", "replace").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", help="path to .SC2Map or .SC2Mod")
    parser.add_argument("--extract", metavar="DIR", help="extract all files here")
    parser.add_argument("--cat", metavar="NAME", help="print one archive file")
    args = parser.parse_args()

    archive = mpyq.MPQArchive(args.archive)
    names = read_names(archive)

    if args.cat:
        data = archive.read_file(args.cat)
        if data is None:
            print(f"not found: {args.cat}", file=sys.stderr)
            return 1
        sys.stdout.buffer.write(data)
        return 0

    if args.extract:
        os.makedirs(args.extract, exist_ok=True)
        for name in names:
            data = archive.read_file(name)
            if data is None:
                print(f"missing: {name}", file=sys.stderr)
                continue
            target = os.path.join(args.extract, name.replace("\\", "/"))
            os.makedirs(os.path.dirname(target) or args.extract, exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(data)
            print(f"{len(data):8d}  {name}")
        return 0

    print(
        f"format_version={archive.header['format_version']} "
        f"files={len(names)} "
        f"hash_entries={archive.header['hash_table_entries']} "
        f"block_entries={archive.header['block_table_entries']}"
    )
    for name in names:
        print(name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
