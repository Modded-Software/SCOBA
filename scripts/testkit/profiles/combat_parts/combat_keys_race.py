"""Keys against fast clicks, combat group `keys`: section `key_race`.

R-PNC-57, SPEC-POINT-AND-CLICK 5.8b. Operator's play 2026-11-27: with the
right button held and the left button clicking, three key downs never
reached the game. Each fell in the gap between a left-button up and the
next left-button down. The host sends that timing here (D and W), and as a
control a key down in the middle of a button hold (A and S). Every down and
up must reach the game.
"""

from __future__ import annotations

import time

from ..bank_checks import _report
from .combat_keys_log import check_host_log
from .combat_keys_real import (
    ARM_WAIT_S,
    LEFT_BUTTON,
    RIGHT_BUTTON,
    STALL_STEP,
    play,
    step_edge,
)

SECTION = "key_race"
AIM_BUTTON = RIGHT_BUTTON
SHOT_BUTTON = LEFT_BUTTON
# Rounds of each key.
ROUNDS = 15
# Keys that go down in the gap between two clicks, and the control keys.
GAP_KEYS = ("d", "w")
MID_KEYS = ("a", "s")
# Real seconds. The operator's clicks: down about 90 ms, up about 40 ms.
CLICK_S = 0.09
BETWEEN_S = 0.04
# The gap: from the button up to the key down, and on to the button down.
# The three lost downs: 39, 12, 16 ms after the up; 0, 18, 10 ms before the down.
AFTER_UP_S = 0.012
BEFORE_DOWN_S = 0.015
# The control: the key goes down this long after the button, and before its up.
MID_S = 0.045
# Index of a key in the harness counters, and the name in the checks.
KEY_INDEX = {"w": 0, "s": 1, "a": 2, "d": 3}
# Least game loops with a key down: two for each of the holds.
HELD_ROWS = 2 * 4 * ROUNDS
# Most ms, in the host key log, from the button up to a gap key down and on
# to the button down. The log reads the X server every 4 ms.
GAP_MOST_MS = 60
# The mouse moves through every round, as it does for a player who aims:
# pixels each slice, the sign flipping from one sweep to the next. Run
# combat/20261127-193353 had no mouse motion and lost no key.
SWEEP_PX = 2
# Least camera turn of the race, degrees x10, summed over the game loops.
TURN_LEAST10 = 300

_CLICK = (("bdown", SHOT_BUTTON), ("wait", CLICK_S), ("bup", SHOT_BUTTON))


def _gap_round(key: str) -> tuple[tuple, ...]:
    """A click, the key down in the gap, two more clicks, the key up."""
    return (
        *_CLICK,
        ("wait", AFTER_UP_S),
        ("kdown", key),
        ("wait", BEFORE_DOWN_S),
        *_CLICK,
        ("wait", BETWEEN_S),
        *_CLICK,
        ("wait", BETWEEN_S),
        ("kup", key),
        ("wait", BETWEEN_S),
    )


def _mid_round(key: str) -> tuple[tuple, ...]:
    """The key down in the middle of a click, two more clicks, the key up."""
    return (
        ("bdown", SHOT_BUTTON),
        ("wait", MID_S),
        ("kdown", key),
        ("wait", MID_S),
        ("bup", SHOT_BUTTON),
        ("wait", BETWEEN_S),
        *_CLICK,
        ("wait", BETWEEN_S),
        *_CLICK,
        ("wait", BETWEEN_S),
        ("kup", key),
        ("wait", BETWEEN_S),
    )


def _rounds() -> tuple[tuple, ...]:
    # D right, A left, W forward, S back: the hero stays where it is.
    steps: list[tuple] = []
    for _ in range(ROUNDS):
        steps.extend(_gap_round("d"))
        steps.extend(_mid_round("a"))
        steps.extend(_gap_round("w"))
        steps.extend(_mid_round("s"))
    # Every wait of the rounds moves the mouse, one way and then the other.
    moving: list[tuple] = []
    sign = 1
    for step in steps:
        if step[0] == "wait":
            moving.append(("sweep", step[1], sign * SWEEP_PX))
            sign = -sign
        else:
            moving.append(step)
    return tuple(moving)


RACE: tuple[tuple, ...] = (("bdown", AIM_BUTTON), ("wait", 0.4), *_rounds(), ("wait", 0.2), ("bup", AIM_BUTTON), ("wait", 0.2))


def sent_keys(steps: tuple[tuple, ...] = RACE) -> dict[str, list[int]]:
    """[downs, ups] of each key of the sequence."""
    found: dict[str, list[int]] = {}
    for step in steps:
        edge = step_edge(step)
        if edge is not None and edge[0] == "key":
            found.setdefault(edge[1], [0, 0])[0 if edge[2] else 1] += 1
    return found


def sent_presses(steps: tuple[tuple, ...] = RACE) -> dict[int, int]:
    """Downs of each mouse button of the sequence."""
    found: dict[int, int] = {}
    for step in steps:
        edge = step_edge(step)
        if edge is not None and edge[0] == "button" and edge[2]:
            found[edge[1]] = found.get(edge[1], 0) + 1
    return found


