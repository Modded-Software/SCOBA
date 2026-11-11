"""Action mode motion test profile."""

from __future__ import annotations

import time
from math import hypot
from pathlib import Path

from project_root import project_root

from ..framelog import parse_section
from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="motion",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["motion"],
        bank_names=PROFILE_BANKS["motion"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "motion.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/motion/common",
            "scripts/test/motion/motion",
        ),
        init_calls=("gt_MotionTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    from .. import input_driver

    input_driver.focus()
    time.sleep(0.2)
    input_driver.key_down("w")
    try:
        time.sleep(5.0)
        ctx.frames.sample("motion_aim_gait", 8, 0.12)
        ctx.frames.capture("motion_aim_walk")
        time.sleep(5.0)
        ctx.frames.capture("motion_aim_walk")
        time.sleep(5.0)
    finally:
        input_driver.focus()
        input_driver.key_up("w")
        input_driver.key_down("d")
    try:
        time.sleep(5.0)
    finally:
        input_driver.focus()
        input_driver.key_up("d")


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1

    checks.eq("meta", "", "done", 1)
    checks.eq("meta", "", "profile", "motion")
    checks.eq("motion_start", "t0000", "ActionMode", 1)
    checks.eq("motion_move", "t15000", "ActionMode", 1)
    checks.eq("motion_start", "t0000", "AimActive", 1)
    checks.eq("motion_move", "t15000", "AimActive", 1)
    move_dx = (checks.value("motion_move", "t15000", "HeroX") or 0) - (checks.value("motion_start", "t0000", "HeroX") or 0)
    move_dy = (checks.value("motion_move", "t15000", "HeroY") or 0) - (checks.value("motion_start", "t0000", "HeroY") or 0)
    if abs(move_dx) + abs(move_dy) >= 10:
        print("motion_move displacement: PASS")
    else:
        print("motion_move displacement: FAIL")
        checks.failures += 1
    checks.eq("motion_lateral", "t20000", "AimActive", 1)
    checks.eq("motion_lateral", "t20000", "LowerState", 2)
    lateral_dx = (checks.value("motion_lateral", "t20000", "HeroX") or 0) - (checks.value("motion_move", "t15000", "HeroX") or 0)
    lateral_dy = (checks.value("motion_lateral", "t20000", "HeroY") or 0) - (checks.value("motion_move", "t15000", "HeroY") or 0)
    if abs(lateral_dx) + abs(lateral_dy) >= 10:
        print("motion_lateral displacement: PASS")
    else:
        print("motion_lateral displacement: FAIL")
        checks.failures += 1
    frames = parse_section(ctx.frame_data.get("frames", {}))
    print(f"motion_frames: {len(frames)}")
    print(f"motion_lower_start: {checks.value('motion_start', 't0000', 'LowerState')}")
    print(f"motion_lower_end: {checks.value('motion_move', 't15000', 'LowerState')}")
    other = [record for record in frames if int(record["player"]) != 1]
    if other:
        print("motion_other_model_frames: PASS")
    else:
        print("motion_other_model_frames: FAIL")
        checks.failures += 1
    walking = [
        record
        for record in frames
        if int(record["player"]) == 1
        and int(record.get("action", 0)) == 1
        and int(record.get("aim", 0)) == 1
        and int(record.get("fwd", 0)) == 1
        and 5000 <= int(record.get("ms", 0)) <= 15000
    ]
    lower_frames = [int(record.get("lframe", -1)) for record in walking]
    lower_frames = [frame for frame in lower_frames if frame >= 0]
    print(f"motion_lower_frames: count={len(lower_frames)} unique={len(set(lower_frames))}")
    lower_ids = [
        int(record.get("lfid", -1))
        for record in walking
        if int(record.get("lfid", -1)) >= 0
    ]
    lower_span = {int(record.get("lframes", 0)) for record in walking if int(record.get("lframes", 0)) > 0}
    in_range = all(frame < max(lower_span) for frame in lower_ids) if lower_span else False
    if len(set(lower_ids)) > 1 and in_range:
        print(f"motion_lower_frame_ids: count={len(lower_ids)} unique={len(set(lower_ids))} PASS")
    else:
        print(f"motion_lower_frame_ids: count={len(lower_ids)} unique={len(set(lower_ids))} in_range={in_range} FAIL")
        checks.failures += 1
    lateral = [
        record
        for record in frames
        if int(record["player"]) == 1
        and int(record.get("action", 0)) == 1
        and int(record.get("aim", 0)) == 1
        and int(record.get("lo", 0)) == 2
        and 16000 <= int(record.get("ms", 0)) <= 21000
    ]
    lateral_ids = [
        int(record.get("lfid", -1))
        for record in lateral
        if int(record.get("lfid", -1)) >= 0
    ]
    lateral_span = {int(record.get("lframes", 0)) for record in lateral if int(record.get("lframes", 0)) > 0}
    lateral_in_range = all(frame < max(lateral_span) for frame in lateral_ids) if lateral_span else False
    if lateral and len(set(lateral_ids)) > 1 and lateral_in_range:
        print(f"motion_lateral_frame_ids: count={len(lateral_ids)} unique={len(set(lateral_ids))} PASS")
    else:
        print(f"motion_lateral_frame_ids: count={len(lateral_ids)} unique={len(set(lateral_ids))} in_range={lateral_in_range} FAIL")
        checks.failures += 1
    dips = 0
    for first, second in zip(walking, walking[1:]):
        distance = hypot(
            int(second.get("xf", 0)) - int(first.get("xf", 0)),
            int(second.get("yf", 0)) - int(first.get("yf", 0)),
        )
        if distance == 0:
            dips += 1
    if dips == 0 and walking:
        print("motion_walk zero dips: PASS")
    else:
        print(f"motion_walk zero dips: got={dips} want=0 FAIL")
        checks.failures += 1
    idle_orders = sum(1 for record in walking if int(record.get("orders", 0)) == 0)
    if idle_orders <= 1:
        print("motion_walk idle orders: PASS")
    else:
        print(f"motion_walk idle orders: got={idle_orders} want<=1 FAIL")
        checks.failures += 1


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="motion",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["motion"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["motion"],
        ready_section="motion_start",
        ready_key="MotionReady",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )