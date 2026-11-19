"""UI panel profile (REQ-UI-PANELS).

XP and level-ups must not close the stats or abilities panel. A closed
panel stays closed. Another player's XP does not touch player 1's panels.
The last stat point keeps the stats panel open; a spend at 0 points does
nothing. Visibility is engine state (DialogIsVisible).
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
        profile="ui",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["ui"],
        bank_names=PROFILE_BANKS["ui"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "ui.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/ui/common",
            "scripts/test/ui/ui",
        ),
        init_calls=("gt_UiTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    return


def _open(checks, section: str, tag: str, stats: int, abil: int) -> None:
    checks.eq(section, tag, "Stats", stats)
    checks.eq(section, tag, "Abil", abil)
    checks.eq(section, tag, "Col", abil)


def _derived(checks, key: str, got) -> None:
    """Computed values go to a 'derived' section so the summary lists them."""
    checks.data.setdefault("derived", {})[key] = got


def _level_up(checks, section: str, before: str, after: str) -> None:
    lb = checks.value(section, before, "Level")
    la = checks.value(section, after, "Level")
    got = None if lb is None or la is None else la - lb
    _derived(checks, f"{section}LevelGain", got)
    checks.eq("derived", "", f"{section}LevelGain", 1)


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    checks.eq("meta", "", "hero", 1)
    checks.eq("ui_end", "", "RealClicks", 0)

    # R-UI-1: stats open through XP without level-up.
    _open(checks, "xp_stats", "open", 1, 0)
    _open(checks, "xp_stats", "after", 1, 0)
    checks.eq("xp_stats", "after", "Xp", 10)

    # R-UI-1: stats open through a level-up, 3 points added.
    _open(checks, "lvl_stats", "after", 1, 0)
    _level_up(checks, "lvl_stats", "open", "after")
    checks.eq("lvl_stats", "after", "StatPts", 3)

    # R-UI-1: abilities panel and key column open through XP and a level-up.
    _open(checks, "abil", "open", 0, 1)
    _open(checks, "abil", "xp", 0, 1)
    _open(checks, "abil", "lvl", 0, 1)
    _level_up(checks, "abil", "xp", "lvl")

    # R-UI-2 (negative): closed panels stay closed; HUD buttons show.
    _open(checks, "closed", "before", 0, 0)
    _open(checks, "closed", "after", 0, 0)
    _level_up(checks, "closed", "before", "after")
    checks.eq("closed", "after", "StatsBtn", 1)
    checks.eq("closed", "after", "AbilBtn", 1)

    # R-UI-4 (negative): player 2 does not close player 1's panels.
    _open(checks, "other", "open", 1, 1)
    _open(checks, "other", "after", 1, 1)

    # R-UI-3: last point keeps the panel open; no spend at 0 points.
    checks.eq("spend", "", "first", 1)
    checks.eq("spend", "", "last", 1)
    checks.eq("spend", "last", "Stats", 1)
    checks.eq("spend", "last", "StatPts", 0)
    checks.eq("spend", "", "empty", 0)
    checks.eq("spend", "empty", "Stats", 1)
    checks.eq("spend", "empty", "StatPts", 0)

    # R-UI-4: toggles and the close button still work.
    _open(checks, "toggle", "statsOn", 1, 0)
    _open(checks, "toggle", "statsOff", 0, 0)
    _open(checks, "toggle", "abilOn", 0, 1)
    _open(checks, "toggle", "abilOff", 0, 0)
    _open(checks, "toggle", "abilClose", 0, 0)

    # R-UI-1 integration: a real kill awards XP; both panels stay open.
    checks.eq("kill", "", "enemyDead", 1)
    _open(checks, "kill", "open", 1, 1)
    _open(checks, "kill", "after", 1, 1)
    xp = checks.value("kill", "after", "Xp")
    lb = checks.value("kill", "open", "Level")
    la = checks.value("kill", "after", "Level")
    awarded = xp is not None and la is not None and lb is not None and (xp > 0 or la > lb)
    print(f"kill raw: xp={xp} level {lb}->{la}")
    _derived(checks, "killXpAwarded", awarded)
    checks.true("derived", "", "killXpAwarded")


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="ui",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["ui"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["ui"],
        ready_section="ui_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
