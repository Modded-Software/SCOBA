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

from project_root import project_root

ROOT = project_root()
GAME_PREFIX = Path(
    os.environ.get("SC2_GAME_PREFIX", str(Path.home() / "Games" / "battlenet-prefix"))
)
DOCS = Path(
    os.environ.get(
        "SC2_DOCUMENTS",
        str(GAME_PREFIX / "pfx/drive_c/users/steamuser/Documents/StarCraft II"),
    )
)
MAP_CACHE = (
    GAME_PREFIX
    / "pfx/drive_c/ProgramData/Blizzard Entertainment/StarCraft II/Maps/Cache"
    / "SCOBA.SC2Map"
)
BANK_GLOBS = ["Banks/SCOBATEST.SC2Bank", "Accounts/*/*/Banks/SCOBATEST.SC2Bank"]
PROBES = {
    "P1": {"start": (150, 128), "target": (6, 128), "axis": "player1-marine-west"},
}
if os.environ.get("SC2_PROBE_START"):
    _sx, _sy = (int(v) for v in os.environ["SC2_PROBE_START"].split(","))
    _tx, _ty = (int(v) for v in os.environ["SC2_PROBE_TARGET"].split(","))
    PROBES = {
        "P1": {"start": (_sx, _sy), "target": (_tx, _ty), "axis": "single-p1"},
    }


def sc2_pids() -> list[int]:
    result = subprocess.run(["pgrep", "-f", "SC2_x64.exe"], capture_output=True, text=True)
    if result.returncode not in (0, 1):
        sys.stderr.write(result.stderr)
        raise RuntimeError(f"pgrep failed with exit code {result.returncode}")
    return [int(x) for x in result.stdout.split() if x.isdigit()]


