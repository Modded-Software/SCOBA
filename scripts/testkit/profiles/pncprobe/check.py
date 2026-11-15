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
