"""10-second aim freeze playtest profile."""

from __future__ import annotations

from pathlib import Path
import time

from project_root import project_root

from ..framelog import parse_section
from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
PITCH_TIME_MS = 10000.0
PITCH_STEPS = 99
STATIC_FRAME_MS = 1000


def expected_clip(time_ms: int) -> str:
    ratio = max(0.0, min(1.0, time_ms / PITCH_TIME_MS))
    step = int(round(ratio * (PITCH_STEPS - 1))) + 1
    step = max(1, min(PITCH_STEPS, step))
    return f"Ready,{step:02d}"


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="aimfreeze",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["aimfreeze"],
        bank_names=PROFILE_BANKS["aimfreeze"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "aimfreeze.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/aimfreeze/common",
            "scripts/test/aimfreeze/aimfreeze",
        ),
        init_calls=("gt_AimFreezeTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    time.sleep(1.5)
    ctx.frames.capture("aimfreeze_hold1")
    time.sleep(1.0)
    ctx.frames.capture("aimfreeze_hold2")
    time.sleep(0.5)
    ctx.frames.capture("aimfreeze_move1")


def expected_frame(time_ms: int) -> int:
    return int(round(time_ms / READY_FRAME_MS))


def check(ctx, data: dict, checks) -> None:
    checks.eq("meta", "", "done", 1)
    checks.eq("meta", "", "profile", "aimfreeze")
    hold1_at = checks.value("freeze", "", "hold1At") or 0
    hold2_at = checks.value("freeze", "", "hold2At") or 0
    move1_at = checks.value("freeze", "", "move1At") or 0
    move2_at = checks.value("freeze", "", "move2At") or 0
    hold1_time = checks.value("freeze", "", "hold1Time") or 0
    move1_time = checks.value("freeze", "", "move1Time") or 0
    frames = parse_section(ctx.frame_data.get("frames", {}))
    hold_rows = [
        record
        for record in frames
        if int(record["player"]) == 1 and hold1_at <= int(record["ms"]) <= hold2_at
    ]
    move_rows = [
        record
        for record in frames
        if int(record["player"]) == 1 and move1_at <= int(record["ms"]) <= move2_at
    ]
    hold_uclip = sorted({str(record.get("uclip", "")) for record in hold_rows})
    move_uclip = sorted({str(record.get("uclip", "")) for record in move_rows})
    hold_ulen = sorted({int(record.get("ulen", -1)) for record in hold_rows})
    move_ulen = sorted({int(record.get("ulen", -1)) for record in move_rows})
    want_hold = expected_clip(hold1_time)
    want_move = expected_clip(move1_time)
    print(
        f"freeze animation: hold={hold_uclip} move={move_uclip} "
        f"len_hold={hold_ulen} len_move={move_ulen} "
        f"want_hold={want_hold} want_move={want_move}"
    )
    playing = (
        hold_uclip == [want_hold]
        and move_uclip == [want_move]
        and hold_ulen == [STATIC_FRAME_MS]
        and move_ulen == [STATIC_FRAME_MS]
    )
    if playing:
        print("freeze correct animation: PASS")
    else:
        print("freeze correct animation: FAIL")
        checks.failures += 1
    held = hold_uclip == [want_hold] and move_uclip == [want_move] and want_move != want_hold
    if held:
        print("freeze camera frame held and changed: PASS")
    else:
        print("freeze camera frame held and changed: FAIL")
        checks.failures += 1


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="aimfreeze",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["aimfreeze"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["aimfreeze"],
        ready_section="freeze",
        ready_key="Ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )