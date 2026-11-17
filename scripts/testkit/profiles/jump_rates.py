"""Jump takeoff burst, clip time scales and landing recovery (R-JUMP-22)."""

from __future__ import annotations

import re

from project_root import project_root

from .bank_checks import _report

ROOT = project_root()
# Strafe and backpedal walk clips vs the stock walk rate (operator 2026-11-16).
STRAFE_RATE = 1.25
# Landing clip (c_JUMP_LAND_TIME) and the speed burst of a walk jump (BehaviorData SCOBAJumpBurst).
LAND_MS = 250
JUMP_CORE = ROOT / "src" / "SCOBA.SC2Map" / "scripts" / "app" / "core" / "jump.galaxy"
BEHAVIOR_DATA = ROOT / "src" / "SCOBA.SC2Map" / "Base.SC2Data" / "GameData" / "BehaviorData.xml"


def burst_speeds() -> tuple[float | None, float | None]:
    """SCOBAJumpBurst MoveSpeedMultiplier in the data, and c_JUMP_BURST_SPEED in the script."""
    data = re.search(r'<CBehaviorBuff id="SCOBAJumpBurst">.*?MoveSpeedMultiplier="([0-9.]+)"', BEHAVIOR_DATA.read_text(encoding="utf-8"), re.S)
    script = re.search(r"const fixed c_JUMP_BURST_SPEED = ([0-9.]+);", JUMP_CORE.read_text(encoding="utf-8"))
    return (float(data.group(1)) if data else None, float(script.group(1)) if script else None)


BURST = burst_speeds()[0] or 0.0


def check_rates(checks, section: str, walk: bool, aim: bool = False) -> None:
    """R-JUMP-22: takeoff burst, clip time scales, and a short landing.

    Walk jump: the burst raises the engine move speed at the press and is
    gone at the end; Start plays at the walk clip rate with the burst, End
    at the walk clip rate; Air at 1. Stand jump (negative): no burst, all 1."""
    v = {k: checks.value(section, "", k) for k in (
        "pressSpeed100", "burstSpeed100", "endSpeed100", "burstCount", "endBurstCount", "bursts",
        "startScale100", "landScale100", "pressStock100", "pressStep1000", "landMs", "doneMs")}
    scales = [int(x) for x in (checks.value(section, "", "scaleLog") or "").split(";") if x]
    steps = [int(x) for x in (checks.value(section, "", "steps") or "").split()]
    print(f"{section} rates: {v} scaleLog={scales} steps={steps}")
    checks.eq(section, "", "bursts", 1 if walk else 0)
    checks.eq(section, "", "burstCount", 1 if walk else 0)
    checks.eq(section, "", "endBurstCount", 0)
    # The engine speed property does not show the burst buff (jump/20261117-014046:
    # 310 at press and during the burst); engine travel below proves the burst.
    # The property is only asserted unchanged; raw values are reported.
    press, burst, end = v["pressSpeed100"], v["burstSpeed100"], v["endSpeed100"]
    ok = None not in (press, burst, end) and abs(end - press) <= 2
    _report(checks, f"{section} move speed property is back at the end", ok, f"press={press} burst={burst} end={end}")
    data_burst, script_burst = burst_speeds()
    _report(checks, f"{section} burst speed in script matches the data", data_burst is not None and data_burst == script_burst, f"data={data_burst} script={script_burst}")
    stock = v["pressStock100"]
    rate = None if stock is None else stock * (STRAFE_RATE if aim else 1.0)
    want = [100, 100, 100] if not walk or rate is None else [rate * BURST, 100, rate]
    ok = len(scales) >= 3 and all(abs(got - exp) <= 4 for got, exp in zip(scales, want))
    _report(checks, f"{section} clip time scales Start, Air, End", ok, f"scales={scales[:3]} want={[round(x) for x in want]}")
    if walk:
        # Engine position: the first loops after the press are faster than
        # the walk before it; the last sampled loops are not.
        before = v["pressStep1000"]
        ok = before is not None and len(steps) >= 12 and max(steps[:3]) >= 1.2 * before
        _report(checks, f"{section} hero moves faster at the push-off", ok, f"before={before} first={steps[:3]}")
        ok = before is not None and len(steps) >= 12 and max(steps[8:12]) <= 1.1 * before + 3
        _report(checks, f"{section} burst is over in the air", ok, f"before={before} later={steps[8:12]}")
    # Landing recovery: the End clip length over its time scale; never the old 400 ms.
    land, done, scale = v["landMs"], v["doneMs"], v["landScale100"]
    took = None if None in (land, done) or land < 0 or done < 0 else done - land
    want_ms = None if not scale else LAND_MS * 100.0 / scale
    ok = None not in (took, want_ms) and want_ms - 70 <= took <= want_ms + 70 and took < 380
    _report(checks, f"{section} landing recovery is short", ok, f"took={took}ms want={want_ms}")
