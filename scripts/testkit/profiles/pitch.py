"""Dedicated 10-second aim pitch playtest profile."""

from __future__ import annotations

from pathlib import Path
import time

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="pitch",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["pitch"],
        bank_names=PROFILE_BANKS["pitch"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "pitch.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/pitch/common",
            "scripts/test/pitch/pitch",
        ),
        init_calls=("gt_PitchTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    time.sleep(2.0)
    ctx.frames.capture("pitch_entry")
    time.sleep(2.0)
    ctx.frames.capture("pitch_down")
    time.sleep(2.0)
    ctx.frames.capture("pitch_mid")
    time.sleep(2.0)
    ctx.frames.capture("pitch_up")
    time.sleep(2.0)
    ctx.frames.capture("pitch_hold")
    time.sleep(3.0)
    ctx.frames.capture("pitch_entry70")
    time.sleep(2.0)
    ctx.frames.capture("pitch_down70")
    time.sleep(2.0)
    ctx.frames.capture("pitch_up70")
    time.sleep(2.0)
    return None


def check(ctx, data: dict, checks) -> None:
    for tag in ("entry", "down", "mid", "up", "hold"):
        print(f"pitch {tag}: camera={checks.value('pitch', '', tag + 'Camera')} rest={checks.value('pitch', '', tag + 'Rest')} time={checks.value('pitch', '', tag + 'Time')}")
    checks.eq("meta", "", "done", 1)
    checks.eq("meta", "", "profile", "pitch")
    checks.between("pitch", "", "midCamera", 25, 35)
    down_time = checks.value("pitch", "", "downTime") or 0
    mid_time = checks.value("pitch", "", "midTime") or 0
    up_time = checks.value("pitch", "", "upTime") or 0
    if down_time < mid_time < up_time:
        print("pitch direction: PASS")
    else:
        print(f"pitch direction: got down={down_time} mid={mid_time} up={up_time} FAIL")
        checks.failures += 1
    if down_time <= 400 and up_time >= 9590:
        print("pitch full range: PASS")
    else:
        print(f"pitch full range: got down={down_time} up={up_time} FAIL")
        checks.failures += 1
    entry70_rest = checks.value("pitch", "", "entry70Rest") or 0
    down70_time = checks.value("pitch", "", "down70Time") or 0
    up70_time = checks.value("pitch", "", "up70Time") or 0
    if entry70_rest == -13 and down70_time <= 400 and up70_time >= 9590:
        print("pitch fixed rest at entry 70: PASS")
    else:
        print(
            f"pitch fixed rest at entry 70: got rest={entry70_rest} down={down70_time} up={up70_time} FAIL"
        )
        checks.failures += 1
    


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="pitch",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["pitch"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["pitch"],
        ready_section="pitch",
        ready_key="Ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
