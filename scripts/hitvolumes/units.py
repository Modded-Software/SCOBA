"""The unit types that can exist on the map.

Map sources (unit_types): every CUnit of the built map's UnitData.xml, every
placed unit in Objects, and every unit type named in a unit-create call of
the map scripts or of the test harness. Stock source (stock_unit_types):
every CUnit of the stock data stack the map depends on (resolve.STACK, the
melee and campaign mods), less templates and missiles. Together they cover
units the AI trains and units an ability spawns.
"""

from __future__ import annotations

import re
from pathlib import Path

from .resolve import Catalog, stock_paths

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


def flag(catalog: Catalog, ident: str, name: str) -> bool:
    """A FlagArray value along the parent chain, nearest and latest first."""
    for cur in catalog.chain(ident):
        for el in reversed(catalog.entries[cur]):
            for f in el.findall("FlagArray"):
                if f.get("index") == name and f.get("value") is not None:
                    return f.get("value") == "1"
    return False


def concrete(catalog: Catalog) -> list[str]:
    """Unit ids that are neither a template (default="1") nor a missile."""
    out = []
    for ident, els in catalog.entries.items():
        if any(el.get("default") == "1" for el in els):
            continue
        if flag(catalog, ident, "Missile"):
            continue
        out.append(ident)
    return sorted(out)


def stock_unit_types(stock_dir: Path) -> list[str]:
    """Every concrete CUnit of the extracted stock stack."""
    return concrete(Catalog(stock_paths(stock_dir, "unit"), ("CUnit",)))
