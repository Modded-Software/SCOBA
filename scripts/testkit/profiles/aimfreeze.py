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


def check(ctx, data: dict, checks) -> None:
    checks.eq("meta", "", "done", 1)
    checks.eq("meta", "", "profile", "aimfreeze")
    for tag in ("entry", "hold1", "hold2", "move1", "move2"):
        print(
            f"freeze {tag}: time={checks.value('freeze', '', tag + 'Time')} "
            f"camera={checks.value('freeze', '', tag + 'Camera')}"
        )
    hold1_time = checks.value("freeze", "", "hold1Time")
    hold2_time = checks.value("freeze", "", "hold2Time")
    if hold1_time == hold2_time:
        print("freeze stationary target: PASS")
    else:
        print(f"freeze stationary target: got {hold1_time} -> {hold2_time} FAIL")
        checks.failures += 1
    move1_time = checks.value("freeze", "", "move1Time")
    if move1_time is not None and move1_time != hold1_time:
        print("freeze pitch change target: PASS")
    else:
        print(f"freeze pitch change target: got {hold1_time} -> {move1_time} FAIL")
        checks.failures += 1
    hold1_at = checks.value("freeze", "", "hold1At") or 0
    hold2_at = checks.value("freeze", "", "hold2At") or 0
    move1_at = checks.value("freeze", "", "move1At") or 0
    move2_at = checks.value("freeze", "", "move2At") or 0
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
    hold_uplayed = [int(record.get("uplayed", -1)) for record in hold_rows]
    hold_ufid = [int(record.get("ufid", -1)) for record in hold_rows]
    move_uplayed = [int(record.get("uplayed", -1)) for record in move_rows]
    move_ufid = [int(record.get("ufid", -1)) for record in move_rows]
    print(
        f"freeze hold rows={len(hold_rows)} uplayed={sorted(set(hold_uplayed))} "
        f"ufid={sorted(set(hold_ufid))}"
    )
    print(
        f"freeze move rows={len(move_rows)} uplayed={sorted(set(move_uplayed))} "
        f"ufid={sorted(set(move_ufid))}"
    )
    hold_uclip = sorted({str(record.get("uclip", "")) for record in hold_rows})
    print(f"freeze hold uclip={hold_uclip}")
    if hold_uclip == ["Ready"]:
        print("freeze upper clip: PASS")
    else:
        print(f"freeze upper clip: {hold_uclip} FAIL")
        checks.failures += 1
    if any(value > 0 for value in hold_ufid):
        print(f"freeze upper playing: ufid={sorted(set(hold_ufid))} PASS")
    else:
        print(f"freeze upper playing: ufid={sorted(set(hold_ufid))} FAIL")
        checks.failures += 1
    if len(set(hold_ufid)) == 1 and hold_ufid[0] > 0:
        print(f"freeze stationary upper frame: ufid={hold_ufid[0]} PASS")
    else:
        print(f"freeze stationary upper frame: ufid={sorted(set(hold_ufid))} FAIL")
        checks.failures += 1
    hold_lfid = [int(record.get("lfid", -1)) for record in hold_rows]
    if len(set(hold_lfid)) > 1:
        print(f"freeze stationary lower moving: {sorted(set(hold_lfid))} PASS")
    else:
        print(f"freeze stationary lower moving: {sorted(set(hold_lfid))} FAIL")
        checks.failures += 1
    if set(move_uplayed) != set(hold_uplayed) or set(move_ufid) != set(hold_ufid):
        print("freeze pitch change upper time: PASS")
    else:
        print("freeze pitch change upper time: unchanged FAIL")
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