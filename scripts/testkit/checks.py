"""Shared assertion reporting for test profiles."""

from __future__ import annotations

from pathlib import Path

from .frames import FrameCollector


class Checks:
    def __init__(self, data: dict) -> None:
        self.data = data
        self.failures = 0
        self.results: list[dict[str, int | str | float | bool | None]] = []

    def value(self, section: str, tag: str, key: str):
        return self.data.get(section, {}).get(tag + key)

    def _record(self, section: str, tag: str, key: str, got, want) -> None:
        ok = got == want if isinstance(want, (bool, int, str)) else got is want
        status = "PASS" if ok else "FAIL"
        print(f"{section} {tag} {key}: got={got} want={want} {status}")
        self.results.append(
            {
                "section": section,
                "tag": tag,
                "key": key,
                "got": got,
                "want": want,
                "status": status,
            }
        )
        if not ok:
            self.failures += 1

    def eq(self, section: str, tag: str, key: str, want) -> None:
        self._record(section, tag, key, self.value(section, tag, key), want)

    def true(self, section: str, tag: str, key: str) -> None:
        self.eq(section, tag, key, True)

    def false(self, section: str, tag: str, key: str) -> None:
        self.eq(section, tag, key, False)

    def gt(self, section: str, tag: str, key: str, floor: float) -> None:
        got = self.value(section, tag, key)
        ok = got is not None and got > floor
        status = "PASS" if ok else "FAIL"
        print(f"{section} {tag} {key}: got={got} want>{floor} {status}")
        self.results.append(
            {"section": section, "tag": tag, "key": key, "got": got, "want": f">{floor}", "status": status}
        )
        if not ok:
            self.failures += 1

    def lt(self, section: str, tag: str, key: str, ceiling: float) -> None:
        got = self.value(section, tag, key)
        ok = got is not None and got < ceiling
        status = "PASS" if ok else "FAIL"
        print(f"{section} {tag} {key}: got={got} want<{ceiling} {status}")
        self.results.append(
            {"section": section, "tag": tag, "key": key, "got": got, "want": f"<{ceiling}", "status": status}
        )
        if not ok:
            self.failures += 1

    def displacement(self, section: str, tag_a: str, tag_b: str, minimum: int = 2) -> None:
        ax = self.value(section, tag_a, "HeroX") or 0
        ay = self.value(section, tag_a, "HeroY") or 0
        bx = self.value(section, tag_b, "HeroX") or 0
        by = self.value(section, tag_b, "HeroY") or 0
        got = abs(bx - ax) + abs(by - ay)
        ok = got >= minimum
        status = "PASS" if ok else "FAIL"
        print(f"{section} {tag_a}->{tag_b} displacement: got={got} want>={minimum} {status}")
        self.results.append(
            {
                "section": section,
                "tag": f"{tag_a}->{tag_b}",
                "key": "displacement",
                "got": got,
                "want": f">={minimum}",
                "status": status,
            }
        )
        if not ok:
            self.failures += 1

    def damage(self, section: str, tag_before: str, tag_after: str) -> None:
        before = self.value(section, tag_before, "EnemyHp")
        after = self.value(section, tag_after, "EnemyHp")
        ok = before is not None and after is not None and after < before
        status = "PASS" if ok else "FAIL"
        print(f"{section} {tag_before}->{tag_after} EnemyHp: before={before} after={after} want damage {status}")
        self.results.append(
            {
                "section": section,
                "tag": f"{tag_before}->{tag_after}",
                "key": "EnemyHp",
                "got": after,
                "want": "damage",
                "status": status,
            }
        )
        if not ok:
            self.failures += 1

    def between(self, section: str, tag: str, key: str, low, high) -> None:
        got = self.value(section, tag, key)
        ok = got is not None and low <= got <= high
        status = "PASS" if ok else "FAIL"
        print(f"{section} {tag} {key}: got={got} want={low}..{high} {status}")
        self.results.append(
            {"section": section, "tag": tag, "key": key, "got": got, "want": f"{low}..{high}", "status": status}
        )
        if not ok:
            self.failures += 1

    def decrease(self, section: str, tag_before: str, tag_after: str, key: str) -> None:
        before = self.value(section, tag_before, key)
        after = self.value(section, tag_after, key)
        ok = before is not None and after is not None and after < before
        status = "PASS" if ok else "FAIL"
        print(f"{section} {tag_before}->{tag_after} {key}: before={before} after={after} want decrease {status}")
        self.results.append(
            {
                "section": section,
                "tag": f"{tag_before}->{tag_after}",
                "key": key,
                "got": after,
                "want": "decrease",
                "status": status,
            }
        )
        if not ok:
            self.failures += 1

    def frame_diff(
        self,
        name: str,
        first: Path,
        second: Path,
        box: tuple[float, float, float, float],
        minimum: int,
    ) -> None:
        got = FrameCollector.difference(first, second, box)
        ok = got >= minimum
        status = "PASS" if ok else "FAIL"
        print(f"{name} frameDiff: got={got} want>={minimum} {status}")
        self.results.append(
            {"section": name, "tag": "", "key": "frameDiff", "got": got, "want": f">={minimum}", "status": status}
        )
        if not ok:
            self.failures += 1
