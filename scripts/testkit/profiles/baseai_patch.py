"""baseai profile: the A/B data patches of the probe map, chosen by the environment
(baseai_env.py): the stock 2x2 Supply Depot, and the gas radius scan (baseai_scan.py)."""

from __future__ import annotations

from pathlib import Path

from .baseai_env import depot_mode
from .baseai_scan import gas_scan, patch_scan

DEPOT_MAP = ('<CUnit id="SupplyDepot">\n        <Footprint value="Footprint4x4DepotContour"/>\n'
             '        <PlacementFootprint value="Footprint4x4Depot"/>\n    </CUnit>')
DEPOT_STOCK = ('<CUnit id="SupplyDepot">\n        <Footprint value="Footprint2x2Contour"/>\n'
               '        <PlacementFootprint value="Footprint2x2"/>\n    </CUnit>')


def _swap_unit(map_dir: Path, old_text: str, new_text: str, what: str) -> None:
    path = map_dir / "Base.SC2Data" / "GameData" / "UnitData.xml"
    raw = path.read_bytes()
    eol = b"\r\n" if b"\r\n" in raw else b"\n"
    old = old_text.encode("utf-8").replace(b"\n", eol)
    if raw.count(old) != 1:
        raise SystemExit(f"{path}: expected one {what} entry")
    path.write_bytes(raw.replace(old, new_text.encode("utf-8").replace(b"\n", eol)))


def patch_depot(map_dir: Path) -> None:
    _swap_unit(map_dir, DEPOT_MAP, DEPOT_STOCK, "SupplyDepot 4x4")


def wanted() -> bool:
    """A data patch is asked for by the environment."""
    return depot_mode() == "stock" or gas_scan() is not None


def patch_ab(map_dir: Path) -> None:
    """The A/B data probes asked for by the environment."""
    if depot_mode() == "stock":
        patch_depot(map_dir)
    scan = gas_scan()
    if scan is not None:
        patch_scan(map_dir, scan)
