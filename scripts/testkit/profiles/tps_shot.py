"""R-TPS-57, R-TPS-58, R-PNC-46 shot clock checks.

The bank values come from gf_DbgClockRead (scripts/testkit/galaxy/common.galaxy).
Tosh fires every 0.15 s, so the clocks are read in the game loop that saw
the shot effect. Used by the tps and combat profiles.
"""

from __future__ import annotations


def shot_clocks(checks, section: str, again: bool, tag: str = "tshot", bounded: bool = True) -> None:
    """One loop after the shot, the hero cooldown and the button clock run.

    They are read inside one weapon period: above 0 and, when `bounded`, at
    most the cooldown of the first enabled weapon. Kerrigan's button clock
    (1.5 s) is not that weapon's: her cases are not bounded. With `again`,
    the second click came while the cooldown ran.
    """
    period = checks.value(section, tag, "CdTimeMs")
    keys = ("ShotSeen", "EarlyCdMs", "EarlyBtnMs", "AgainCdMs", "CooldownMs", "ButtonCdMs")
    raw = {key: checks.value(section, tag, key) for key in keys}
    print(f"{section} raw clocks period={period} {raw}")
    checks.true(section, tag, "ShotSeen")
    checks.gt(section, tag, "CdTimeMs", 0)
    if bounded:
        # Tosh's weapon cooldown (operator 2026-11-27: 0.15 s; was 0.1, 0.25).
        # Galaxy fixed point holds 0.15 as 614 / 4096: 149 or 150 ms.
        checks.between(section, tag, "CdTimeMs", 149, 150)
        # The weapon clock starts one loop (62.5 ms) before the shot effect.
        # At 0.1 s it was over (-25) in the loop that saw the effect
        # (combat/20261127-105141). Started within that loop: above -62.5.
        # The button clock below is set by the effect itself.
        checks.between(section, tag, "EarlyCdMs", -62, period or 0)
        checks.between(section, tag, "EarlyBtnMs", 1, period or 0)
    else:
        checks.gt(section, tag, "EarlyCdMs", 0)
        checks.gt(section, tag, "EarlyBtnMs", 0)
    checks.true(section, tag, "EarlyCmdCd")
    if again:
        checks.gt(section, tag, "AgainCdMs", 0)
