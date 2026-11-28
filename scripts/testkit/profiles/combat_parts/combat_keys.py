"""WASD key checks of the combat profile (R-PNC-57 to 59).

Design and test table: SPEC-POINT-AND-CLICK 5.8a. Every check reads the test
bank. Travel is measured along the camera yaw, in map units.
"""

from __future__ import annotations

import math
import time

from ..bank_checks import _delta, _report
from .combat_keys_log import check_edge_log
from .combat_keys_race import check_race
from .combat_keys_real import check_combo
from .combat_keys_stuck import check_stuck

# Least travel of a 1 s walk. The heroes walk about 3 per second.
WALK = 1.5
# Least travel of a 1.5 s walk that starts with a turn around.
TURNED = 1.0
# Most travel of a hero that stands.
STILL = 0.3
# Most travel across the walked axis.
ACROSS = 1.0


def _travel(checks, section: str, tag_a: str, tag_b: str) -> tuple[float, float] | None:
    """Travel a->b as (forward, left) of the camera yaw at b."""
    dx = _delta(checks, section, tag_a, tag_b, "HeroX10")
    dy = _delta(checks, section, tag_a, tag_b, "HeroY10")
    yaw = checks.value(section, tag_b, "CamYaw")
    if dx is None or dy is None or yaw is None:
        return None
    rad = math.radians(yaw)
    forward = (dx * math.cos(rad) + dy * math.sin(rad)) / 10
    left = (-dx * math.sin(rad) + dy * math.cos(rad)) / 10
    return forward, left


def _walks(checks, name: str, section: str, tags: tuple[str, str], axis: tuple[int, int], least: float = WALK) -> None:
    """The hero travels at least `least` along `axis` (forward, left signs)."""
    got = _travel(checks, section, *tags)
    ok = got is not None
    if got is not None:
        for value, want in zip(got, axis):
            ok = ok and (value * want >= least if want else abs(value) < ACROSS)
    detail = "no snapshot" if got is None else f"forward={got[0]:.1f} left={got[1]:.1f} least={least}"
    _report(checks, f"{section} {tags[0]}->{tags[1]} {name}", ok, detail)


def _stands(checks, name: str, section: str, tag_a: str, tag_b: str) -> None:
    """Negative: no travel between the two snapshots."""
    got = _travel(checks, section, tag_a, tag_b)
    ok = got is not None and math.hypot(*got) <= STILL
    detail = "no snapshot" if got is None else f"forward={got[0]:.1f} left={got[1]:.1f} most={STILL}"
    _report(checks, f"{section} {tag_a}->{tag_b} {name}", ok, detail)


def _released(checks, section: str, prefix: str = "t") -> None:
    """After the release: no travel and no move order. Every key call ran."""
    _stands(checks, "no travel after the release", section, prefix + "stop", prefix + "end")
    checks.false(section, prefix + "end", "MoveOrder")
    sent = checks.value(section, "", "keysSent")
    run = checks.value(section, "", "keysRun")
    _report(checks, f"{section} {prefix} every key call ran", sent is not None and sent == run, f"sent={sent} run={run}")


FORWARD = (1, 0)
BACK = (-1, 0)
LEFT = (0, 1)
RIGHT = (0, -1)


def _key_hold(checks) -> None:
    # R-PNC-57, R-PNC-53: W down walks in Chase stand until the release.
    section = "key_hold"
    checks.eq(section, "t0000", "Root", 1)
    _walks(checks, "W walks", section, ("t0000", "tmove"), FORWARD)
    _walks(checks, "W keeps walking", section, ("tmove", "tmore"), FORWARD)
    for tag in ("tmove", "tmore"):
        checks.eq(section, tag, "Root", 0)
        checks.true(section, tag, "MoveOrder")
    _released(checks, section)
    checks.eq(section, "tend", "Root", 1)


def _key_retap(checks) -> None:
    # AC-PNC-36: W up and W down in one game loop, Chase stand.
    section = "key_retap"
    _walks(checks, "W walks on after the retap", section, ("t0000", "tmove"), FORWARD)
    checks.eq(section, "tmove", "Root", 0)
    checks.true(section, "tmove", "MoveOrder")
    _released(checks, section)
    checks.eq(section, "tend", "Root", 1)


def _key_pair(checks, section: str, first: tuple[int, int], last: tuple[int, int]) -> None:
    # R-PNC-59, AC-PNC-37: the key pressed last wins; its release gives the
    # movement back to the key still down.
    _walks(checks, "first key walks", section, ("t0000", "ta"), first)
    _walks(checks, "last key wins", section, ("ta", "tb"), last, TURNED)
    _walks(checks, "first key walks again", section, ("tb", "ta2"), first, TURNED)
    _released(checks, section)
    checks.eq(section, "tend", "Root", 1)


def _key_order(checks) -> None:
    # R-PNC-58, AC-PNC-39: W replaces a click move within one game loop.
    section = "key_order"
    before = checks.value(section, "", "clickBefore10")
    after = checks.value(section, "", "clickAfter10")
    print(f"{section} raw order target off the click point x10: before={before} after={after}")
    _walks(checks, "click move walks away", section, ("c0", "c1"), BACK, 0.8)
    _report(checks, f"{section} click move order", before is not None and 0 <= before <= 5, f"off10={before}")
    _report(checks, f"{section} W replaces the click move in one loop", after is not None and after > 20, f"off10={after}")
    _walks(checks, "W walks forward", section, ("c1", "c2"), FORWARD, TURNED)
    _released(checks, section, "c")

    # W pressed in order mode walks.
    checks.true(section, "", "m0OrderMode")
    checks.true(section, "", "m1OrderMode")
    _walks(checks, "W walks in order mode", section, ("m0", "m1"), FORWARD)
    _released(checks, section, "m")

    # W held into order mode keeps walking.
    checks.true(section, "", "h0OrderMode")
    _walks(checks, "W held into order mode", section, ("h0", "h1"), FORWARD)
    _released(checks, section, "h")


