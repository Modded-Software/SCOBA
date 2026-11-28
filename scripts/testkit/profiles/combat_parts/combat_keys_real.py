"""Real keys and mouse of the combat group `keys`: section `key_combo`.

R-PNC-57 to 59, SPEC-POINT-AND-CLICK 5.8a. The host holds real keys in pairs
in TPS and adds a camera turn, an aim and clicks while they are down. The
harness (galaxy/combat/combat_keys_real.galaxy) writes one row each game
loop. The checks read those rows: the host clock and the game clock are not
compared.
"""

from __future__ import annotations

import math
import time

from ..bank_checks import _report

SECTION = "key_combo"
# The bit of a key in the trace columns: W 1, S 2, A 4, D 8.
KEYS = ("w", "s", "a", "d")
WA = 1 | 4
SD = 2 | 8
LEFT_BUTTON = 1
MIDDLE_BUTTON = 2
RIGHT_BUTTON = 3
MARK_KEY = "m"

# Real seconds. A pair stays down under 2 s: the group has 9 free each way.
STAGGER_S = 0.15
PAUSE_S = 0.6
TURN_STEPS = 24
# Real seconds between two mouse nudges of a `sweep` step.
SWEEP_SLICE_S = 0.004
# Real seconds to wait for the harness to arm the recorder.
ARM_WAIT_S = 40.0


def _pair(first: str, second: str, *inside: tuple) -> tuple[tuple, ...]:
    """`first` down, `second` down, the steps inside, both up, a pause."""
    return (
        ("down", first),
        ("wait", STAGGER_S),
        ("down", second),
        *inside,
        ("up", second),
        ("wait", STAGGER_S),
        ("up", first),
        ("wait", PAUSE_S),
    )


def _click(button: int) -> tuple[tuple, ...]:
    return (("press", button), ("release", button))


# Each pair walks back what the pair before it walked.
SEQUENCE: tuple[tuple, ...] = (
    # A, then W (operator 2026-11-27: A and W held, the hero walked straight).
    *_pair("a", "w", ("wait", 1.6)),
    *_pair("d", "s", ("wait", 1.6)),
    # An aim starts and ends with two keys down.
    *_pair("w", "a", ("wait", 0.5), ("press", RIGHT_BUTTON), ("wait", 0.6), ("release", RIGHT_BUTTON), ("wait", 0.5)),
    # Two shots with two keys down.
    *_pair("s", "d", ("wait", 0.5), *_click(LEFT_BUTTON), ("wait", 0.4), *_click(LEFT_BUTTON), ("wait", 0.5)),
    # The camera turns with two keys down, and back.
    *_pair("w", "a", ("wait", 0.3), ("turn", 360, 1.0), ("wait", 0.3)),
    *_pair("s", "d", ("wait", 0.3), ("turn", -360, 1.0), ("wait", 0.3)),
    # A shot inside an aim.
    *_pair("w", "a", ("wait", 0.4), ("press", RIGHT_BUTTON), ("wait", 0.3), *_click(LEFT_BUTTON), ("wait", 0.3), ("release", RIGHT_BUTTON), ("wait", 0.4)),
    # The free-cursor state on and off. Then the mark key of the recorders
    # (5.8b), as the operator presses it: with the direction keys held.
    *_pair("s", "d", ("wait", 0.4), *_click(MIDDLE_BUTTON), ("wait", 0.5), *_click(MIDDLE_BUTTON), ("wait", 0.3), ("down", MARK_KEY), ("up", MARK_KEY), ("wait", 0.3)),
)


def sent_edges(steps: tuple[tuple, ...] = SEQUENCE) -> tuple[list[int], list[int]]:
    """Key downs and key ups of the sequence, by key index."""
    downs = [sum(1 for step in steps if step == ("down", key)) for key in KEYS]
    ups = [sum(1 for step in steps if step == ("up", key)) for key in KEYS]
    return downs, ups


def sent_buttons(steps: tuple[tuple, ...] = SEQUENCE) -> int:
    """Mouse button downs of the sequence: what the harness counts as clicks."""
    return sum(1 for step in steps if step[0] == "press")


