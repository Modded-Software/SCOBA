#!/usr/bin/env python3
"""Stop StarCraft II processes before staging a map."""

from __future__ import annotations

import os
import signal
import sys
import time

TARGETS = (
    "SC2_x64.exe",
    "SC2Switcher_x64.exe",
    "StarCraft II.exe",
    "xalia.exe",
    "xalia",
)


def find_targets() -> list[int]:
    found: list[int] = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        if pid == os.getpid():
            continue
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as handle:
                cmd = handle.read().replace(b"\x00", b" ").decode("utf-8", "replace")
            with open(f"/proc/{pid}/comm", "r", encoding="utf-8", errors="replace") as handle:
                comm = handle.read().strip()
        except OSError as exc:
            print(f"WARNING: cannot read /proc/{pid}: {exc}", file=sys.stderr)
            continue
        haystack = cmd + " " + comm
        if any(target in haystack for target in TARGETS):
            found.append(pid)
    return found


def main() -> int:
    pids = find_targets()
    for pid in pids:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            sys.stderr.write(f"WARNING: cannot terminate pid {pid}: {exc}\n")
    if pids:
        time.sleep(3)
    for pid in find_targets():
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError as exc:
            sys.stderr.write(f"WARNING: cannot kill pid {pid}: {exc}\n")
    print(f"stopped {len(pids)} StarCraft process(es)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())