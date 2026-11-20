"""Tuning of the rim waterfalls (REQ-RIM-FALLS).

Operator, 2026-11-20: rock and normal waterfalls "at relatively empty
positions at the inner rim of the map (it is a bowl with raised walls)",
"scaled and layered randomly, rotated so they face the same direction as
the normal of the raised terrain behind them"; 12 to 24 groups; basins
allowed, with rocks on the bottom; decorative, walkable; rock waterfalls at
the rim only.

Lengths are world units of the built 256 map. Heights are ground space
(waterfeatures/build.py doodad_rise).
"""

from __future__ import annotations

SEED = 20261121

# --- the rim wall -----------------------------------------------------------
EDGE_MIN = 5.0  # a site is at least this far inside the map edge
EDGE_MAX = 20.0  # and at most this far: the wall, not the bowl floor
NORMAL_RADIUS = 3  # vertices each way the ground is averaged over for the wall normal
WALL_SLOPE = 0.45  # averaged slope of a wall, rise per unit
INWARD = 0.3  # the wall's downhill direction points to the map centre at least this much (cosine)
WALL_REACH = 6.0  # the ground this far uphill ...
WALL_RISE = 2.5  # ... stands at least this much higher: raised terrain behind
FOOT_REACH = 6.0  # the ground this far downhill ...
FOOT_SLOPE = 0.7  # ... is flatter than this: the foot of the wall

# --- empty spots ------------------------------------------------------------
CLEAR = 4.5  # nothing placed (doodad, unit, point) within this of a site, past its reach
TREE_PREFIX = "ZerusTree"
TREE_REACH = 0.5  # canopy radius of a tree per unit of its scale (flora/treevary.py CANOPY_PER_SCALE)
# Operator, 2026-11-20: "never place them near geysers".
GEYSER_UNITS = ("VespeneGeyser",)
GEYSER_REACH = 12.0  # a geyser keeps sites this much further away
WATER_MARGIN = 14.0  # and no water rectangle
SECTORS = 28  # the rim is cut in this many sectors round the map centre: one site each at most
SECTOR_USE = 0.85  # only the middle share of a sector takes a site: neighbours stay apart
MIN_SITES = 12  # operator: 12 to 24
MAX_SITES = 24
MIN_SPACING = 14.0

# --- the basin at the foot --------------------------------------------------
BASIN_AHEAD = 2.0  # basin centre, downhill of the site
BASIN_RADIUS = 3.0
BASIN_DEPTH = 0.9
BASIN_BLEND = 2.5  # the cut fades out over this width
MAX_CUT = 8.0  # the ground is never lowered more than this

# --- the falls --------------------------------------------------------------
ROCK_FALL = "RockWaterfall"
FALL = "Waterfall"
ROCK_FALLS = (1, 2)  # per group
FALLS = (1, 3)
ROCK_FALL_SCALE = (0.9, 1.7)
ROCK_FALL_TALL = (0.9, 1.25)  # height scale over the ground-plane scale
ROCK_FALL_BACK = 0.7  # a rock waterfall stands at least this share of the basin radius uphill of the basin centre
ROCK_FALL_SIDE = (2.0, 3.5)  # a second one stands this far to a side
# Operator, 2026-11-20: "embedded in the terrain, they are floating in front
# of it". A rock waterfall stands uphill where the wall covers this share of
# its height over the water.
EMBED = (0.35, 0.5)
EMBED_MIN = 0.25  # the build fails under this
EMBED_REACH = 14.0  # uphill of the basin centre, at most
EMBED_STEP = 0.25
FALL_WIDE = (0.8, 1.9)  # ground-plane scale of a normal waterfall
FALL_REACH = (0.45, 0.95)  # its top, as a share of the rock waterfall's height over the water
FALL_SIDE = 1.8  # sideways from the rock waterfall, at most
FALL_AHEAD = (0.2, 1.4)  # in front of it
TURN_JITTER = 0.14  # radians each way round the wall normal
SURFACE = 0.5  # the water surface of the models: this share of the basin depth below the basin edge

# --- rocks on the basin floor -----------------------------------------------
ROCK_SOURCE = "ZerusRockLarge"  # the stock rock: model and measured bounds
ROCK = "ZerusRockLargeScobaRim"  # same model, no footprint: the rim stays walkable
NONE_FOOTPRINT = "FootprintScobaRimNone"
ROCKS = (2, 3)
ROCK_SCALE = (0.3, 0.7)
ROCK_SPREAD = 0.8  # share of the basin radius
ROCK_SPACING = 1.2
ROCK_FALL_CLEAR = 0.9  # from where a rock waterfall's streams land
ROCK_SINK = 0.1
ROCK_TRIES = 24

MARKER = ".rim_falls"
