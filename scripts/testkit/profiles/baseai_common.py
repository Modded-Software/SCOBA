"""baseai profile: keys, constants and report helpers shared by the group checks."""

from __future__ import annotations

PLAYER_TYPE_COMPUTER = 2  # c_playerTypeComputer
PLAYER_STATUS_ACTIVE = 1  # c_playerStatusActive
WORKERS = 12
DIFFICULTY = 10  # c_skirChInsane
# The Terran owner also holds its two placed Supply Depots, 8 each (R-BASE-29).
PLACED_DEPOTS = 2
SNAP_KEYS = ("Workers", "Minerals", "Vespene", "MinCollected", "GasCollected", "SupplyUsed", "SupplyMade",
             "Structures", "Army", "StructureTypes", "ArmyTypes", "Spread100", "WorkerOrders", "Difficulty",
             "TownState", "Supply", "SupplyLow", "AllWorkerOrders", "BuildOrder", "PlaceDepotLow", "PlaceDepotStd",
             "PlaceRax", "PlaceDepotNear", "DepotAllowed")


def _raw(checks, s: str, prefix: str, keys: tuple[str, ...]) -> None:
    print(f"{s} raw {prefix}: " + " ".join(f"{k}={checks.value(s, prefix, k)}" for k in keys))


def _ok(checks, s: str, name: str, ok: bool, detail: str) -> None:
    print(f"{s} {name}: {detail} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1
