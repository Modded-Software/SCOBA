"""Base AI profile (REQ-BASE-AI, SPEC-BASE-AI 6): the wiring of the test map and the run.

The groups and their checks:
  probe   baseai_probe.py   engine assumptions A1, A3-A8 on a harness-made base
  macro   baseai_macro.py   all six owners under real conditions
  flight  baseai_flight.py  the Alt+4 regular unit
  hall    baseai_hall.py    the measured Command Center footprint
  gas     baseai_gas.py     6x6 geysers (R-BASE-35), the map's gas orders (R-BASE-36)
Switches: baseai_env.py. Data patches: baseai_patch.py, baseai_scan.py.
"""

from __future__ import annotations

from pathlib import Path

import workpaths
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from . import baseai_patch
from .baseai_env import (
    ALL_GROUPS,
    GROUPS,
    gas_extra,
    gas_help,
    gas_ring,
    gas_town,
    selected_group,
)
from .baseai_flight import check_flight_group
from .baseai_gas import check_gas
from .baseai_hall import check_hall
from .baseai_macro import check_macro
from .baseai_probe import check_probe
from .registry import PROFILE_BANKS, profile_output

ROOT = project_root()
GALAXY = ROOT / "scripts" / "testkit" / "galaxy"
# Include order: a module calls only what comes before it (or what it declares).
HARNESS = ("baseai", "baseai_live", "baseai_macro", "baseai_land", "baseai_feel", "baseai_flight", "baseai_hall",
           "baseai_gas", "baseai_gas_build", "baseai_gas_probe", "baseai_gas_help", "baseai_gas_map",
           "baseai_gas_main")

CHECKS = {
    "probe": check_probe,
    "macro": check_macro,
    "flight": check_flight_group,
    "hall": check_hall,
    "gas": check_gas,
}


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        patch=baseai_patch.patch_ab if baseai_patch.wanted() else None,
        profile="baseai",
        source=workpaths.path("SC2_BUILT_MAP"),
        output=profile_output("baseai"),
        bank_names=PROFILE_BANKS["baseai"],
        galaxy_files=(GALAXY / "common.galaxy",) + tuple(GALAXY / "baseai" / f"{name}.galaxy" for name in HARNESS),
        galaxy_includes=("scripts/test/baseai/common",) + tuple(f"scripts/test/baseai/{name}" for name in HARNESS),
        init_calls=((f'gv_dbgGroup = "{selected_group()}";',)
                    + (("gv_bgHelp = true;",) if gas_help() else ())
                    + (("gv_bgHelpOwn = true;",) if gas_help() == 2 else ())
                    + (("gv_bgRing = true;",) if gas_ring() else ())
                    + (("gv_bgTown = true;",) if gas_town() else ())
                    + (("gv_bgExtraOn = true;",) if gas_extra() else ())
                    + ("gt_BaseAiTest_Init();",)),
    )


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    group = selected_group()
    if group == "macro":
        # The operator flies the Wraith: input is expected; the macro checks
        # read AI engine state only.
        print(f"ba_end raw RealClicks={checks.value('ba_end', '', 'RealClicks')} (operator input, not asserted)")
    else:
        checks.eq("ba_end", "", "RealClicks", 0)
    print(f"group: {group}")
    for name in GROUPS:
        if (group == "all" and name in ALL_GROUPS) or group == name:
            CHECKS[name](checks)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="baseai",
        map_name="SCOBA.SC2Map",
        map_source=profile_output("baseai"),
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["baseai"],
        ready_section="ba_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