def _key_scene(checks) -> None:
    # AC-PNC-38, R-INTRO-9: W pressed in an input hold walks when it ends.
    section = "key_scene"
    checks.true(section, "", "held")
    checks.false(section, "", "heldAfter")
    _stands(checks, "no travel in the hold", section, "t0000", "thold")
    _walks(checks, "W walks when the hold ends", section, ("thold", "tfree"), FORWARD)
    _released(checks, section)

    # A down before the hold: no travel in it. Released in it: none after.
    _walks(checks, "A walks before the hold", section, ("r0", "r1"), LEFT, 0.8)
    _stands(checks, "no travel in the hold, key down", section, "r2", "r3")
    _stands(checks, "keys released in the hold", section, "r3", "r4")
    _released(checks, section, "r")


def _key_strafe(checks) -> None:
    # R-PNC-57 in strafe movement (right hold; TPS uses the same step).
    section = "key_strafe"
    open_row = str(checks.value(section, "", "reachOpen") or "")
    wall_row = str(checks.value(section, "", "reachWall") or "")
    print(f"{section} raw far points reachable (y), 30 down to 6: open={open_row} wall={wall_row}")
    print(f"{section} raw wall: count={checks.value(section, '', 'wallCount')} off10={checks.value(section, '', 'wallOff10')}")
    checks.true(section, "o0", "HoldStrafe")
    _walks(checks, "W walks in the open", section, ("o0", "o1"), FORWARD)
    _released(checks, section, "o")

    # The block leaves no far point: the arrangement of the case.
    checks.eq(section, "", "wallCount", 11)
    _report(checks, f"{section} block covers every far point", bool(wall_row) and "y" not in wall_row, f"row={wall_row}")
    checks.true(section, "w0", "HoldStrafe")
    _walks(checks, "W walks up to the block", section, ("w0", "w1"), FORWARD, 2.0)
    # Negative: it does not enter the block, 4.0 ahead.
    got = _travel(checks, section, "w0", "w1")
    detail = "no snapshot" if got is None else f"forward={got[0]:.1f}"
    _report(checks, f"{section} stops at the block", got is not None and got[0] <= 4.5, detail)
    _released(checks, section, "w")


# Real seconds the host holds the real W key. The harness walks 1 game
# second of it and waits up to 20 game seconds for each key edge.
REAL_KEY_HOLD_S = 4.0


def press_real_key(data: dict) -> None:
    """key_real: one real W key into the game window, when the harness waits."""
    if data.get("key_real", {}).get("waiting") != 1:
        return
    from ... import input_driver

    input_driver.focus()
    time.sleep(0.2)
    input_driver.key_down("w")
    try:
        time.sleep(REAL_KEY_HOLD_S)
    finally:
        input_driver.focus()
        input_driver.key_up("w")


def _key_real(checks) -> None:
    # R-PNC-57, R-PNC-58 through the real key event and the key trigger.
    section = "key_real"
    print(f"{section} raw while W is down: forward={checks.value(section, '', 'k1Forward')} inputHeld={checks.value(section, '', 'k1InputHeld')}")
    checks.true(section, "", "downSeen")
    _walks(checks, "a real W key walks", section, ("k0", "k1"), FORWARD)
    checks.true(section, "", "upSeen")
    _stands(checks, "no travel after the release", section, "kstop", "kend")
    checks.false(section, "kend", "MoveOrder")


def _key_tps(checks) -> None:
    # R-PNC-57, R-PNC-71: TPS, the mode after every touchdown.
    section = "key_tps"
    print(f"{section} raw while W is down: forward={checks.value(section, '', 'p1Forward')} inputHeld={checks.value(section, '', 'p1InputHeld')}")
    checks.true(section, "", "tpsOn")
    checks.true(section, "p0", "HoldStrafe")
    _walks(checks, "W walks in TPS", section, ("p0", "p1"), FORWARD)
    _released(checks, section, "p")
    _walks(checks, "A walks in TPS", section, ("q0", "q1"), LEFT)
    _released(checks, section, "q")
    checks.false(section, "", "tpsAfter")


def _key_spot(checks) -> None:
    # The arrangement of the group: free ground 9 each way (18 half steps).
    section = "key_spot"
    print(
        f"{section} raw free half steps, 8 directions from the camera yaw:"
        f" anchor={checks.value(section, '', 'anchorRow')} least={checks.value(section, '', 'anchorOpen')}"
        f" spot={checks.value(section, '', 'row')} ring={checks.value(section, '', 'ring')} dir={checks.value(section, '', 'dir')}"
    )
    print(f"{section} raw units ahead of the anchor: {checks.value(section, '', 'anchorAhead')}")
    checks.true(section, "", "found")


def check_keys(checks) -> None:
    _key_spot(checks)
    _key_real(checks)
    check_combo(checks)
    check_edge_log(checks)
    check_race(checks)
    _key_tps(checks)
    _key_hold(checks)
    _key_retap(checks)
    _key_pair(checks, "key_ws", FORWARD, BACK)
    _key_pair(checks, "key_ad", LEFT, RIGHT)
    _key_order(checks)
    _key_scene(checks)
    _key_strafe(checks)
    check_stuck(checks)
