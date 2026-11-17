"""Aim near-DOF tuning profile (REQ-CAMERA-DOF R-DOF-2).

Cycles 5 labelled near-DOF candidates with aim on. The blur is an operator
check; the program checks only that aim was on and every candidate ran.
"""

from __future__ import annotations

from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="aimdof",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["aimdof"],
        bank_names=PROFILE_BANKS["aimdof"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "aimdof.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/aimdof/common",
            "scripts/test/aimdof/aimdof",
        ),
        init_calls=("gt_AimDofTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    checks.eq("ad_end", "", "RealClicks", 0)
    for k in (str(i) for i in range(1, 11)):
        raw = str(checks.value("ad", "", k) or "")
        parts = raw.split(",")
        ok = len(parts) == 5 and abs(int(parts[3]) - 100) <= 10 and parts[4] == "1"
        print(f"ad candidate {k} arm 1 and aiming (blur: operator check) raw={raw} {'PASS' if ok else 'FAIL'}")
        if not ok:
            checks.failures += 1


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="aimdof",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["aimdof"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["aimdof"],
        ready_section="ad_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
