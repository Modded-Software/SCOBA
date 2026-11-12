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
STATIC_FRAME_MS = 100
PITCH_MIN = -95.0
PITCH_MAX = 50.0
PITCH_REST = -13.0


def expected_step(camera_deg: float) -> int:
    aim = PITCH_REST - camera_deg
    ratio = max(0.0, min(1.0, (aim - PITCH_MIN) / (PITCH_MAX - PITCH_MIN)))
    return max(1, min(PITCH_STEPS, int(round(ratio * (PITCH_STEPS - 1))) + 1))


def clip_step(text: str) -> int | None:
    parts = text.split(",")
    if len(parts) != 2 or parts[0] != "Ready":
        return None
    if not parts[1].isdigit():
        return None
    return int(parts[1])


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
    frames = parse_section(ctx.frame_data.get("frames", {}))
    rows = [
        record
        for record in frames
        if int(record["player"]) == 1
        and hold1_at <= int(record["ms"]) <= move2_at
    ]
    hold_rows = [record for record in rows if int(record["ms"]) <= hold2_at]
    move_rows = [record for record in rows if int(record["ms"]) >= move1_at]
    bad_clip = []
    bad_len = []
    for record in rows:
        step = clip_step(str(record.get("uclip", "")))
        want = expected_step(int(record.get("pitch", 0)))
        if step is None or abs(step - want) > 1:
            bad_clip.append((int(record["ms"]), step, want))
        length = int(record.get("ulen", -1))
        if abs(length - STATIC_FRAME_MS) > 2:
            bad_len.append((int(record["ms"]), length))
    hold_steps = sorted({clip_step(str(record.get("uclip", ""))) for record in hold_rows})
    move_steps = sorted({clip_step(str(record.get("uclip", ""))) for record in move_rows})
    print(
        f"freeze animation: hold={hold_steps} move={move_steps} "
        f"bad_clip={len(bad_clip)} bad_len={len(bad_len)}"
    )
    if bad_clip:
        print(f"freeze clip mismatches: {bad_clip[:5]}")
    if bad_len:
        print(f"freeze length mismatches: {bad_len[:5]}")
    playing = not bad_clip and not bad_len
    if playing:
        print("freeze correct animation: PASS")
    else:
        print("freeze correct animation: FAIL")
        checks.failures += 1
    stable = True
    for before, after in zip(rows, rows[1:]):
        if int(before.get("pitch", 0)) != int(after.get("pitch", 0)):
            continue
        if before.get("uclip") != after.get("uclip"):
            stable = False
            break
    changed = bool(move_steps) and bool(hold_steps) and move_steps != hold_steps
    if stable and changed:
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