def play_race(read, driver, sleep=time.sleep, clock=time.monotonic) -> None:
    """key_race: the sequence, once the harness has armed its counters."""
    deadline = clock() + ARM_WAIT_S
    while (read() or {}).get(SECTION, {}).get("armed") != 1:
        if clock() >= deadline:
            raise RuntimeError(f"{SECTION}: the harness did not arm its counters in {ARM_WAIT_S:.0f} s")
        sleep(0.5)
    play(driver, steps=RACE, sleep=sleep)


def check_race(checks) -> None:
    values = checks.data.get(SECTION, {})
    print(f"{SECTION} raw key edges (game ms, d or u, key index): {values.get('edgeLog')}")
    print(f"{SECTION} raw: repeats={values.get('repeats')} looseUps={values.get('looseUps')} left={values.get('btnLeft')} right={values.get('btnRight')}")
    checks.true(SECTION, "", "tpsOn")
    checks.true(SECTION, "", "started")

    # R-PNC-57: every key down the host sent reaches the game.
    sent = sent_keys()
    for key in (*GAP_KEYS, *MID_KEYS):
        where = "in the gap between two clicks" if key in GAP_KEYS else "inside a click"
        downs = values.get(f"downs{KEY_INDEX[key]}")
        ups = values.get(f"ups{KEY_INDEX[key]}")
        _report(checks, f"{SECTION} {key.upper()} down {where}", downs == sent[key][0], f"seen={downs} sent={sent[key][0]}")
        _report(checks, f"{SECTION} {key.upper()} ups as sent", ups == sent[key][1], f"seen={ups} sent={sent[key][1]}")
    checks.eq(SECTION, "", "looseUps", 0)
    checks.eq(SECTION, "", "rawEnd", 0)
    checks.eq(SECTION, "", "scriptEnd", 0)

    # The script and the key triggers of the map got them as well.
    checks.eq(SECTION, "", "scriptOff", 0)
    edges = sum(downs + ups for downs, ups in sent.values())
    print(f"{SECTION} raw map triggers: key={values.get('mapKeyEdges')} any={values.get('mapAnyEdges')} button={values.get('mapBtnEdges')}")
    _report(checks, f"{SECTION} the map's key triggers got every edge", values.get("mapKeyEdges") == edges, f"seen={values.get('mapKeyEdges')} sent={edges}")

    # Engine: the hero walks while a key is down.
    rows = values.get("heldRows")
    path = values.get("path100")
    print(f"{SECTION} raw: rows={values.get('rows')} heldRows={rows} path100={path}")
    _report(checks, f"{SECTION} keys down for their loops", rows is not None and rows >= HELD_ROWS, f"rows={rows} least={HELD_ROWS}")
    walks = rows is not None and path is not None and rows > 0 and path >= rows * STALL_STEP * 100
    _report(checks, f"{SECTION} the hero walks with a key down", walks, f"path100={path} rows={rows} least per row={STALL_STEP}")

    # The arrangement: the game got the mouse motion of the sweeps.
    turn = values.get("turn10")
    _report(checks, f"{SECTION} the camera turns with the mouse", turn is not None and turn >= TURN_LEAST10, f"degrees x10={turn} least={TURN_LEAST10}")

    # The arrangement: the clicks and the aim hold took place.
    presses = sent_presses()
    _report(checks, f"{SECTION} left clicks as sent", values.get("btnLeft") == presses[SHOT_BUTTON], f"seen={values.get('btnLeft')} sent={presses[SHOT_BUTTON]}")
    _report(checks, f"{SECTION} one aim hold", values.get("btnRight") == presses[AIM_BUTTON], f"seen={values.get('btnRight')} sent={presses[AIM_BUTTON]}")
    checks.false(SECTION, "", "tpsAfter")


def gap_times(lines: list[str]) -> list[tuple[str, int, int]]:
    """Each gap key down of the host key log: (key, ms since the left-button
    up, ms to the next left-button down); -1, -1 when it was not in a gap."""
    edges: list[tuple[int, str, str]] = []
    for line in lines:
        fields = line.split()
        if len(fields) == 3 and fields[1] in ("d", "u"):
            edges.append((int(fields[0]), fields[1], fields[2]))
    shot = f"B{SHOT_BUTTON}"
    found: list[tuple[str, int, int]] = []
    for index, (ms, edge, name) in enumerate(edges):
        if edge != "d" or name not in GAP_KEYS:
            continue
        before = next((item for item in reversed(edges[:index]) if item[2] == shot), None)
        after = next((item for item in edges[index + 1 :] if item[2] == shot), None)
        if before is None or after is None or before[1] != "u" or after[1] != "d":
            found.append((name, -1, -1))
        else:
            found.append((name, ms - before[0], after[0] - ms))
    return found


def check_race_host(lines: list[str]) -> list[str]:
    """Findings of the host key log of the race; none when it shows it."""
    errors = check_host_log(lines, RACE, SECTION)
    gaps = gap_times(lines)
    print(f"{SECTION} raw host gaps (key, ms after the button up, ms before the button down): {gaps}")
    # The arrangement: the X server held each gap key down inside a gap.
    bad = [gap for gap in gaps if not (0 <= gap[1] <= GAP_MOST_MS and 0 <= gap[2] <= GAP_MOST_MS)]
    if bad or len(gaps) != len(GAP_KEYS) * ROUNDS:
        errors.append(f"{SECTION} host log: gap keys down between a button up and a button down: count={len(gaps)} want={len(GAP_KEYS) * ROUNDS} outside={bad[:6]}")
    return errors
