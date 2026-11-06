#!/usr/bin/env python3
"""Run the instrumented map integration test end to end.

Builds out/SCOBA256.SC2Map, launches StarCraft II, waits for the test bank,
then prints probe paths and pass/fail diagnostics.

No keyboard or mouse input is needed: the test build has Wait-for-Key cleared.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = Path(
    "/home/agent/Games/battlenet-prefix/pfx/drive_c/users/steamuser/Documents/StarCraft II"
)
BANK_GLOBS = ["Banks/SCOBATEST.SC2Bank", "Accounts/*/*/Banks/SCOBATEST.SC2Bank"]
PROBES = {
    "P1": {"start": (150, 128), "target": (6, 128), "axis": "player1-marine-west"},
    "P7": {"start": (150, 128), "target": (6, 128), "axis": "player7-zergling-west"},
}
if os.environ.get("SC2_PROBE_START"):
    _sx, _sy = (int(v) for v in os.environ["SC2_PROBE_START"].split(","))
    _tx, _ty = (int(v) for v in os.environ["SC2_PROBE_TARGET"].split(","))
    PROBES = {
        "P1": {"start": (_sx, _sy), "target": (_tx, _ty), "axis": "single-p1"},
        "P7": {"start": (_sx, _sy), "target": (_tx, _ty), "axis": "single-p7"},
    }


def sc2_pids() -> list[int]:
    result = subprocess.run(["pgrep", "-f", "SC2_x64.exe"], capture_output=True, text=True)
    return [int(x) for x in result.stdout.split() if x.isdigit()]


def kill_sc2() -> None:
    for pid in sc2_pids():
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    time.sleep(3)
    for pid in sc2_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def find_bank(started: float) -> Path | None:
    candidates = []
    for pattern in BANK_GLOBS:
        candidates.extend(p for p in DOCS.glob(pattern) if p.stat().st_mtime >= started)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def read_bank(path: Path) -> dict | None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None
    data: dict[str, dict[str, int]] = {}
    for section in root.findall("Section"):
        name = section.get("name", "")
        values: dict[str, int] = {}
        for key in section.findall("Key"):
            value = key.find("Value")
            if value is not None and value.get("int") is not None:
                values[key.get("name", "")] = int(value.get("int"))
        data[name] = values
    return data


def latest_script_error(started: float) -> Path | None:
    logs = DOCS / "GameLogs"
    if not logs.is_dir():
        return None
    candidates = [p for p in logs.glob("*ScriptError.txt") if p.stat().st_mtime >= started]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def main() -> int:
    import shutil
    shutil.rmtree(Path("/home/agent/Games/battlenet-prefix/pfx/drive_c/ProgramData/Blizzard Entertainment/StarCraft II/Maps/Cache/SCOBA.SC2Map"), ignore_errors=True)
    kill_sc2()
    for old in DOCS.glob("Banks/SCOBATEST.SC2Bank"):
        old.unlink()
    started = time.time()
    env = {**os.environ, "SC2_MAP_SOURCE": os.environ.get("SC2_TEST_MAP", str(ROOT / "out" / "SCOBA256.SC2Map"))}
    log_dir = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "scoba"
    log_dir.mkdir(parents=True, exist_ok=True)
    launch_log = open(log_dir / "integration-test.log", "ab")
    subprocess.Popen(
        ["bash", str(ROOT / "scripts" / "launch-scoba.sh")],
        cwd=ROOT,
        env=env,
        stdout=launch_log,
        stderr=launch_log,
        start_new_session=True,
    )

    time.sleep(15)
    for _ in range(4):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "input_inject.py"), "auto"])
        time.sleep(6)
    bank_path: Path | None = None
    data: dict | None = None
    deadline = time.time() + 150
    while time.time() < deadline:
        time.sleep(2)
        bank_path = find_bank(started)
        if bank_path is not None:
            data = read_bank(bank_path)
            if data and data.get("meta", {}).get("done") == 1:
                break

    if bank_path is None or data is None:
        print("FAIL: no test bank produced", file=sys.stderr)
        err = latest_script_error(started)
        if err is not None:
            print(err.read_text(errors="replace"), file=sys.stderr)
        kill_sc2()
        return 1
    err = latest_script_error(started)
    if err is not None:
        print(f"WARNING: script errors logged: {err}", file=sys.stderr)

    print(f"bank: {bank_path}")
    meta = data.get("meta", {})
    print(f"ticks: {meta.get('tick')}  done: {meta.get('done')}")
    engine = data.get("engine", {})
    print(f"engine entire bounds: ({engine.get('entire_min_x')},{engine.get('entire_min_y')})..({engine.get('entire_max_x')},{engine.get('entire_max_y')})")
    print(f"engine playable bounds: ({engine.get('play_min_x')},{engine.get('play_min_y')})..({engine.get('play_max_x')},{engine.get('play_max_y')})")

    grid = data.get("grid")
    if grid:
        print("pathing grid (33x33, 8..232 step 7):")
        for gy in range(33):
            print("  " + "".join("#" if grid.get(str(gy * 33 + gx)) == 1 else "." for gx in range(33)))



    failures = 0
    for p, info in PROBES.items():
        vals = data.get(p, {})
        fx, fy = vals.get("x"), vals.get("y")
        sx, sy = info["start"]
        tx, ty = info["target"]
        print(f"\nprobe {p} ({info['axis']}): start=({sx},{sy}) target=({tx},{ty}) final=({fx},{fy})")
        if fx is None or fy is None:
            print("  FAIL: no final position")
            failures += 1
            continue
        remaining = abs(tx - fx) + abs(ty - fy)
        start_dist = abs(tx - sx) + abs(ty - sy)
        progress = 1.0 - remaining / start_dist if start_dist else 0.0
        print(f"  progress={progress:.0%} remaining={remaining}")
        if progress < 0.90:
            print("  FAIL: did not reach target")
            failures += 1
        else:
            print("  PASS")

    import shutil
    shutil.rmtree(Path("/home/agent/Games/battlenet-prefix/pfx/drive_c/ProgramData/Blizzard Entertainment/StarCraft II/Maps/Cache/SCOBA.SC2Map"), ignore_errors=True)
    kill_sc2()
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
