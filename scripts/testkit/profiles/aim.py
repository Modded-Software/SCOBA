"""Aim test profile."""

from __future__ import annotations

import os
import time
from math import atan2, degrees
from pathlib import Path

from project_root import project_root

from ..framelog import parse_section
from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
AIM_LEG_CROP = (0.30, 0.45, 0.70, 0.90)
AIM_FRAME_MIN_CHANGED = 500
AIM_STOP_MIN_CHANGED = 100
AIM_IDLE_MIN_CHANGED = 100


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="aim",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["aim"],
        bank_names=PROFILE_BANKS["aim"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "aim.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/aim/common",
            "scripts/test/aim/aim",
        ),
        init_calls=("gt_AimTest_Init();",),
    )


def _release_keys(input_driver) -> None:
    for key in ("w", "a", "s", "d"):
        input_driver.key_up(key)


def _wait_realkeys_ready(docs: Path, timeout_s: float) -> bool:
    from ..bank import find_latest_bank, read_bank

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        path = find_latest_bank(docs, "SCOBAAIMTEST", 0.0)
        if path is not None:
            try:
                data = read_bank(path)
            except RuntimeError:
                data = None
            if data and data.get("aim_realkeys", {}).get("Ready") == 1:
                return True
        time.sleep(0.1)
    return False


