"""Roster profile (REQ-ROSTER, SPEC-ROSTER 4).

The test launch has one person in seat 1; seats 2 and 3 stay open and
empty, so they are the unplayed seats. Every check reads the test bank:
player type, race and status, alliances, seat heroes, wave units.
Two clients and the lobby are operator checks (AC-ROSTER-1, 2).
"""

from __future__ import annotations

from pathlib import Path

import workpaths
from mapgen import player_slots
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, profile_output

ROOT = project_root()
PLAYER_TYPE_USER = 1      # c_playerTypeUser
PLAYER_TYPE_COMPUTER = 2  # c_playerTypeComputer
PLAYER_STATUS_ACTIVE = 1  # c_playerStatusActive
RACE = {"Terr": "Terr", "Zerg": "Zerg"}


def check_table(checks) -> None:
    s = "rs_table"
    for p in range(16):
        k = f"p{p}"
        print(f"{s} raw {k}: type={checks.value(s, k, 'Type')} race={checks.value(s, k, 'Race')} "
              f"status={checks.value(s, k, 'Status')} lane={checks.value(s, k, 'Lane')} owner={checks.value(s, k, 'Owner')}")
    # R-ROSTER-2: base owners, computer, active, with race; the script table agrees.
    for lane, (seat, owner, race) in player_slots.LANES.items():
        checks.eq(s, f"p{owner}", "Type", PLAYER_TYPE_COMPUTER)
        checks.eq(s, f"p{owner}", "Race", RACE[race])
        checks.eq(s, f"p{owner}", "Status", PLAYER_STATUS_ACTIVE)
        checks.eq(s, f"p{owner}", "Lane", lane)
        checks.true(s, f"p{owner}", "Owner")
        checks.eq(s, f"p{seat}", "Lane", lane)
        checks.false(s, f"p{seat}", "Owner")
    # Seat 1: the person of the test launch.
    checks.eq(s, "p1", "Type", PLAYER_TYPE_USER)
    checks.eq(s, "p1", "Status", PLAYER_STATUS_ACTIVE)
    # Negative: no other player is in the roster.
    for p in (0, 7, 8, 15):
        checks.eq(s, f"p{p}", "Lane", 0)
        checks.false(s, f"p{p}", "Owner")
    # R-ROSTER-4: allies inside a team, none across.
    print(f"{s} raw inBadPairs={checks.value(s, '', 'inBadPairs')!r} crossBadPairs={checks.value(s, '', 'crossBadPairs')!r}")
    checks.eq(s, "", "inBad", 0)
    checks.eq(s, "", "crossBad", 0)


def check_seats(checks) -> None:
    s = "rs_seats"
    print(f"{s} raw waveMs={checks.value(s, '', 'waveMs')}")
    checks.lt(s, "", "waveMs", 60000)
    for tag in ("t0", "t1"):
        for p in range(1, 7):
            k = f"{tag}p{p}"
            print(f"{s} raw {k}: " + " ".join(f"{key}={checks.value(s, k, key)}" for key in (
                "Played", "SeatHero", "Tps", "Toshes", "Wallet", "Pods", "Marines", "MarinesOrdered",
                "Zerglings", "ZerglingsOrdered")))
    # R-ROSTER-5: seat 1 played, with its hero and wallet.
    checks.true(s, "t0p1", "Played")
    checks.true(s, "t0p1", "SeatHero")
    checks.true(s, "t0p1", "Wallet")
    # Unplayed seats: no hero, no wallet, no pod (negative case).
    for p in (2, 3, 4, 5, 6):
        for tag in ("t0", "t1"):
            k = f"{tag}p{p}"
            checks.false(s, k, "Played")
            checks.false(s, k, "SeatHero")
            checks.false(s, k, "Tps")
            checks.eq(s, k, "Toshes", 0)
            checks.false(s, k, "Wallet")
            checks.eq(s, k, "Pods", 0)
    # Every lane's wave on a reinforcement, with its gate order, for played
    # and unplayed seats alike. Marines: 4 per Terran wave; Zerglings: 8.
    for p in (1, 2, 3):
        before = checks.value(s, f"t0p{p}", "Marines") or 0
        checks.gt(s, f"t1p{p}", "Marines", before + 3)
        checks.gt(s, f"t1p{p}", "MarinesOrdered", 3)
    for p in (4, 5, 6):
        before = checks.value(s, f"t0p{p}", "Zerglings") or 0
        checks.gt(s, f"t1p{p}", "Zerglings", before + 7)
        checks.gt(s, f"t1p{p}", "ZerglingsOrdered", 7)
    # Negative: the living seat 1 hero gets no pod.
    checks.eq(s, "t1p1", "Pods", checks.value(s, "t0p1", "Pods"))


def check_gate(checks) -> None:
    """R-ROSTER-9: past the X, every seat's unit heads for the enemy spawn."""
    s = "rs_gate"
    print(f"{s} raw waitMs={checks.value(s, '', 'waitMs')}")
    for i in range(4):
        k = f"c{i}"
        print(f"{s} raw {k}: " + " ".join(f"{key}={checks.value(s, k, key)!r}" for key in (
            "Seat", "Race", "Dest", "Orders", "At100")))
    for i in range(4):
        # 1: enemy spawn. -1 (own spawn, the retreat) and 0 (no order past
        # the X) both fail.
        checks.eq(s, f"c{i}", "Dest", 1)


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="roster",
        source=workpaths.path("SC2_BUILT_MAP"),
        output=profile_output("roster"),
        bank_names=PROFILE_BANKS["roster"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "roster.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/roster/common",
            "scripts/test/roster/roster",
        ),
        init_calls=("gt_RosterTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    checks.eq("rs_end", "", "RealClicks", 0)
    check_table(checks)
    check_gate(checks)
    check_seats(checks)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="roster",
        map_name="SCOBA.SC2Map",
        map_source=profile_output("roster"),
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["roster"],
        ready_section="rs_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