# Steps that send one edge: (key or button, down). `down`, `up`, `press` and
# `release` wait 80 ms after the edge. `kdown`, `kup`, `bdown` and `bup`
# send it at once: the waits of the sequence alone set the time between
# two edges (key_race, 5.8b).
_EDGES = {
    "down": ("key", True),
    "up": ("key", False),
    "press": ("button", True),
    "release": ("button", False),
    "kdown": ("key", True),
    "kup": ("key", False),
    "bdown": ("button", True),
    "bup": ("button", False),
}
_AT_ONCE = ("kdown", "kup", "bdown", "bup")


def step_edge(step: tuple) -> tuple[str, str | int, bool] | None:
    """(`key` or `button`, name, down) of an edge step; None for the others."""
    found = _EDGES.get(step[0])
    return None if found is None else (found[0], step[1], found[1])


def _send(driver, at_once: bool, kind: str, name, down: bool) -> None:
    if kind == "key" and at_once:
        driver.key_edge(name, down)
    elif kind == "key" and down:
        driver.key_down(name)
    elif kind == "key":
        driver.key_up(name)
    elif at_once:
        driver.button_edge(name, down)
    else:
        driver.button(name, down)


def play(driver, steps: tuple[tuple, ...] = SEQUENCE, sleep=time.sleep) -> None:
    """Sends the sequence to the game window. Leaves no key or button down."""
    keys: list[str] = []
    buttons: list[int] = []
    driver.focus()
    driver.move(*driver.center_point())
    held = driver.focus_id()
    try:
        for step in steps:
            op = step[0]
            if op == "wait":
                sleep(step[1])
                continue
            if op == "sweep":
                # The time of a wait, with the mouse moving through it.
                slices = max(1, round(step[1] / SWEEP_SLICE_S))
                for _ in range(slices):
                    sleep(step[1] / slices)
                    driver.nudge(step[2], 0)
                continue
            # A key sent after the focus left the game window is typed into
            # another window, and the game releases the keys it held
            # (run combat/20261127-162040).
            now = driver.focus_id()
            if now != held:
                raise RuntimeError(f"the keyboard focus left the game window (window {held} to {now}) before {step}")
            edge = step_edge(step)
            if edge is not None:
                kind, name, down = edge
                down_now = keys if kind == "key" else buttons
                if down:
                    down_now.append(name)
                _send(driver, op in _AT_ONCE, kind, name, down)
                if not down:
                    down_now.remove(name)
            elif op == "turn":
                for _ in range(TURN_STEPS):
                    driver.nudge(step[1] // TURN_STEPS, 0)
                    sleep(step[2] / TURN_STEPS)
            else:
                raise ValueError(f"unknown step: {step}")
    finally:
        # After an error: the keys first, then the buttons.
        for key in reversed(keys):
            driver.key_up(key)
        for button in reversed(buttons):
            driver.button(button, False)


def play_combo(read, driver, sleep=time.sleep, clock=time.monotonic) -> None:
    """key_combo: the sequence, once the harness has armed the recorder.

    `read` returns the test bank as a dict, or None while it cannot be read.
    """
    deadline = clock() + ARM_WAIT_S
    while "clicks0" not in (read() or {}).get(SECTION, {}):
        if clock() >= deadline:
            raise RuntimeError(f"{SECTION}: the harness did not arm the recorder in {ARM_WAIT_S:.0f} s")
        sleep(0.5)
    play(driver, sleep=sleep)


# Rows after a key edge that are not judged: the hero turns and speeds up.
GRACE = 4
# Rows in a row that make a finding: 0.25 game seconds.
RUN = 4
# Least travel of one game loop of a walking hero. A walk is about 0.19.
STALL_STEP = 0.03
# Most degrees between the travel of one loop and the heading of the keys.
OFF_DEG = 30.0
# Most degrees between the mean travel of a pair and its heading.
MEAN_DEG = 20.0
# Least judged rows of each pair: about 2.5 game seconds of the 4 holds.
PAIR_ROWS = 40
# Least camera turn with keys down, degrees, summed over the rows.
TURNED_DEG = 40
# Least rows in aim with a key down.
AIM_ROWS = 4


def trace_rows(values: dict) -> list[tuple[int, ...]]:
    """Rows (keys, script keys, flags, aim, move order, x100, y100, yaw)."""
    rows: list[tuple[int, ...]] = []
    for index in range(int(values.get("chunks") or 0)):
        for item in str(values.get(f"trace{index}") or "").split(";"):
            fields = item.split()
            if len(fields) == 8:
                rows.append(tuple(int(field) for field in fields))
    return rows


def key_heading(bits: int) -> float | None:
    """Degrees left of the camera yaw the keys ask for; None with no heading."""
    forward = (bits & 1) - ((bits >> 1) & 1)
    left = ((bits >> 2) & 1) - ((bits >> 3) & 1)
    if forward == 0 and left == 0:
        return None
    return math.degrees(math.atan2(left, forward))


def _angle_off(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _longest(marks: list[bool]) -> tuple[int, int]:
    """(length, first index) of the longest run of marked rows."""
    best = (0, -1)
    run = 0
    for index, mark in enumerate(marks):
        run = run + 1 if mark else 0
        if run > best[0]:
            best = (run, index - run + 1)
    return best


def analyse(rows: list[tuple[int, ...]]) -> dict:
    """What the rows show. Travel is judged against the keys the game saw."""
    count = len(rows)
    stall = [False] * count
    off = [False] * count
    travel: dict[int, list[float]] = {}
    judged: dict[int, int] = {}
    turned = 0
    aim_rows = 0
    for index in range(1, count):
        keys, _script, _flags, aim, _order, x100, y100, yaw = rows[index]
        before = rows[index - 1]
        if keys != 0:
            turned += round(_angle_off(yaw, before[7]))
            aim_rows += 1 if aim else 0
        want = key_heading(keys)
        settled = index >= GRACE and all(rows[index - back][0] == keys for back in range(1, GRACE + 1))
        if want is None or not settled:
            continue
        dx = (x100 - before[5]) / 100.0
        dy = (y100 - before[6]) / 100.0
        rad = math.radians(yaw)
        forward = dx * math.cos(rad) + dy * math.sin(rad)
        left = -dx * math.sin(rad) + dy * math.cos(rad)
        judged[keys] = judged.get(keys, 0) + 1
        total = travel.setdefault(keys, [0.0, 0.0])
        total[0] += forward
        total[1] += left
        if math.hypot(dx, dy) < STALL_STEP:
            stall[index] = True
        elif _angle_off(math.degrees(math.atan2(left, forward)), want) > OFF_DEG:
            off[index] = True
    return {
        "rows": count,
        "script": [index for index, row in enumerate(rows) if row[1] != row[0]],
        "flags": [index for index, row in enumerate(rows) if row[2] != row[0]],
        "stall": _longest(stall),
        "off": _longest(off),
        "travel": travel,
        "judged": judged,
        "turned": turned,
        "aim_rows": aim_rows,
    }


def _show(rows: list[tuple[int, ...]], first: int, name: str) -> None:
    """Raw rows around a finding, so a failure shows what the engine did."""
    if first < 0:
        return
    start = max(0, first - GRACE)
    for index in range(start, min(len(rows), first + 8)):
        print(f"{SECTION} raw {name} row {index}: keys={rows[index][0]} script={rows[index][1]} flags={rows[index][2]} aim={rows[index][3]} order={rows[index][4]} x100={rows[index][5]} y100={rows[index][6]} yaw={rows[index][7]}")


def _pair_travel(checks, got: dict, name: str, bits: int) -> None:
    want = key_heading(bits)
    rows = got["judged"].get(bits, 0)
    forward, left = got["travel"].get(bits, [0.0, 0.0])
    heading = math.degrees(math.atan2(left, forward)) if rows else None
    _report(checks, f"{SECTION} {name} held together", rows >= PAIR_ROWS, f"rows={rows} least={PAIR_ROWS}")
    ok = heading is not None and want is not None and _angle_off(heading, want) <= MEAN_DEG and math.hypot(forward, left) >= rows * STALL_STEP
    detail = "no rows" if heading is None else f"forward={forward:.1f} left={left:.1f} heading={heading:.0f} want={want:.0f}"
    _report(checks, f"{SECTION} {name} travels on the heading of both keys", ok, detail)


def check_combo(checks) -> None:
    values = checks.data.get(SECTION, {})
    rows = trace_rows(values)
    got = analyse(rows)
    print(f"{SECTION} raw key edges (game ms, d or u, key index): {values.get('edgeLog')}")
    print(f"{SECTION} raw: rows={got['rows']} repeats={values.get('repeats')} judged={got['judged']} turned={got['turned']} aimRows={got['aim_rows']}")
    checks.true(SECTION, "", "tpsOn")
    checks.true(SECTION, "", "started")
    _report(checks, f"{SECTION} trace complete", got["rows"] > 0 and got["rows"] == values.get("rows"), f"rows={got['rows']} written={values.get('rows')}")

    # The keys the game saw are the keys the host sent: none more, none less.
    downs, ups = sent_edges()
    seen_downs = [values.get(f"downs{index}") for index in range(4)]
    seen_ups = [values.get(f"ups{index}") for index in range(4)]
    _report(checks, f"{SECTION} key downs as sent", seen_downs == downs, f"seen={seen_downs} sent={downs}")
    _report(checks, f"{SECTION} key ups as sent", seen_ups == ups, f"seen={seen_ups} sent={ups}")
    checks.eq(SECTION, "", "looseUps", 0)
    checks.eq(SECTION, "", "rawEnd", 0)
    checks.eq(SECTION, "", "scriptEnd", 0)

    # R-PNC-57: the script holds a key down for as long as it is down.
    for key, name in (("script", "script key state follows the keys"), ("flags", "direction flags follow the keys")):
        bad = got[key]
        _report(checks, f"{SECTION} {name}", not bad, f"rows off={len(bad)} first={bad[:6]}")
        _show(rows, bad[0] if bad else -1, key)

    _pair_travel(checks, got, "W+A", WA)
    _pair_travel(checks, got, "S+D", SD)
    for key, name in (("stall", "no stall with a key down"), ("off", "no stretch off the heading of the keys")):
        length, first = got[key]
        _report(checks, f"{SECTION} {name}", length < RUN, f"longest={length} at row={first} most={RUN - 1}")
        if length >= RUN:
            _show(rows, first, key)

    # The arrangement: the aim, the camera turn and the clicks took place.
    _report(checks, f"{SECTION} aim with a key down", got["aim_rows"] >= AIM_ROWS, f"rows={got['aim_rows']} least={AIM_ROWS}")
    _report(checks, f"{SECTION} camera turned with a key down", got["turned"] >= TURNED_DEG, f"degrees={got['turned']} least={TURNED_DEG}")
    before = values.get("clicks0")
    after = values.get("clicks1")
    clicks = None if before is None or after is None else after - before
    _report(checks, f"{SECTION} mouse buttons as sent", clicks == sent_buttons(), f"seen={clicks} sent={sent_buttons()}")
    sent_by = [sum(1 for step in SEQUENCE if step == ("press", button)) for button in (LEFT_BUTTON, MIDDLE_BUTTON, RIGHT_BUTTON)]
    print(f"{SECTION} raw button downs (left, middle, right): seen={[values.get(key) for key in ('btnLeft', 'btnMiddle', 'btnRight')]} sent={sent_by}")

    # The stuck recorder of the map (5.8b) heard the same keys: its key
    # state never differed from the script's, and the hero never stood.
    for key, name in (("keyOffs", "recorder key state follows the real keys"), ("stucks", "no stuck entry with the keys down")):
        first = values.get(key + "0")
        last = values.get(key + "1")
        _report(checks, f"{SECTION} {name}", first is not None and last == first, f"before={first} after={last}")

    checks.false(SECTION, "cend", "MoveOrder")
    checks.false(SECTION, "", "tpsAfter")