def kill_sc2() -> None:
    for pid in sc2_pids():
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError as exc:
            sys.stderr.write(f"WARNING: process {pid} already gone: {exc}\n")
    time.sleep(3)
    for pid in sc2_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError as exc:
            sys.stderr.write(f"WARNING: process {pid} already gone: {exc}\n")


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
    except (ET.ParseError, OSError) as exc:
        sys.stderr.write(f"WARNING: cannot parse bank {path}: {exc}\n")
        return None
    data: dict[str, dict[str, int | bool]] = {}
    for section in root.findall("Section"):
        name = section.get("name", "")
        values: dict[str, int | bool] = {}
        for key in section.findall("Key"):
            value = key.find("Value")
            if value is not None and value.get("int") is not None:
                values[key.get("name", "")] = int(value.get("int"))
            elif value is not None and value.get("flag") is not None:
                values[key.get("name", "")] = value.get("flag") == "1"
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
    shutil.rmtree(MAP_CACHE, ignore_errors=True)
    kill_sc2()
    for old in DOCS.glob("Banks/SCOBATEST.SC2Bank"):
        old.unlink()
    started = time.time()
    env = {**os.environ, "SC2_MAP_SOURCE": os.environ.get("SC2_TEST_MAP", str(ROOT / "out" / "SCOBA256.SC2Map"))}
    log_dir = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "scoba"
    log_dir.mkdir(parents=True, exist_ok=True)
    launch_log = open(log_dir / "integration-test.log", "ab")
    launcher = subprocess.Popen(
        ["bash", str(ROOT / "scripts" / "launch-scoba.sh")],
        cwd=ROOT,
        env=env,
        stdout=launch_log,
        stderr=launch_log,
        start_new_session=True,
    )

    timeout = float(os.environ.get("SC2_TEST_TIMEOUT", "90"))
    deadline = time.time() + timeout
    bank_path: Path | None = None
    data: dict | None = None
    sc2_seen = False
    missing_since: float | None = None
    while time.time() < deadline:
        time.sleep(1)
        now = time.time()
        pids = sc2_pids()
        if pids:
            sc2_seen = True
            missing_since = None
        else:
            if missing_since is None:
                missing_since = now
            if sc2_seen and now - missing_since >= 5:
                print("FAIL: SC2 exited before the test bank completed", file=sys.stderr)
                break
            if not sc2_seen and now - started >= 30 and launcher.poll() is not None:
                print("FAIL: SC2 did not start", file=sys.stderr)
                break
        bank_path = find_bank(started)
        if bank_path is not None:
            data = read_bank(bank_path)
            if data and data.get("meta", {}).get("done") == 1:
                break
        err = latest_script_error(started)
        if err is not None:
            print(f"FAIL: script compile or runtime error: {err}", file=sys.stderr)
            print(err.read_text(errors="replace"), file=sys.stderr)
            kill_sc2()
            return 1

    if bank_path is None or data is None or data.get("meta", {}).get("done") != 1:
        if time.time() >= deadline:
            print(f"FAIL: test bank timed out after {timeout:.0f}s", file=sys.stderr)
        elif bank_path is not None and data is not None:
            print("FAIL: test bank incomplete", file=sys.stderr)
        else:
            print("FAIL: no test bank produced", file=sys.stderr)
        log_path = log_dir / "launcher.log"
        if log_path.is_file():
            lines = log_path.read_text(errors="replace").splitlines()[-40:]
            print("launcher log tail:", file=sys.stderr)
            print("\n".join(lines), file=sys.stderr)
        kill_sc2()
        return 1
    err = latest_script_error(started)
    if err is not None:
        print(f"WARNING: script errors logged: {err}", file=sys.stderr)

    print(f"bank: {bank_path}")
    meta = data.get("meta", {})
    print(f"done: {meta.get('done')}  anchor: ({meta.get('anchorX')},{meta.get('anchorY')})")
    engine = data.get("engine", {})
    print(f"engine entire bounds: ({engine.get('entire_min_x')},{engine.get('entire_min_y')})..({engine.get('entire_max_x')},{engine.get('entire_max_y')})")
    print(f"engine playable bounds: ({engine.get('play_min_x')},{engine.get('play_min_y')})..({engine.get('play_max_x')},{engine.get('play_max_y')})")

    grid = data.get("grid")
    if grid:
        print("pathing grid (33x33, 8..232 step 7):")
        for gy in range(33):
            print("  " + "".join("#" if grid.get(str(gy * 33 + gx)) == 1 else "." for gx in range(33)))

    failures = 0

    def value(section: str, tag: str, key: str):
        return data.get(section, {}).get(tag + key)

    def check_equal(section: str, tag: str, key: str, want) -> None:
        nonlocal failures
        got = value(section, tag, key)
        status = "PASS" if got == want else "FAIL"
        print(f"{section} {tag} {key}: got={got} want={want} {status}")
        if got != want:
            failures += 1

    def check_true(section: str, tag: str, key: str) -> None:
        check_equal(section, tag, key, True)

    def check_false(section: str, tag: str, key: str) -> None:
        check_equal(section, tag, key, False)

    def displacement(section: str, tag_a: str, tag_b: str) -> int:
        ax = value(section, tag_a, "HeroX") or 0
        ay = value(section, tag_a, "HeroY") or 0
        bx = value(section, tag_b, "HeroX") or 0
        by = value(section, tag_b, "HeroY") or 0
        return abs(bx - ax) + abs(by - ay)

    def check_damage(section: str, tag_before: str, tag_after: str) -> None:
        nonlocal failures
        before = value(section, tag_before, "EnemyHp")
        after = value(section, tag_after, "EnemyHp")
        ok = before is not None and after is not None and after < before
        print(f"{section} {tag_before}->{tag_after} EnemyHp: before={before} after={after} want damage {'PASS' if ok else 'FAIL'}")
        if not ok:
            failures += 1

    if meta.get("done") != 1:
        print(f"meta done: got={meta.get('done')} want=1 FAIL")
        failures += 1

    check_equal("startup", "t0000", "Auto", 0)
    check_equal("startup", "t0000", "Stand", 1)
    check_equal("startup", "t0000", "Root", 1)
    check_true("startup", "t0000", "MoveSuppressed")
    check_false("startup", "t0000", "AttackOrder")

    check_equal("auto_off", "t0000", "Auto", 0)
    check_false("auto_off", "t3000", "AttackOrder")
    check_equal("auto_off", "t0000", "EnemyHp", value("auto_off", "t3000", "EnemyHp"))
    if displacement("auto_off", "t0000", "t3000") > 1:
        print("auto_off displacement: want<=1 FAIL")
        failures += 1

    check_equal("stand_in", "t0000", "Stand", 1)
    check_equal("stand_in", "t0000", "Root", 1)
    check_true("stand_in", "t0000", "MoveSuppressed")
    check_true("stand_in", "t0500", "AttackOrder")
    check_damage("stand_in", "t0000", "t2500")
    if displacement("stand_in", "t0000", "t2500") > 1:
        print("stand_in displacement: want<=1 FAIL")
        failures += 1

    check_equal("stand_out", "t2500", "Root", 1)
    check_true("stand_out", "t2500", "MoveSuppressed")
    if displacement("stand_out", "t0000", "t2500") > 1:
        print("stand_out displacement: want<=1 FAIL")
        failures += 1

    check_equal("stand_outside", "t2000", "Root", 1)
    check_true("stand_outside", "t2000", "MoveSuppressed")
    check_false("stand_outside", "t2000", "AttackOrder")
    if displacement("stand_outside", "t0000", "t2000") > 1:
        print("stand_outside displacement: want<=1 FAIL")
        failures += 1

    check_equal("stand_auto_off", "t0000", "Auto", 0)
    check_equal("stand_auto_off", "t0000", "Root", 1)
    check_true("stand_auto_off", "t0000", "MoveSuppressed")
    check_equal("stand_auto_off", "t2000", "Root", 1)
    if displacement("stand_auto_off", "t0000", "t2000") > 1:
        print("stand_auto_off displacement: want<=1 FAIL")
        failures += 1

    check_equal("stand_wake_manual", "t0200", "Root", 0)
    check_equal("stand_wake_manual", "t1000", "Root", 1)
    check_equal("stand_wake_manual", "t2000", "Root", 1)
    if displacement("stand_wake_manual", "t0000", "t2000") > 1:
        print("stand_wake_manual displacement: want<=1 FAIL")
        failures += 1

    check_equal("right_click", "", "ran", True)
    check_true("right_click", "t0200", "AttackOrder")
    check_true("right_click", "t0200", "TargetEnemy")
    check_equal("right_click", "t0200", "Root", 1)

    check_equal("right_drag", "", "ran", False)
    check_false("right_drag", "t0000", "AttackOrder")
    check_false("right_drag", "t0500", "AttackOrder")
    check_equal("right_drag", "t0000", "Root", 1)

    check_equal("right_point", "", "pickValid", True)

    check_equal("right_ground_walk", "", "ran", True)
    if displacement("right_ground_walk", "t0000", "t1000") <= 1:
        print("right_ground_walk displacement: want>1 FAIL")
        failures += 1

    check_equal("right_ground_stand", "", "ran", True)
    check_equal("right_ground_stand", "t0500", "Root", 1)
    if displacement("right_ground_stand", "t0000", "t0500") > 1:
        print("right_ground_stand displacement: want<=1 FAIL")
        failures += 1

    check_true("right_target_kept", "t0200", "TargetEnemy")

    check_true("both_forward", "tkey", "Forward")
    check_false("both_forward", "tmouse", "Forward")

    if displacement("walk_ground", "t0000", "t1000") <= 1:
        print("walk_ground displacement: want>1 FAIL")
        failures += 1

    check_equal("stand_ground", "t1000", "Root", 1)
    if displacement("stand_ground", "t0000", "t1000") > 1:
        print("stand_ground displacement: want<=1 FAIL")
        failures += 1

    check_equal("move_wake", "t0000", "Root", 1)
    check_true("move_wake", "t0000", "MoveSuppressed")
    check_equal("move_wake", "t0200", "Root", 0)
    check_false("move_wake", "t0200", "MoveSuppressed")
    if displacement("move_wake", "t0000", "t1200") <= 1:
        print("move_wake displacement: want>1 FAIL")
        failures += 1
    check_equal("move_wake", "t2200", "Root", 1)

    check_equal("walk_chase", "t0000", "Root", 0)
    check_false("walk_chase", "t0000", "MoveSuppressed")
    start_distance = value("walk_chase", "t0000", "Distance")
    end_distance = value("walk_chase", "t3000", "Distance")
    if start_distance is None or end_distance is None or end_distance >= start_distance:
        print(f"walk_chase Distance: start={start_distance} end={end_distance} want decrease FAIL")
        failures += 1
    check_true("walk_chase", "t3000", "AttackOrder")
    check_damage("walk_chase", "t0000", "t3000")

    check_equal("walk_idle", "t0000", "Root", 0)
    check_false("walk_idle", "t2000", "AttackOrder")
    if displacement("walk_idle", "t0000", "t2000") > 1:
        print("walk_idle displacement: want<=1 FAIL")
        failures += 1

    check_equal("weapon", "t0000", "CooldownMs", 0)
    check_false("weapon", "t0000", "CmdCooldown")
    if value("weapon", "t0500", "CooldownMs") is None or value("weapon", "t0500", "CooldownMs") <= 0:
        print(f"weapon t0500 CooldownMs: got={value('weapon', 't0500', 'CooldownMs')} want>0 FAIL")
        failures += 1
    check_true("weapon", "t0500", "CmdCooldown")
    check_true("weapon", "t0500", "AttackOrder")
    check_damage("weapon", "t0000", "t1000")

    import shutil
    shutil.rmtree(MAP_CACHE, ignore_errors=True)
    kill_sc2()
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
