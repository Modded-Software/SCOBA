"""Bank check helpers shared by the combat, tps and pose profiles."""

from __future__ import annotations


def _report(checks, name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"{name}: {detail} {status}")
    checks.results.append(
        {"section": name, "tag": "", "key": "", "got": detail, "want": "", "status": status}
    )
    if not ok:
        checks.failures += 1


def _delta(checks, section: str, tag_a: str, tag_b: str, key: str):
    before = checks.value(section, tag_a, key)
    after = checks.value(section, tag_b, key)
    if before is None or after is None:
        return None
    return after - before


def _still(checks, section: str, tag_a: str, tag_b: str) -> None:
    dx = _delta(checks, section, tag_a, tag_b, "HeroX")
    dy = _delta(checks, section, tag_a, tag_b, "HeroY")
    ok = dx is not None and dy is not None and abs(dx) + abs(dy) <= 1
    _report(checks, f"{section} hero still", ok, f"dx={dx} dy={dy}")


def _no_damage(checks, section: str, tag_a: str, tag_b: str) -> None:
    delta = _delta(checks, section, tag_a, tag_b, "EnemyHp")
    _report(checks, f"{section} {tag_a}->{tag_b} no damage", delta == 0, f"hpDelta={delta}")


def _shots(checks, section: str, tag_a: str, tag_b: str, want: int) -> None:
    delta = _delta(checks, section, tag_a, tag_b, "Shots")
    _report(checks, f"{section} {tag_a}->{tag_b} shots", delta == want, f"got={delta} want={want}")
