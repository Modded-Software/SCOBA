"""Checks of the two input logs in combat group `keys`, section `key_combo`.

SPEC-POINT-AND-CLICK 5.8b. The game's edge log is
`systems/recorders/move_log_keys` of the shipped map. The host key log is
`testkit/host_keys.py`; it runs for the time of the host's sequence. Both
must show the sequence, edge for edge.
"""

from __future__ import annotations

import re

from ... import host_keys
from ..bank_checks import _report
from .combat_keys_real import SECTION, SEQUENCE, step_edge
from .combat_keys_stuck import entry_fields

# Name of the four keys in the game's edge log, by the host's key name.
GAME_NAMES = {"w": "W", "s": "S", "a": "A", "d": "D"}
# The game's key codes (c_keyW ... in the stock natives.galaxy): the any-key
# trigger names a key `k<code>`.
GAME_CODES = {"w": 35, "s": 31, "a": 13, "d": 16, "m": 25}
# Bits of S and D in the `raw` and `keys` fields of a recorder entry.
SD_BITS = "10"
# Least travel in the mark's window with two keys down. A walk: about 1.5.
MARK_TRAVEL = 0.5
# Least entries of the mark: the entry, 160 rows before, one `edges` entry.
MARK_ENTRIES = 162

_EDGE = re.compile(r"^\d+([du])([A-Z]\d?|k\d+)$")
# Taps of one key in a row: n downs and n ups with no other edge between.
_TAPS = re.compile(r"^\d+r(k\d+)\*(\d+)from\d+$")


def edge_counts(text) -> dict[str, int]:
    """Edges of the game's log by name: dW, uW, dk35, uk35, dB1, ..."""
    found: dict[str, int] = {}
    for token in str(text or "").split():
        match = _EDGE.match(token)
        if match:
            name = match.group(1) + match.group(2)
            found[name] = found.get(name, 0) + 1
            continue
        match = _TAPS.match(token)
        if match:
            for edge in "du":
                found[edge + match.group(1)] = found.get(edge + match.group(1), 0) + int(match.group(2))
    return found


def sent_counts(steps: tuple[tuple, ...] = SEQUENCE) -> dict[str, int]:
    """The edges the game's log must hold for the host's sequence."""
    want: dict[str, int] = {}
    for step in steps:
        if step[0] in ("down", "up"):
            edge = step[0][0]
            names = [f"{edge}k{GAME_CODES[step[1]]}"]
            if step[1] in GAME_NAMES:
                names.append(edge + GAME_NAMES[step[1]])
        elif step[0] in ("press", "release"):
            names = [("d" if step[0] == "press" else "u") + f"B{step[1]}"]
        else:
            continue
        for name in names:
            want[name] = want.get(name, 0) + 1
    return want


def sent_host_counts(steps: tuple[tuple, ...] = SEQUENCE) -> dict[str, list[int]]:
    """[downs, ups] the host key log must hold, by its own names."""
    want: dict[str, list[int]] = {}
    for step in steps:
        edge = step_edge(step)
        if edge is None:
            continue
        name = str(edge[1]) if edge[0] == "key" else f"B{edge[1]}"
        want.setdefault(name, [0, 0])[0 if edge[2] else 1] += 1
    return want


def _pick(counts: dict[str, int], prefix: str) -> dict[str, int]:
    return {name: count for name, count in sorted(counts.items()) if name[1:].startswith(prefix)}


def check_edge_log(checks) -> None:
    values = checks.data.get(SECTION, {})
    text = values.get("moveEdges")
    print(f"{SECTION} raw game edge log (game ms, d or u, name): {text}")
    print(f"{SECTION} raw mark entry: {values.get('markText')}")
    got = edge_counts(text)
    want = sent_counts()

    # The game got every edge the host sent, by each of its three triggers.
    four = {name: count for name, count in sorted(got.items()) if name[1:] in GAME_NAMES.values()}
    four_want = {name: count for name, count in sorted(want.items()) if name[1:] in GAME_NAMES.values()}
    _report(checks, f"{SECTION} edge log: four keys as sent", four == four_want, f"seen={four} sent={four_want}")
    any_want = _pick(want, "k")
    any_got = {name: count for name, count in _pick(got, "k").items() if name in any_want}
    _report(checks, f"{SECTION} edge log: any-key edges as sent", any_got == any_want, f"seen={any_got} sent={any_want}")
    _report(checks, f"{SECTION} edge log: button edges as sent", _pick(got, "B") == _pick(want, "B"), f"seen={_pick(got, 'B')} sent={_pick(want, 'B')}")
    # Negative: no key the host did not send.
    other = {name: count for name, count in _pick(got, "k").items() if name not in any_want}
    _report(checks, f"{SECTION} edge log: no key the host did not send", bool(text) and not other, f"seen={other}")

    # The real M with S and D down: one mark, with the keys, the travel,
    # the 10 s of rows before and the edges.
    first = values.get("marks0")
    last = values.get("marks1")
    marks = None if first is None or last is None else last - first
    _report(checks, f"{SECTION} one mark by the real M", marks == 1, f"got={marks} want=1")
    fields = entry_fields(values.get("markText"))
    held = (fields.get("raw"), fields.get("keys"))
    _report(checks, f"{SECTION} mark has S and D down", held == (SD_BITS, SD_BITS), f"raw={held[0]} keys={held[1]} want={SD_BITS}")
    try:
        travel = float(fields.get("travel", ""))
    except ValueError:
        travel = None
    _report(checks, f"{SECTION} mark has the travel", travel is not None and travel >= MARK_TRAVEL, f"travel={travel} least={MARK_TRAVEL}")
    first = values.get("seq0")
    last = values.get("seq1")
    entries = None if first is None or last is None else last - first
    _report(checks, f"{SECTION} mark wrote its rows and edges", entries is not None and entries >= MARK_ENTRIES, f"entries={entries} least={MARK_ENTRIES}")


def check_host_log(lines: list[str], steps: tuple[tuple, ...] = SEQUENCE, section: str = SECTION) -> list[str]:
    """Findings of the host key log of a sequence; none when it shows it."""
    errors = []
    got = host_keys.counts(lines)
    want = sent_host_counts(steps)
    print(f"{section} raw host key log [downs, ups]: seen={dict(sorted(got.items()))} sent={dict(sorted(want.items()))}")
    focus = host_keys.focus_changes(lines)
    print(f"{section} raw host focus changes (ms, window, game): {focus}")
    if not any(game for _ms, _window, game in focus):
        errors.append(f"{section} host log: the game window never had the focus: changes={focus}")
    # The X server held every key and button the host sent, none else.
    if got != want:
        errors.append(f"{section} host log: key and button edges as sent: seen={dict(sorted(got.items()))} sent={dict(sorted(want.items()))}")
    left = [change for change in focus if not change[2]]
    if left:
        errors.append(f"{section} host log: the focus left the game window: {left}")
    x_errors = [line for line in lines if " xerror " in line]
    if x_errors:
        errors.append(f"{section} host log: X errors: {x_errors[:4]}")
    return errors
