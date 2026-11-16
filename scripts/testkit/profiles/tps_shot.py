"""R-TPS-57, R-TPS-58 clock checks of the tps shot scenarios.

The bank values come from scripts/testkit/galaxy/tpsclock.galaxy. Tosh fires
every 0.25 s, so the clocks are read one game loop after the shot effect.
"""

from __future__ import annotations


def shot_clocks(checks, section: str, again: bool) -> None:
    """One loop after the shot, the hero cooldown and the button clock run.

    They are read inside one weapon period: above 0 and at most the weapon
    cooldown. With `again`, the second click came while the cooldown ran.
    """
    period = checks.value(section, "tshot", "CdTimeMs")
    keys = ("EarlyCdMs", "EarlyBtnMs", "AgainCdMs", "CooldownMs", "ButtonCdMs")
    raw = {key: checks.value(section, "tshot", key) for key in keys}
    print(f"{section} raw clocks period={period} {raw}")
    checks.gt(section, "tshot", "CdTimeMs", 0)
    checks.between(section, "tshot", "EarlyCdMs", 1, period or 0)
    checks.between(section, "tshot", "EarlyBtnMs", 1, period or 0)
    checks.true(section, "tshot", "EarlyCmdCd")
    if again:
        checks.gt(section, "tshot", "AgainCdMs", 0)
