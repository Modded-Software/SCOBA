"""Tuning of the water features (REQ-WATER-FEATURES). Units: 256-map cells."""

from __future__ import annotations

# --- Sites -----------------------------------------------------------------
# Water types whose rectangles get a feature. Operator, 2026-11-20:
# "Decimator holes first". Both holes are painted with Albion water.
SITE_WATER = ("Albion",)
# Placed unit type -> pipe entry in scripts/data/water_models.json.
PIPE_UNITS = {"PsiDecimator": "PsiDecimator"}
# A pipe mouth feeds a pool when it lies within this far of its rectangle.
MOUTH_REACH = 4.0
# Placed water doodads this close to a site rectangle are dropped: the
# feature replaces them (operator: "fully procedural").
CLEAR_MARGIN = 12.0
WATER_TYPES = ("Waterfall", "RockWaterfall", "ZerusWaterfall")

# --- Water level -----------------------------------------------------------
# The pool surface sits this far below the lowest pipe lip of the site set.
DROP = 3.0
# Height of the engine's default CWater (core.sc2mod WaterData): a water
# type the map does not override stands at this level.
DEFAULT_WATER_HEIGHT = 9.0

# --- Carve -----------------------------------------------------------------
POOL_RADIUS = 7.5  # the pool is the wet ground within this far of an impact
RIM = 0.4  # ground around the pool, inside the rectangle, is at least level + RIM
BASIN_RADIUS = 3.5  # bowl dug under each impact
BASIN_DEPTH = 1.2  # depth of that bowl at the impact
PIPE_CLEAR = 0.3  # ground stays this far below a pipe mouth
MOUTH_BACK = 1.5  # the mouth is freed this far back along the pipe
MOUTH_FRONT = 1.0  # and this far in front of it
SHORE_MARGIN = 4.0  # low ground this close outside the rectangle is filled to the rim
BLEND_PASSES = 4  # cells over which a raise or cut fades into the old ground
BLEND_KEEP = 0.6  # share of a raise kept per cell of distance
BLEND_KEEP_CUT = 0.5  # share of a cut kept per cell: walls like the sculpted holes (2 to 3 per cell)
MAX_CHANGE = 7.0  # no vertex moves further than this (guard); the built map needs 6.26
NO_PATH_DEPTH = 0.3  # water at least this deep is painted unpathable

# --- Composition -----------------------------------------------------------
SEED = 20261120
FALL_TYPE = "Waterfall"
FALL_SCALE = (0.6, 2.6)  # height (z) scale limits of a pipe fall
# The fall top is this far up the pipe opening (0 lip, 1 top). Operator,
# 2026-11-20: 0.0 was "way too low", 0.6 was "from the top, not the bottom".
FALL_TOP = 0.15
FALL_TOP_JITTER = 0.08  # +-, per fall (operator 2026-11-20: "more variation in their scale")
# Operator, 2026-11-20: "the regular waterfalls bring up with .2". The whole
# fall moves up; its base is then this far over the water.
FALL_RAISE = 0.2
# Operator, 2026-11-20: the bigger pipe gets the bigger fall, and no fall
# reaches past the side of its pipe. Width is a share of the opening.
FALL_WIDTH = 0.5
FALL_WIDTH_JITTER = 0.2  # +-, per fall (operator 2026-11-20: "more variation in their scale")
FALL_COUNT = 3  # falls side by side under one pipe, across its opening
FALL_GAP = 0.0  # from the mouth to the back of the stream
FALL_GAP_JITTER = 0.25  # +-, per fall
FALL_TURN_JITTER = 0.12  # radians, +-, per fall
# Operator, 2026-11-20, from the game: the right group ran "too much facing
# the east", the left "too much to the south, need a southwest facing". The
# falls faced along their own pipes (south-southwest and west-southwest).
# Share of the turn from the pipe's direction to the mean direction of all
# pipes (southwest for the decimator): 0 own pipe, 1 the mean.
FALL_FACE_COMMON = 1.0
RECT_INSET = 1.0  # water lands at least this far inside the water rectangle (carve.basin digs no closer)
# Operator, 2026-11-20, from the game: both features stood "2-3 units" off
# their pipes. Cells, toward the bigger pipe of the site (sites.toward_big).
SITE_SHIFT = 2.5
FALL_OVERLAP_LIMIT = 0.8  # two pipe falls: they merge into one stream, but are not stacked
FLAGS = ("HeightAbsolute", "ForcePlacement")

# --- Rocks in the pool -----------------------------------------------------
# Operator, 2026-11-20: "the pools need vegetation around and some rocks
# inside, find appropriate doodads from zerus". ZerusRockLarge is the Zerus
# rock doodad of liberty.sc2mod (8 variations). The vegetation is flora's
# (flora/pools.py).
ROCK_TYPE = "ZerusRockLarge"
ROCK_COUNT = 4  # per pool, fewer when they do not fit
ROCK_SCALE = (0.45, 1.1)
ROCK_ABOVE = (0.3, 0.9)  # the top of a rock stands this far over the water
ROCK_LIFT = 0.6  # the origin may stand this share of the model's underside over the pool floor
ROCK_MIN_DEPTH = 0.4  # water this deep under a rock
ROCK_FALL_CLEAR = 2.0  # from where a fall lands
ROCK_SPACING = 2.5  # between two rocks
ROCK_JITTER = 0.3  # +-, off the vertex

# --- Wall paint ------------------------------------------------------------
# Operator, 2026-11-20: no rock waterfalls; "paint the sloped walls of the
# pools with an upscaled rock texture", then "switch to dirt, replace with
# the dirt texture we use". Zerus1 is the lane dirt (flora.dirt.DIRT_NAME,
# editor name "Zerus Dirt Medium"); the HD texture build upscales it.
WALL_TEXTURE = "Zerus1"
WALL_SLOPE = (0.5, 1.2)  # rise per cell: no paint below, solid paint above
WALL_MARGIN = 8.0  # cells round a water rectangle that can be painted (SHORE_MARGIN + BLEND_PASSES)

# --- Checks ----------------------------------------------------------------
TOP_TOLERANCE = 0.25  # fall top to its aim inside the pipe opening
SIDE_TOLERANCE = 0.3  # a fall may reach this far past the side of its pipe (its turn)
WET_MIN = 0.2  # water depth wanted under a fall
