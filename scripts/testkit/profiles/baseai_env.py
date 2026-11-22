"""baseai profile: the group and the environment switches of a run.

SC2_TEST_GROUP picks the group. SC2_BA_DEPOT and SC2_BA_GAS_* pick A/B data probes and gas probe
modes (SPEC-BASE-AI 8); each switch is checked here, so a typo stops the run before the build.
SC2_BA_GAS_SCAN is parsed in baseai_scan.py."""

from __future__ import annotations

import os

from .baseai_scan import SCAN_ENV

GROUPS = ("probe", "macro", "flight", "hall", "gas")
# "all" runs these; macro (about 5 min, waves on) and gas (about 4 min) run by name only.
ALL_GROUPS = ("probe", "hall")


def selected_group() -> str:
    group = os.environ.get("SC2_TEST_GROUP", "all")
    if group != "all" and group not in GROUPS:
        raise SystemExit(f"unknown baseai group: {group}; choose all or one of {', '.join(GROUPS)}")
    return group


def depot_mode() -> str:
    """SC2_BA_DEPOT=stock: the probe map gets the stock 2x2 depot footprint
    (A/B probe of the c_canLower placement). Default: the map's 4x4."""
    mode = os.environ.get("SC2_BA_DEPOT", "map")
    if mode not in ("map", "stock"):
        raise SystemExit(f"SC2_BA_DEPOT must be map or stock, got {mode}")
    return mode


def gas_help() -> int:
    """SC2_BA_GAS_HELP=1: the gas harness lets a script worker build a gas
    building on both placed geysers of every AI lane, and three script
    workers gather from each. 2: the same with the AI's own workers, not
    script controlled (does the AI leave them alone?). Default: 0, off."""
    mode = os.environ.get("SC2_BA_GAS_HELP", "0")
    if mode not in ("0", "1", "2"):
        raise SystemExit(f"SC2_BA_GAS_HELP must be 0, 1 or 2, got {mode}")
    return int(mode)


def gas_ring() -> bool:
    """SC2_BA_GAS_RING=1 (with SC2_BA_GAS_SCAN): the gas harness fills the 6x6
    square of the Terran lanes' probe geyser with stock 1x1 pathing blockers,
    and on lane 3 a script worker is ordered to build on it. Default: off."""
    mode = os.environ.get("SC2_BA_GAS_RING", "0")
    if mode not in ("0", "1"):
        raise SystemExit(f"SC2_BA_GAS_RING must be 0 or 1, got {mode}")
    if mode == "1" and not os.environ.get(SCAN_ENV):
        raise SystemExit(f"SC2_BA_GAS_RING=1 needs {SCAN_ENV}")
    return mode == "1"


def gas_extra() -> bool:
    """SC2_BA_GAS_EXTRA=1: the stock baseline probes of the gas harness (a
    stock 3x3 RichVespeneGeyser and a 6x6 VespeneGeyser near the town of
    lanes 2 and 5). Default: off, the lanes as in the game."""
    mode = os.environ.get("SC2_BA_GAS_EXTRA", "0")
    if mode not in ("0", "1"):
        raise SystemExit(f"SC2_BA_GAS_EXTRA must be 0 or 1, got {mode}")
    return mode == "1"


def gas_town() -> bool:
    """SC2_BA_GAS_TOWN=1: the gas harness declares town one of every AI lane
    again, at its hall, and places no probe geysers (does the AI's town
    point stay at the hall, and which geysers does it count then?).
    Default: off."""
    mode = os.environ.get("SC2_BA_GAS_TOWN", "0")
    if mode not in ("0", "1"):
        raise SystemExit(f"SC2_BA_GAS_TOWN must be 0 or 1, got {mode}")
    return mode == "1"
