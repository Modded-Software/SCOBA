"""pncprobe `roach` group: a close Roach must be in range (operator 2026-11-27).

Heroes h0 Tosh and h1 Kerrigan. Cases d0-d6 put the Roach 0.5 to 6 from the
hero centre, d7 at 16 (negative). `pod`: a ZergDropPod 30 behind Tosh,
a Roach 3 ahead (aim log marks 2 to 5). `walk` is the closest the engine let the
hero walk into the Roach. Each case reads the script check in TPS and in
aim, then fires one aim shot. The verdict uses the centre distance the
engine reports: a Roach centre within weapon range is in range whatever its
Radius. Raw rows are printed so a failure shows what the engine did.
"""

from __future__ import annotations

from ...checks import Checks

HEROES = (0, 1)
CASES = 8
NEGATIVE = 7


def _fields(row: str) -> dict[str, str]:
    parts = str(row).split()
    return dict(zip(parts[0::2], parts[1::2]))


def _verdict(checks: Checks, label: str, got, want) -> None:
    verdict = "PASS" if got == want else "FAIL"
    print(f"roach {label}: got={got} want={want} {verdict}")
    if verdict == "FAIL":
        checks.failures += 1


def _case(raw: dict, checks: Checks, tag: str, negative: bool) -> None:
    rows = {state: _fields(raw.get(f"{tag}{state}", "")) for state in ("tps", "aim")}
    shot = _fields(raw.get(f"{tag}shot", ""))
    aim = rows["aim"]
    if "dist" not in aim or "wRange" not in aim:
        _verdict(checks, f"{tag} recorded", 0, 1)
        return
    in_reach = float(aim["dist"]) <= float(aim["wRange"])
    if negative:
        _verdict(checks, f"{tag} negative case out of reach", in_reach, False)
    want = "1" if in_reach else "0"
    for state in ("tps", "aim"):
        _verdict(checks, f"{tag}{state} script", rows[state].get("script"), want)
        _verdict(checks, f"{tag}{state} pick", rows[state].get("pick"), "1")
    damage = float(shot.get("damage", "nan"))
    _verdict(checks, f"{tag} shot damage > 0", damage > 0.0, in_reach)
    _verdict(checks, f"{tag} shot proxy", shot.get("proxy"), "0" if in_reach else "1")


def print_roach(data: dict, checks: Checks) -> None:
    raw = data.get("roach", {})
    for key in sorted(raw):
        print(f"  {key}: {raw[key]}")
    for h in HEROES:
        for d in range(CASES):
            _case(raw, checks, f"h{h}d{d}", d == NEGATIVE)
        _case(raw, checks, f"h{h}walk", False)
    # Aim log marks 2 to 5: a ZergDropPod behind the hero won the pick.
    # The Roach 3 ahead must be picked, in range, and take the shot.
    pod = _fields(raw.get("podRaw", ""))
    _verdict(checks, "pod spawned", pod.get("valid"), "1")
    _verdict(checks, "pod not picked", pod.get("pickPod"), "0")
    _case(raw, checks, "pod", False)
