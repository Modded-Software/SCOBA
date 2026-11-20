"""Resource line constants (SPEC-BASE-AI 4.7a). Built map cells (256)."""

SEED = 20261118
CENTRE = (128.0, 128.0)          # map centre; piles lie on the side away from it
FIELDS = 8
GEYSERS = 2
HALL_HALF = 4                    # 8x8 Command Center (R-BASE-30)
FIELD_SIZE = (2, 1)
GEYSER_SIZE = (6, 6)                # R-BASE-35: twice the stock 3x3 (FootprintScobaGeyser6x6)

# Organic shape (R-BASE-32), per line from Random(f"{SEED}:{name}").
ARC_SPAN = (100.0, 130.0)        # degrees covered by the fields
ARC_TURN = 20.0                  # arc centre off the away direction, +-
FIELD_R = (6.5, 9.0)
FIELD_JITTER = 6.0               # degrees, +-
FIELD_BACK = 1.5                 # every other field set back up to this
GEYSER_GAP = (14.0, 30.0)        # degrees past an arc end
GEYSER_R = (8.5, 10.5)           # the 3x3 range (7, 9) plus the 1.5 the half side grew
SNAP_TRIES = ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1),
              (2, 0), (-2, 0), (0, 2), (0, -2))

# Search for an expansion hall spot.
RING = 2.0
RINGS = 8
ANGLES = 16
GUARD_OFFSET = 12.0              # camp to each of its hall spots
DOUBLE_OFFSET = 10.0             # jungle anchor to each hall spot
SPAWNS = ("Tosh Spawn", "Kerrigan Spawn", "Nova Spawn", "Raynor Spawn", "Stukov Spawn", "Dehaka Spawn")
SPAWN_CLEAR = 4.0                # sites keep out of the spawn discs, grown by this

TERRAN_JUNGLES = (("TerranJungleLeft", 12), ("TerranJungleRight", 13))   # Regions ids
LURKER = "LurkerMPBurrowed"
LURKER_PLAYER = "8"
GUARDS = (("Brakk", "Brakk"), ("InfestedTank", "InfestedSiegeBreakerSieged"))
# Both camps stand in water about 3 deep, nothing dry within 24 (measured
# 2026-11-18); their sites may stand in it. Every other line stays dry.
WET_SITES = ("BrakkFront", "BrakkBack", "InfestedTankFront", "InfestedTankBack")
SITE_COUNT = 12                  # 4 jungles x 2 + 2 camps x 2
MAIN_COUNT = 6

# Fitting (R-BASE-31).
KEEP_GROW = 2                    # line keep-out: hall and pile cells grown by this
TREE_CLEAR = 1.0                 # a tree position keeps this far outside the keep-out,
TREE_SCALE_CLEAR = 0.35          # plus this times its scale (blockers grow with scale, up to 8)
TREE_GAP = 2.5                   # a moved tree keeps this far from other trees
UNIT_CLEAR = 1.5                 # a unit position keeps this far outside the keep-out
UNIT_GAP = 1.5                   # a moved unit keeps this far from units and trees
FIT_RINGS = 24
FIT_ANGLES = 16

DATA_FILE = "scripts/app/data/base_sites.galaxy"
REPORT = "base_sites_report.txt"
MARKER = ".resources_applied"
