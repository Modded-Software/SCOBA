"""Fast moving-attack test profile."""

from __future__ import annotations

from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="rungun",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["rungun"],
        bank_names=PROFILE_BANKS["rungun"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "rungun.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/rungun/common",
            "scripts/test/rungun/rungun",
        ),
        init_calls=("gt_RungunTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1

    checks.eq("meta", "", "done", 1)
    print(f"rungun Tosh AllowedMovement: {checks.value('rungun_start', '', 'ToshAllowedMovement')}")
    checks.eq("rungun", "t1000", "Root", 0)
    checks.displacement("rungun", "t0000", "t3000", minimum=1)
    shots = checks.value("rungun", "t3000", "AimShots")
    if shots is None or shots <= 0:
        print(f"rungun t3000 AimShots: got={shots} want>0 FAIL")
        checks.failures += 1
    period = checks.value("rungun", "shot", "WeaponPeriodMs")
    print(f"rungun shot WeaponPeriodMs: {period}")


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="rungun",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["rungun"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["rungun"],
        ready_section="rungun_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )