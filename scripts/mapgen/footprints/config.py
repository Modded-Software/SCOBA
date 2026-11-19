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
FOOTPRINT_PREFIX = "FootprintScoba"
ACTOR_PREFIX = TREE_TYPE + "Fp"
