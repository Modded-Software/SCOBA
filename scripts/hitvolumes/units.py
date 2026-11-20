"""The unit types that can exist on the map, from the map's own files.

Sources: every CUnit of the built map's UnitData.xml, every placed unit in
Objects, and every unit type named in a unit-create call of the map scripts
or of the test harness. A unit an ability spawns from stock data is not
listed; the pick reports such a type once at run time (SPEC-TPS 5.8).
"""

from __future__ import annotations

import re
from pathlib import Path

CUNIT_RE = re.compile(r'<CUnit id="([^"]+)"')
PLACED_RE = re.compile(r'UnitType="([^"]+)"')
CREATE_RE = re.compile(
    r'(?:CreateUnits\w*|UnitCreateFacingPoint|UnitCreate|gf_CreateSpawnGroup|gf_DbgTpsPick|gf_ProbeHoverInit)\s*\(\s*[^,()]*,\s*"([A-Za-z0-9_]+)"'
)
CONST_RE = re.compile(r'const string (c_\w+_UNIT) = "([A-Za-z0-9_]+)";')
CONST_USE_RE = re.compile(r'(?:CreateUnits\w*|UnitCreateFacingPoint|UnitCreate)\s*\(\s*[^,()]*,\s*(c_\w+_UNIT)\b')


def script_types(paths: list[Path]) -> set[str]:
    texts = [p.read_text(encoding="utf-8") for p in paths]
    consts: dict[str, str] = {}
    for text in texts:
        consts.update(CONST_RE.findall(text))
    found: set[str] = set()
    for text in texts:
        found.update(CREATE_RE.findall(text))
        found.update(consts[name] for name in CONST_USE_RE.findall(text) if name in consts)
    return found


def unit_types(map_dir: Path, harness_dir: Path) -> list[str]:
    data = map_dir / "Base.SC2Data" / "GameData" / "UnitData.xml"
    found = set(CUNIT_RE.findall(data.read_text(encoding="utf-8")))
    found.update(PLACED_RE.findall((map_dir / "Objects").read_text(encoding="utf-8")))
    scripts = sorted((map_dir / "scripts").rglob("*.galaxy")) + sorted(harness_dir.rglob("*.galaxy"))
    found.update(script_types(scripts))
    return sorted(found)
