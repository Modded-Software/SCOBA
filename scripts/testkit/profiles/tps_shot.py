"""R-TPS-57, R-TPS-58, R-PNC-46 shot clock checks.

The bank values come from gf_DbgClockRead (scripts/testkit/galaxy/common.galaxy).
Tosh fires every 0.25 s, so the clocks are read one game loop after the
shot effect. Used by the tps and combat profiles.
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
        checks.between(section, tag, "EarlyCdMs", 1, period or 0)
        checks.between(section, tag, "EarlyBtnMs", 1, period or 0)
    else:
        checks.gt(section, tag, "EarlyCdMs", 0)
        checks.gt(section, tag, "EarlyBtnMs", 0)
    checks.true(section, tag, "EarlyCmdCd")
    if again:
        checks.gt(section, tag, "AgainCdMs", 0)
