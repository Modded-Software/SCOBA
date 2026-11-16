"""pncprobe verdicts: run validity, then the report of the selected group."""

from __future__ import annotations

from typing import Callable

from ...checks import Checks
from .attach import print_attach
from .click import CLICK_PROBE_PRESSES, print_click, print_hit, print_warp
from .hover import print_hover, print_recenter, print_recentre, print_rotate, print_scale
from .ray import check_point, print_ray
from .shots import print_shots

# A group report: prints the raw lines, may add verdicts to checks.
Report = Callable[[dict, Checks], None]


def _point(data: dict, checks: Checks) -> None:
    check_point(data.get("hover", {}), checks)


# Enemy Marine at 1, 2, 4, 8, 13 (d0-d4) and 30 (d5) east of Tosh, weapon
# range 14. The script in-range check ignores the hero facing (the native
# does not: pncprobe 20261116-145031) and measures distance only.
INRANGE_STATES = ("rest", "away", "aim", "shot")


def _inrange(data: dict, checks: Checks) -> None:
    raw = data.get("inrange", {})
    for key in sorted(raw):
        print(f"  {key}: {raw[key]}")
    for d in range(6):
        want = 1 if d < 5 else 0
        for state in INRANGE_STATES:
            row = str(raw.get(f"d{d}{state}", "")).split()
            got = int(row[row.index("script") + 1]) if "script" in row else None
            verdict = "PASS" if got == want else "FAIL"
            print(f"inrange d{d}{state} script: got={got} want={want} {verdict}")
            if verdict == "FAIL":
                checks.failures += 1
        # The probe aimed the crosshair at the Marine: the pick must see it.
        for state in ("rest", "aim"):
            row = str(raw.get(f"d{d}{state}", "")).split()
            got = int(row[row.index("pick") + 1]) if "pick" in row else None
            verdict = "PASS" if got == 1 else "FAIL"
            print(f"inrange d{d}{state} pick: got={got} want=1 {verdict}")
            if verdict == "FAIL":
                checks.failures += 1


def _report(fn: Callable[[dict], None]) -> Report:
    return lambda data, _checks: fn(data)


# Group -> report. "all" is the shot, walk and spawn-scan run. "picklog" has
# no scenario and no end: it is launched for manual play, never checked.
GROUP_REPORTS: dict[str, Report] = {
    "all": _report(print_shots),
    "hover": _report(print_hover),
    "recenter": _report(print_recenter),
    "click": _report(print_click),
    "warp": _report(print_warp),
    "hit": _report(print_hit),
    "rotate": _report(print_rotate),
    "recentre": _report(print_recentre),
    "scale": _report(print_scale),
    "ray": _report(print_ray),
    "look": _report(print_ray),
    "point": _point,
    "inrange": _inrange,
    "attach": _report(print_attach),
}


def check(ctx, data: dict, checks, group: str) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    # The click probe presses the left button itself, once per case
    # (operator approval for this group only). Every other group: none.
    checks.eq("done", "tend", "RealClicks", CLICK_PROBE_PRESSES if group == "click" else 0)
    GROUP_REPORTS[group](data, checks)