def on_ready(ctx, data: dict) -> None:
    from .. import input_driver

    input_driver.focus()
    _release_keys(input_driver)
    time.sleep(0.2)
    time.sleep(0.25)
    ctx.frames.capture("aim_idle_lower")
    time.sleep(0.25)
    ctx.frames.capture("aim_idle_lower")
    time.sleep(1.5)
    ctx.frames.capture("aim_walk")
    time.sleep(0.3)
    ctx.frames.capture("aim_walk")
    time.sleep(0.3)
    ctx.frames.capture("aim_walk")
    time.sleep(4.0)
    ctx.frames.capture("aim_stop")

    game_prefix = Path(os.environ.get("SC2_GAME_PREFIX", str(Path.home() / "Games" / "battlenet-prefix")))
    docs = Path(
        os.environ.get(
            "SC2_DOCUMENTS",
            str(game_prefix / "pfx/drive_c/users/steamuser/Documents/StarCraft II"),
        )
    )
    if not _wait_realkeys_ready(docs, 90.0):
        ctx.errors.append("real key phase did not start")
        return
    combos = (
        ("k0", ("w",)),
        ("k1", ("w", "a")),
        ("k2", ("a",)),
        ("k3", ("s", "a")),
        ("k4", ("s",)),
        ("k5", ("s", "d")),
        ("k6", ("d",)),
        ("k7", ("w", "d")),
    )
    time.sleep(3.0)
    for _, keys in combos:
        input_driver.focus()
        _release_keys(input_driver)
        for key in keys:
            input_driver.key_down(key)
        time.sleep(1.0)
        _release_keys(input_driver)
        time.sleep(0.2)


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1

    checks.eq("meta", "", "done", 1)
    checks.eq("meta", "", "profile", "aim")
    checks.eq("aim_enter", "t0200", "AimActive", 1)
    checks.eq("aim_enter", "t0200", "CursorVisible", 1)
    checks.between("aim_enter", "t0200", "UpperState", 3, 5)
    checks.eq("aim_enter", "t0200", "LowerState", 1)
    checks.eq("aim_idle", "t0700", "AimActive", 1)
    checks.eq("aim_idle", "t0700", "LowerState", 1)
    checks.eq("aim_hold", "t1700", "AimActive", 1)
    checks.eq("aim_hold", "t1700", "UpperState", 4)
    checks.eq("aim_fixed", "t0200", "UpperState", 4)
    checks.eq("aim_fixed", "t0200", "UpperClip", checks.value("aim_hold", "t1700", "UpperClip"))
    checks.eq("aim_settle", "t1500", "LowerState", 1)
    checks.eq("aim_enemy", "t0000", "AimCursorTarget", 1)
    checks.eq("aim_enemy", "t0000", "CursorVisible", 1)
    checks.eq("aim_walk", "t0000", "AimActive", 1)
    checks.eq("aim_walk", "t2500", "AimActive", 1)
    checks.eq("aim_walk", "t1500", "LowerState", 2)
    checks.eq("aim_walk", "t1800", "LowerState", 2)
    checks.eq("aim_stop", "t2500", "LowerState", 1)
    checks.eq("aim_stop", "t2750", "LowerState", 1)
    checks.eq("aim_release", "t0500", "AimActive", 0)
    directions = {
        "d0": (0, "Forward"),
        "d1": (1, "Forward,Left"),
        "d2": (2, "Left"),
        "d3": (3, "Back,Left"),
        "d4": (4, "Back"),
        "d5": (5, "Back,Right"),
        "d6": (6, "Right"),
        "d7": (7, "Forward,Right"),
    }
    expected_offsets = {
        "d0": 0.0,
        "d1": 45.0,
        "d2": 90.0,
        "d3": 135.0,
        "d4": 180.0,
        "d5": -135.0,
        "d6": -90.0,
        "d7": -45.0,
    }
    for tag, (index, token) in directions.items():
        checks.eq("aim_dir", tag, "AimDir", index)
        clip = str(checks.value("aim_dir", tag, "AimClip"))
        if token in clip:
            print(f"aim_dir {tag} clip: PASS")
        else:
            print(f"aim_dir {tag} clip: got={clip} want={token} FAIL")
            checks.failures += 1
        yaw = int(checks.value("aim_dir", tag, "CameraYaw"))
        facing = int(checks.value("aim_dir", tag, "UnitFacing"))
        delta = (facing - yaw + 180) % 360 - 180
        if abs(delta) <= 20:
            print(f"aim_dir {tag} facing: delta={delta} PASS")
        else:
            print(f"aim_dir {tag} facing: delta={delta} FAIL")
            checks.failures += 1
        start_x = int(checks.value("aim_dir_start", tag, "HeroX"))
        start_y = int(checks.value("aim_dir_start", tag, "HeroY"))
        end_x = int(checks.value("aim_dir", tag, "HeroX"))
        end_y = int(checks.value("aim_dir", tag, "HeroY"))
        dx = end_x - start_x
        dy = end_y - start_y
        if dx * dx + dy * dy < 4:
            print(f"aim_dir {tag} displacement: got=({dx},{dy}) FAIL")
            checks.failures += 1
            continue
        travel = degrees(atan2(dy, dx))
        expected = (yaw + expected_offsets[tag] + 180) % 360 - 180
        heading_delta = (travel - expected + 180) % 360 - 180
        if abs(heading_delta) <= 25:
            print(f"aim_dir {tag} travel: delta={heading_delta:.1f} PASS")
        else:
            print(f"aim_dir {tag} travel: got={travel:.1f} want={expected:.1f} FAIL")
            checks.failures += 1
    real_tags = {
        "k0": 0.0,
        "k1": 45.0,
        "k2": 90.0,
        "k3": 135.0,
        "k4": 180.0,
        "k5": -135.0,
        "k6": -90.0,
        "k7": -45.0,
    }
    for tag, offset in real_tags.items():
        yaw = checks.value("aim_realkeys", tag, "CameraYaw")
        facing = checks.value("aim_realkeys", tag, "UnitFacing")
        if yaw is None or facing is None:
            print(f"aim_realkeys {tag}: missing FAIL")
            checks.failures += 1
            continue
        delta = (int(facing) - int(yaw) + 180) % 360 - 180
        if abs(delta) <= 25:
            print(f"aim_realkeys {tag} facing: delta={delta} PASS")
        else:
            print(f"aim_realkeys {tag} facing: delta={delta} FAIL")
            checks.failures += 1
        start_x = int(checks.value("aim_realkeys_start", tag, "HeroX"))
        start_y = int(checks.value("aim_realkeys_start", tag, "HeroY"))
        end_x = int(checks.value("aim_realkeys", tag, "HeroX"))
        end_y = int(checks.value("aim_realkeys", tag, "HeroY"))
        dx = end_x - start_x
        dy = end_y - start_y
        if dx * dx + dy * dy < 4:
            print(f"aim_realkeys {tag} displacement: got=({dx},{dy}) FAIL")
            checks.failures += 1
            continue
        travel = degrees(atan2(dy, dx))
        expected = (int(yaw) + offset + 180) % 360 - 180
        heading_delta = (travel - expected + 180) % 360 - 180
        if abs(heading_delta) <= 30:
            print(f"aim_realkeys {tag} travel: delta={heading_delta:.1f} PASS")
        else:
            print(f"aim_realkeys {tag} travel: got={travel:.1f} want={expected:.1f} FAIL")
            checks.failures += 1
    frames = parse_section(ctx.frame_data.get("frames", {}))
    aim_walk = [
        record
        for record in frames
        if int(record["player"]) == 1
        and int(record.get("aim", 0)) == 1
        and int(record.get("lo", 0)) == 2
    ]
    upper_frames = [int(record.get("uframe", -1)) for record in aim_walk if int(record.get("uframe", -1)) >= 0]
    lower_ids = [int(record.get("lfid", -1)) for record in aim_walk if int(record.get("lfid", -1)) >= 0]
    if upper_frames and len(set(upper_frames)) == 1:
        print(f"aim_upper_frozen: count={len(upper_frames)} PASS")
    else:
        print(f"aim_upper_frozen: count={len(upper_frames)} unique={len(set(upper_frames))} FAIL")
        checks.failures += 1
    if len(set(lower_ids)) > 1:
        print(f"aim_lower_moving: count={len(lower_ids)} unique={len(set(lower_ids))} PASS")
    else:
        print(f"aim_lower_moving: count={len(lower_ids)} unique={len(set(lower_ids))} FAIL")
        checks.failures += 1
    turn_starts = 0
    aim_starts = 0
    for text in ctx.anim_data.get("events", {}).values():
        if "kind=upper_start" in str(text) and "clip=Turn" in str(text):
            turn_starts += 1
        if "kind=upper_start" in str(text) and "clip=Attack,Ready" in str(text):
            aim_starts += 1
    if turn_starts == 0:
        print("aim upper_start turn count: PASS")
    else:
        print(f"aim upper_start turn count: got={turn_starts} want=0 FAIL")
        checks.failures += 1
    if aim_starts == 0:
        print("aim upper_start hold count: PASS")
    else:
        print(f"aim upper_start hold count: got={aim_starts} want=0 FAIL")
        checks.failures += 1

    for key in ("Auto", "Stand"):
        checks.eq("aim_enter", "t0200", key, checks.value("aim_release", "t0500", key))
    for key in ("Root", "MoveSuppressed"):
        checks.eq("aim_enter", "t0200", key, checks.value("aim_idle", "t0700", key))

    walk = [path for path in ctx.frames.captured if path.name.startswith("aim_walk-")]
    stop = next((path for path in ctx.frames.captured if path.name.startswith("aim_stop-")), None)
    idle_lower = [path for path in ctx.frames.captured if path.name.startswith("aim_idle_lower-")]
    if len(walk) >= 3:
        checks.frame_diff("aim_walk", walk[0], walk[1], AIM_LEG_CROP, AIM_FRAME_MIN_CHANGED)
        checks.frame_diff("aim_walk", walk[1], walk[2], AIM_LEG_CROP, AIM_FRAME_MIN_CHANGED)
    else:
        print(f"aim_walk frames: got={len(walk)} want>=3 FAIL")
        checks.failures += 1
    if stop is not None and walk:
        checks.frame_diff("aim_stop", walk[-1], stop, AIM_LEG_CROP, AIM_STOP_MIN_CHANGED)
    else:
        print("aim_stop frame: missing FAIL")
        checks.failures += 1
    if len(idle_lower) >= 2:
        checks.frame_diff("aim_idle_lower", idle_lower[0], idle_lower[1], AIM_LEG_CROP, AIM_IDLE_MIN_CHANGED)
    else:
        print(f"aim idle lower frames: got={len(idle_lower)} want>=2 FAIL")
        checks.failures += 1


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="aim",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["aim"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["aim"],
        ready_section="aim_walk",
        ready_key="AimVisualReady",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )