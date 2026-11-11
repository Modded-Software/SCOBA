#!/usr/bin/env python3
"""Print live character frame probe rows from the latest bank."""

from __future__ import annotations

import argparse
import os
import time
from pathlib import Path

from project_root import project_root
from testkit.bank import find_latest_bank, read_bank
from testkit.framelog import analyze, frame_order, parse_section

ROOT = project_root()
BANK = "SCOBAFRAMELOG"


def docs_path() -> Path:
    prefix = Path(os.environ.get("SC2_GAME_PREFIX", str(Path.home() / "Games" / "battlenet-prefix")))
    return Path(
        os.environ.get(
            "SC2_DOCUMENTS",
            str(prefix / "pfx/drive_c/users/steamuser/Documents/StarCraft II"),
        )
    )


def latest_bank(explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    return find_latest_bank(docs_path(), BANK, 0)


def format_row(record: dict[str, int | str]) -> str:
    parts = [
        f"p{record.get('player', 0)}",
        f"ms={record.get('ms', 0)}",
        f"seq={record.get('seq', 0)}",
        f"up={record.get('up', 0)}",
        f"lo={record.get('lo', 0)}",
        f"uclip={record.get('uclip', '')}",
        f"lclip={record.get('lclip', '')}",
        f"uq={record.get('uq', '')}",
        f"lq={record.get('lq', '')}",
        f"uframe={record.get('uframe', -1)}",
        f"lframe={record.get('lframe', -1)}",
        f"x={record.get('x', 0)}",
        f"y={record.get('y', 0)}",
        f"a0={record.get('a0', '')}",
    ]
    return " ".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", type=Path)
    parser.add_argument("--follow", action="store_true")
    parser.add_argument("--interval", type=float, default=0.25)
    args = parser.parse_args()
    seen = 0
    while True:
        path = latest_bank(args.bank)
        if path is None:
            print(f"waiting for {BANK}")
            if not args.follow:
                return 1
            time.sleep(args.interval)
            continue
        data = read_bank(path)
        if data is None:
            print(f"cannot read {path}")
            return 1
        frames = parse_section(data.get("frames", {}))
        frames.sort(key=frame_order)
        events = parse_section(data.get("events", {}))
        config = {str(key): str(value) for key, value in data.get("config", {}).items()}
        for record in frames[seen:]:
            print(format_row(record))
        seen = len(frames)
        print(f"anomalies={analyze(frames, events, config)} events={len(events)}")
        if not args.follow:
            return 0
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())