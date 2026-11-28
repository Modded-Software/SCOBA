"""Engine probes for WASD / Point & Click: map and run specs.

The probes record raw engine values for unconfirmed engine assumptions.
The only verdicts are run validity, and the point group checks. The raw
lines are the output. Reports live in the sibling modules; check.py maps
each group to its report.
"""

from __future__ import annotations

import os
from pathlib import Path

import workpaths
from project_root import project_root

from ...map_builder import TestMapSpec
from ...runner import TestRunSpec
from ..registry import PROFILE_BANKS, profile_output
from . import check as check_mod

ROOT = project_root()
GALAXY = ROOT / "scripts" / "testkit" / "galaxy"

GROUPS = ("hover", "recenter", "click", "warp", "hit", "rotate", "recentre", "scale", "ray", "look", "point", "inrange", "roach", "picklog", "attach")
# Galaxy sources in include order. shotprobe holds the group "all" probes;
# pncprobe holds the trigger and the group dispatch, so it comes last.
GALAXY_FILES = (
    "common", "hoverprobe", "recenterprobe", "clickprobe", "hitprobe", "rotateprobe", "recentreprobe",
    "scaleprobe", "rayprobe", "lookprobe", "pointprobe", "inrangeprobe", "roachprobe", "picklog", "attachprobe", "shotprobe", "pncprobe",
)


def selected_group() -> str:
    """`all` runs the shot, walk and spawn-scan probes. Every other group runs alone.

    `picklog` builds a map that only logs while the operator plays. It has no
    scenario and no end: launch it with `scripts/playtest.sh picklog`, never
    through the runner.
    """
    group = os.environ.get("SC2_TEST_GROUP", "all")
    if group != "all" and group not in GROUPS:
        raise SystemExit(f"unknown pncprobe group: {group}; choose all or one of {', '.join(GROUPS)}")
    return group


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="pncprobe",
        source=workpaths.path("SC2_BUILT_MAP"),
        output=profile_output("pncprobe"),
        bank_names=PROFILE_BANKS["pncprobe"],
        galaxy_files=tuple(GALAXY / f"{name}.galaxy" for name in GALAXY_FILES),
        galaxy_includes=tuple(f"scripts/test/pncprobe/{name}" for name in GALAXY_FILES),
        init_calls=(f'gv_dbgGroup = "{selected_group()}";', "gt_PncProbe_Init();"),
    )


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    check_mod.check(ctx, data, checks, selected_group())


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="pncprobe",
        map_name="SCOBA.SC2Map",
        map_source=profile_output("pncprobe"),
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["pncprobe"],
        ready_section="meta",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
