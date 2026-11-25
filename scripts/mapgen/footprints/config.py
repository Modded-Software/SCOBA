"""Knobs and fixed names. Other modules read these as `config.NAME`, so tests can patch them."""

from __future__ import annotations

from project_root import project_root

SLICES = project_root() / "scripts" / "data" / "footprint_slices.json"
MARKER = ".scaled_footprints"
REPORT = "footprint_report.txt"

# World height of a walking unit's feet. Raise FEET_LOW to leave out the root flare.
FEET_LOW = 0.05
FEET_HIGH = 0.35
FEET_SAMPLES = 4

# Pathing grid found by the fprot probe, and the fill sampling inside one sub-cell.
SUB = 0.5
SAMPLES_PER_SUB = 4
# A sub-cell blocks when at least this share of it is mesh.
COVERAGE = 0.5
# Units keep their centre one radius off a blocker, so the visible blocked
# area is the Shape grown by that radius. The mesh is shrunk by it first
# (operator, 2026-11-15: blockers looked about 1.75x too large by area).
ERODE = 0.375

# Build fails when a tree blocker covers less of the (eroded) mesh, or blocks
# more than this multiple of the mesh area plus one cell. Below
# MIN_CHECKED_MESH the 0.5 grid cannot follow the outline, so coverage is not checked.
MIN_MESH_COVERED = 0.5
MAX_BLOCKED_RATIO = 1.5
MIN_CHECKED_MESH = 1.0

TREE_TYPE = "ZerusTree"
# The map's ModelData sets VariationCount 12; placed trees name 0-14. A
# variation >= 12 may show its own model or the wrapped one: fill both.
TREE_VARIATION_COUNT = 12
SPORE_UNITS = ("SporeCannon", "SporeCrawler")
# Units with a fixed square blocker, side in cells (operator, 2026-11-20:
# 12x12 for the caged ultralisk, "increase the blocking and terrain
# flattening footprint"; its hit shapes reach 5 to 6.8 from the centre. Before, 2026-11-19:
# 8x8 for the caged ultralisk).
SQUARE_UNITS = {"HybridUltraliskShackled": 12}
# Square units also flatten the terrain under their footprint, with the stock
# core.sc2mod deformers that buildings use (UseUnitFootprint). Operator,
# 2026-11-19.
FLATTEN_EVENTS = (
    ("UnitBirth.{u}.Normal", "Create BuildingTerrainFlatten"),
    ("UnitBirth.{u}.Suppressed", "Create BuildingTerrainFlattenInstant"),
    ("UnitBirth.{u}.EditorPlaced", "Create BuildingTerrainFlattenEditor"),
)
# Units that keep their own footprint and flatten the terrain under it the
# same way (operator 2026-11-20: "the geysers also need a terrain flattening
# actor to match"). The geyser footprint is FootprintScobaGeyser6x6 (R-BASE-35).
FLATTEN_UNITS = ("VespeneGeyser",)
# Halls with a measured leg footprint (R-FP-10): unit -> measured model group.
# All three show the model entry CommandCenter and are drawn at one scale
# (operator 2026-11-20; check_halls). Before, the Orbital Command and the
# Planetary Fortress kept FootprintSCOBAHall1x1 and blocked nothing.
HALL_UNITS = {"CommandCenter": "CommandCenter", "OrbitalCommand": "CommandCenter", "PlanetaryFortress": "CommandCenter"}
# The map shows the classic Command Center model (scripts/hdtex/sc2/classic_skins.py).
# The legs are still those measured on the stock model: operator 2026-11-20,
# "it's got pretty much the same 4 legs, enable pathblocking". Off: the hall
# keeps FootprintSCOBAHall1x1 and blocks no pathing.
HALL_FOOTPRINTS_ON = True
# A hall cell blocks when this many of its four 0.5 sub-cells block.
HALL_SUBCELLS = 2
# Unit facing in degrees, as the engine reports it in the map: every
# grounded CC (SCV-built, created, landed, starting) has UnitGetFacing
# -135 = 225 (baseai hall run 20261119-211246, raw). Liberty UnitData
# says Facing 315; both are 45 degrees off the model axes. The
# engine draws the model turned by Facing - MODEL_FORWARD; a structure's
# footprint is not turned, so the turn is baked into the hall footprint.
# Operator 2026-11-19: the unturned feet sat 45 degrees off the drawn ones.
HALL_FACING = {"CommandCenter": 225.0}
# Facing at which a model is drawn as authored (the default unit Facing).
MODEL_FORWARD = 270.0
FOOTPRINT_PREFIX = "FootprintScoba"
ACTOR_PREFIX = TREE_TYPE + "Fp"
