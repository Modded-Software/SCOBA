"""Knobs for rule-based Zerus vegetation and lane hazards.

Other modules read these as `config.NAME`, so tests can patch them.
Distances are world units (one map cell = 1).
"""

from __future__ import annotations

from typing import NamedTuple

SEED = 20261115
MARKER = ".flora"
REPORT = "flora_report.txt"
MAP_CELLS = 256

# Ground: a cell is a wall where the slope (height per unit) exceeds WALL_SLOPE.
# Ground plants need slope below FLAT_SLOPE. Curtains need RELIEF of height
# change within RELIEF_RADIUS.
WALL_SLOPE = 0.8
FLAT_SLOPE = 0.45
RELIEF = 4.0
RELIEF_RADIUS = 3
# Water: depth bands below the water surface (map WaterData height).
GROUND_LIFT = 1.0  # placed z = computed ground + this (operator probe 2026-11-15, row F)
SHORE_BAND = 3.0  # dry cells this close to water are shore
BRAMBLE_FOREST = 2  # ZerusBrambles need this many trees within CLUSTER_RADIUS
BRAMBLE_WATER_CLEAR = 4.0  # and stay this far from water
BRAMBLE_LANE_CLEAR = 6.0  # and from any lane route
SHALLOW = 0.6  # swamp plants stand in water up to this depth
WATER_PLANT_MIN = 0.2
WATER_PLANT_MAX = 2.5

# Keep-outs (radius around the object).
KEEP_HERO = 12.0  # player 1 units and the faction heroes
HERO_UNITS = ("Kerrigan", "Tosh")
KEEP_STRUCTURE = 6.0
KEEP_UNIT = 3.0
STRUCTURE_UNITS = (
    "Hive", "GreaterNydusWorm", "HybridUltraliskShackled", "PsiDecimator", "MengskBC", "SupplyDepot",
    "SensorTower", "PerditionTurret", "AutoTurret", "KorhalPalaceTurret", "SpineCrawler", "SporeCrawler",
    "SporeCannon", "InfestedSiegeBreakerSieged", "Brakk",
)
TREE_MARGIN = 0.5  # plants keep this far outside tree blockers

# Tree clusters: a tree with at least CLUSTER_MIN neighbours within CLUSTER_RADIUS.
CLUSTER_RADIUS = 12.0
CLUSTER_MIN = 3

# Zerg accents: deadly plants within this distance of these player-8 structures.
ZERG_ACCENT_UNITS = ("SporeCannon", "SporeCrawler", "Hive", "GreaterNydusWorm", "SpineCrawler")
ZERG_ACCENT_RADIUS = 12.0

# A family: how far its own instances keep apart, its cap, its scale range.
class Family(NamedTuple):
    spacing: float
    cap: int
    scale: tuple[float, float]
    variations: int
    blocks: bool = False  # stock footprint kept (hazards); plants never block


FAMILIES: dict[str, Family] = {
    # Priority order: earlier families claim space first.
    "ZerusCliffVines": Family(3.0, 220, (0.9, 1.3), 6),
    "ZerusCurtain": Family(6.0, 40, (1.0, 1.4), 4),
    "ZerusLargeVines": Family(6.0, 60, (0.9, 1.2), 2),
    "ZerusPlantClusterLarge": Family(4.0, 80, (1.0, 1.2), 6),
    "ZerusPlantClusterMedium": Family(3.0, 150, (1.0, 1.2), 8),
    "ZerusPlantClusterSmall": Family(2.0, 250, (1.0, 1.2), 8),
    "ZerusWaterPlant": Family(3.0, 150, (0.9, 1.3), 11),
    "ZerusSwampPlantsLarge": Family(5.0, 60, (0.9, 1.2), 5),
    "ZerusSwampPlants": Family(2.5, 250, (0.9, 1.2), 7),
    "ZerusGroundVines": Family(4.0, 200, (0.95, 1.15), 4),
    "ZerusBrambles": Family(3.0, 400, (0.9, 3.0), 3),
    "ZerusTallGrassCluster": Family(3.5, 300, (0.9, 1.2), 2),
    "ZerusDeadlyPlant": Family(5.0, 16, (1.0, 1.2), 1),
    "ZerusPlant": Family(3.0, 250, (0.9, 1.1), 20),  # also replaces dry-ground reeds
    "ZerusPlantlife": Family(3.0, 120, (0.9, 1.1), 17),
}
# Two different families keep this share of their mean spacing apart.
MIX_SPACING = 0.35
# Plant cluster size by the tree's scale: below SMALL_TREE small, below LARGE_TREE medium.
SMALL_TREE = 3.5
LARGE_TREE = 5.5
# Non-blocking footprint for plants whose stock footprint would block.
NONE_FOOTPRINT = "FootprintScobaFloraNone"

# Lanes as the map's lane triggers define them (camera.galaxy gt_X*UnitOrders):
# a unit entering an X region is sent to the Zerg or the Terran spawn of that
# lane. Each lane runs Zerg spawn -> X region -> Terran spawn, split at X.
class LaneRoute(NamedTuple):
    name: str
    zerg: str  # region name
    cross: str
    terran: str


LANE_ROUTES = (
    LaneRoute("center", "Kerrigan Spawn", "X Center", "Tosh Spawn"),
    LaneRoute("top", "Dehaka Spawn", "X Top", "Raynor Spawn"),
    LaneRoute("bottom", "Stukov Spawn", "X Bottom", "Nova Spawn"),
)
FACTION_SIDES = ("Zerg", "Terran")
# Spawn and base regions are kept clear of flora and hazards, grown by this.
SPAWN_REGIONS = (
    "Tosh Spawn", "Kerrigan Spawn", "Nova Spawn", "Raynor Spawn", "Stukov Spawn", "Dehaka Spawn", "Zerg", "Terran",
)
KEEP_SPAWN = 4.0
# Zerg accent structures belong to this player.
ZERG_PLAYER = "8"
SLOPE_COST = 4.0
WATER_COST = 0.5

# Hazards: pairs at the same arc distance from the lane's river crossing, one on
# each faction's side, on the same hand of each faction's direction of travel.
class Hazard(NamedTuple):
    distance: float  # from the crossing, along the lane
    kind: str
    hand: int  # +1 left, -1 right, seen walking toward the enemy


HAZARDS = (
    Hazard(18.0, "ZerusLavaGroundCrack", 1),
    Hazard(30.0, "ZerusTarPit", -1),
    Hazard(42.0, "ZerusLavaGroundSpire", 1),
    Hazard(54.0, "ZerusLavaGroundCrack", -1),
)
HAZARD_VARIATIONS = {"ZerusLavaGroundCrack": 3, "ZerusLavaGroundSpire": 3, "ZerusTarPit": 7}
# Stock footprint half sizes, to keep the lane open (FootprintDoodad4x4 etc.).
HAZARD_HALF = {"ZerusLavaGroundCrack": 1.5, "ZerusLavaGroundSpire": 0.5, "ZerusTarPit": 2.0}
# Hazard sits this share of the lane's half clearance to the side, at most HAZARD_SIDE_MAX.
HAZARD_SIDE = 0.5
HAZARD_SIDE_MAX = 4.0
# A lane's corridor: cells this close to its route. Detours are measured inside it.
LANE_CORRIDOR = 8.0
# Shared shifts along the lane tried when a pair's spot is blocked.
HAZARD_SHIFTS = (0.0, 3.0, -3.0, 6.0, -6.0)
# A lane must stay connected with hazards in, no longer than this multiple.
LANE_DETOUR_MAX = 1.25
