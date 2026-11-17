"""TPS mouse-mode send checks (SPEC-TPS 5.3), part of tps group cursor."""

from __future__ import annotations

from .bank_checks import _delta, _report


def _sends(checks, section: str, tag_a: str, tag_b: str, want: int) -> None:
    for key in ("RelSends", "CurSends"):
        got = _delta(checks, section, tag_a, tag_b, key)
        _report(checks, f"{section} {tag_a}->{tag_b} {key}", got == want, f"got={got} want={want}")


def check_sends(checks) -> None:
    """SPEC-TPS 5.3: mouse look and cursor reach the engine once per change."""
    s = "tps_sends"
    # TPS: mouse look on, cursor hidden, as sent.
    for tag in ("ttps", "taims", "tsame", "tback"):
        checks.true(s, tag, "SentRelative")
        checks.false(s, tag, "SentCursor")
        checks.true(s, tag, "ControlRelative")
        checks.false(s, tag, "CursorVisible")
    # Ten aim cycles and two calls that change nothing: no send.
    _sends(checks, s, "ttps", "taims", 0)
    _sends(checks, s, "taims", "tsame", 0)
    # A middle click: one send of each, cursor shown, mouse look off.
    _sends(checks, s, "tsame", "tmid", 1)
    for tag in ("tmid", "tmidaim"):
        checks.false(s, tag, "SentRelative")
        checks.true(s, tag, "SentCursor")
        checks.true(s, tag, "CursorVisible")
        checks.false(s, tag, "AimActive")
    # Negative: a right press in the free-cursor state sends nothing.
    _sends(checks, s, "tmid", "tmidaim", 0)
    # The second middle click: one send of each, back to mouse look.
    _sends(checks, s, "tmidaim", "tback", 1)
    # Leaving TPS frees the cursor.
    checks.false(s, "tend", "SentRelative")
    checks.true(s, "tend", "SentCursor")
