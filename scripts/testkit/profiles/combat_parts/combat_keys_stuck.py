"""Checks of the stuck recorder, combat group `keys`, section `key_stuck`.

SPEC-POINT-AND-CLICK 5.8b. The recorder is
`systems/recorders/move_log.galaxy` of the shipped map. The harness reads
its counters at tags a to h and the text of its last `stuck` entry.
"""

from __future__ import annotations

import math

from ..bank_checks import _report

SECTION = "key_stuck"
# Least travel of a 1.5 s walk. The heroes walk about 3 per second.
WALK = 1.5
# Most travel of a hero that stands.
STILL = 0.3
# Least movement steps of the script in the 1.5 s the hero stood: 24 loops.
STEPS = 8
# Least entries of one case: the `stuck` entry, its 32 `before` rows and
# one `edges` entry.
ENTRIES = 34


def entry_fields(text) -> dict[str, str]:
    """The `name=value` fields of a recorder entry."""
    fields: dict[str, str] = {}
    for token in str(text or "").split():
        name, sep, value = token.partition("=")
        if sep:
            fields.setdefault(name, value)
    return fields


def _count(checks, name: str, tag_a: str, tag_b: str, key: str, want: int) -> None:
    before = checks.value(SECTION, tag_a, key)
    after = checks.value(SECTION, tag_b, key)
    got = None if before is None or after is None else after - before
    _report(checks, f"{SECTION} {tag_a}->{tag_b} {name}", got == want, f"{key} got={got} want={want}")


def _travel(checks, tag_a: str, tag_b: str) -> float | None:
    values = [checks.value(SECTION, tag, key) for tag in (tag_a, tag_b) for key in ("HeroX10", "HeroY10")]
    if any(value is None for value in values):
        return None
    return math.hypot(values[2] - values[0], values[3] - values[1]) / 10


def check_stuck(checks) -> None:
    text = checks.value(SECTION, "", "stuckText")
    print(f"{SECTION} raw stuck entry: {text}")

    # Negative: a stand with no key, and a walk on free ground.
    _count(checks, "no entry for a stand with no key", "a", "b", "Stucks", 0)
    walked = _travel(checks, "f0", "f1")
    _report(checks, f"{SECTION} f0->f1 W walks", walked is not None and walked >= WALK, f"travel={walked} least={WALK}")
    _count(checks, "no entry for a walk", "b", "c", "Stucks", 0)

    # W down and the hero stunned: it stands, the script still steps.
    stood = _travel(checks, "f1", "s1")
    _report(checks, f"{SECTION} f1->s1 the stunned hero stands", stood is not None and stood <= STILL, f"travel={stood} most={STILL}")
    _count(checks, "one stuck entry", "c", "d", "Stucks", 1)
    for key in ("Steps", "Ticks"):
        before = checks.value(SECTION, "c", key)
        after = checks.value(SECTION, "d", key)
        got = None if before is None or after is None else after - before
        _report(checks, f"{SECTION} c->d the script kept stepping: {key}", got is not None and got >= STEPS, f"got={got} least={STEPS}")
    before = checks.value(SECTION, "c", "Seq")
    after = checks.value(SECTION, "d", "Seq")
    got = None if before is None or after is None else after - before
    _report(checks, f"{SECTION} c->d entry, its rows and its edges written", got is not None and got >= ENTRIES, f"got={got} least={ENTRIES}")
    # The edge log: W down is one edge; none while it stays down.
    _count(checks, "W down is one key edge", "b", "c", "KeyEdges", 1)
    _count(checks, "no key edge while W stays down", "c", "d", "KeyEdges", 0)

    # The entry names what holds the hero and what the keys were.
    fields = entry_fields(text)
    for name, want in (("stun", "1"), ("raw", "1"), ("keys", "1"), ("flags", "1"), ("held", "0"), ("alive", "1")):
        _report(checks, f"{SECTION} stuck entry {name}", fields.get(name) == want, f"got={fields.get(name)} want={want}")
    for name in ("order0", "path", "behaviors", "near", "steps", "ticks", "jump", "moveSup", "scene"):
        _report(checks, f"{SECTION} stuck entry has {name}", name in fields, f"present={name in fields}")
    # Negative: the key events and the script agreed, so no `keys` entry.
    _count(checks, "no keys entry while both agree", "c", "d", "KeyOffs", 0)

    # Once per case. The stun ends: the hero walks and one `free` is written.
    _count(checks, "no second entry while it stands", "d", "e", "Stucks", 0)
    _count(checks, "one free entry", "e", "f", "Frees", 1)
    freed = _travel(checks, "s1", "s2")
    _report(checks, f"{SECTION} s1->s2 walks when the stun ends", freed is not None and freed >= WALK, f"travel={freed} least={WALK}")

    # Negative: a turn-around walks out and back; it is not a stand
    # (combat/20261127-162040 wrote an entry for each one).
    _count(checks, "no entry for a turn-around", "i", "j", "Stucks", 0)

    # A key the script holds and no key event gave: one `keys` entry.
    _count(checks, "one keys entry", "g", "h", "KeyOffs", 1)

    # Negative: the any-key and button triggers hear real input only. This
    # section sends none.
    _count(checks, "no any-key edge from script keys", "a", "h", "AnyEdges", 0)
    _count(checks, "no button edge from script keys", "a", "h", "BtnEdges", 0)
