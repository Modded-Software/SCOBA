"""Cinematic mode profile (REQ-CINEMATIC): F9 hides the UI, Shift+F9 the
16:9 bars. The look of the screen is an operator check."""

from __future__ import annotations

from pathlib import Path

import workpaths
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, profile_output

ROOT = project_root()
S = "cine"


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="cinematic",
        source=workpaths.path("SC2_BUILT_MAP"),
        output=profile_output("cinematic"),
        bank_names=PROFILE_BANKS["cinematic"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "cinematic.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/cinematic/common",
            "scripts/test/cinematic/cinematic",
        ),
        init_calls=("gt_CineTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    return


def _ui_shown(checks, tag: str, dialogs) -> None:
    checks.gt(S, tag, "Dialogs", 0)
    checks.eq(S, tag, "Dialogs", dialogs)
    checks.true(S, tag, "Minimap")
    checks.true(S, tag, "TextTags")
    checks.true(S, tag, "Reticle")
    checks.eq(S, tag, "Bars", 0)


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    for key in sorted(data.get(S, {})):
        print(f"  {key}: {data[S][key]}")
    base = checks.value(S, "base", "Dialogs")
    # Before: UI shown, mode off, no hold (R-CINE-4 baseline).
    checks.false(S, "base", "On")
    checks.false(S, "base", "InputHeld")
    _ui_shown(checks, "base", base)
    # R-CINE-6: Shift+F9 with the mode off: refused, no bars.
    checks.eq(S, "boxOff", "BoxRefused", 1)
    checks.eq(S, "boxOff", "Bars", 0)
    checks.false(S, "boxOff", "Box")
    # R-CINE-1, 2: on, everything hidden.
    checks.true(S, "on", "On")
    checks.eq(S, "on", "Dialogs", 0)
    checks.false(S, "on", "Minimap")
    checks.false(S, "on", "TextTags")
    checks.false(S, "on", "Reticle")
    checks.false(S, "on", "TpsTexts")
    checks.eq(S, "on", "Bars", 0)
    # R-CINE-3: no hold, the hero walked.
    checks.false(S, "on", "InputHeld")
    ax, bx = checks.value(S, "moveA", "X100"), checks.value(S, "moveB", "X100")
    moved = ax is not None and bx is not None and bx - ax >= 100
    print(f"cine hero moved in the mode: dx100={None if None in (ax, bx) else bx - ax} want>=100 {'PASS' if moved else 'FAIL'}")
    if not moved:
        checks.failures += 1
    # R-CINE-5, 10: bars slide in, 60 high (16:10 to 16:9).
    checks.eq(S, "box1", "Bars", 2)
    checks.eq(S, "box1", "BarH", 60)
    checks.eq(S, "box1", "BarH2", 60)
    checks.eq(S, "box1", "SlideIns", 1)
    checks.false(S, "box1", "Leaving")
    # R-CINE-10: a slide out keeps them shown, then hides them.
    checks.false(S, "box2", "Box")
    checks.eq(S, "box2", "SlideOuts", 1)
    checks.eq(S, "box2", "Bars", 2)
    checks.true(S, "box2", "Leaving")
    checks.eq(S, "box2done", "Bars", 0)
    checks.false(S, "box2done", "Leaving")
    checks.eq(S, "box3", "Bars", 2)
    checks.eq(S, "box3", "BoxToggles", 3)
    checks.eq(S, "box3", "SlideIns", 2)
    # The bars do not bring any UI back.
    checks.eq(S, "box3", "Dialogs", 0)
    # Negative: in during a slide out; the old hide must not fire.
    checks.true(S, "box5", "Box")
    checks.eq(S, "box5", "Bars", 2)
    checks.false(S, "box5", "Leaving")
    checks.eq(S, "box5", "SlideIns", 3)
    checks.eq(S, "box5", "SlideOuts", 2)
    # R-CINE-4, 7: off, bars slide out, the same UI as before.
    checks.false(S, "off", "On")
    checks.false(S, "off", "Box")
    checks.true(S, "off", "TpsTexts")
    checks.eq(S, "off", "SlideOuts", 3)
    checks.true(S, "off", "Leaving")
    checks.eq(S, "offDone", "Bars", 0)
    _ui_shown(checks, "offDone", base)
    checks.eq(S, "offDone", "Toggles", 2)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="cinematic",
        map_name="SCOBA.SC2Map",
        map_source=profile_output("cinematic"),
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["cinematic"],
        ready_section="meta",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
