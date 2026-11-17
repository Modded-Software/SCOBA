#!/usr/bin/env python3
import os
import re
import sys

WIDTH = os.environ.get("SC2_WINDOW_WIDTH", "1920")
HEIGHT = os.environ.get("SC2_WINDOW_HEIGHT", "1080")
DOCS = os.environ.get(
    "SC2_DOCUMENTS",
    os.path.expanduser(
        "~/Games/battlenet-prefix/pfx/drive_c/users/steamuser/Documents/StarCraft II"
    ),
)
path = os.path.join(DOCS, "Variables.txt")

if not os.path.isfile(path):
    print("missing", path)
    sys.exit(1)

with open(path, "r", encoding="utf-8", errors="replace") as handle:
    lines = handle.read().splitlines()

SHADOW_MAP_SIZE = "8192"  # operator 2026-11-16: forced on every launch (4096, 2048 tried, then 8192)
TERRAIN_TEXTURE_SIZE = "2048"  # operator 2026-11-16: forced on every launch (was 768; 4096 tried, then 2048)

values = {
    "displaymode": "0",
    "windowwidth": WIDTH,
    "windowheight": HEIGHT,
    "shadowmapsize": SHADOW_MAP_SIZE,
    "TerrainTextureSize": TERRAIN_TEXTURE_SIZE,
}
seen = set()
result = []
for line in lines:
    match = re.match(r"^([A-Za-z0-9_]+)=", line)
    key = match.group(1) if match else None
    if key in values:
        result.append("%s=%s" % (key, values[key]))
        seen.add(key)
    else:
        result.append(line)
for key, value in values.items():
    if key not in seen:
        result.append("%s=%s" % (key, value))

with open(path, "w", encoding="utf-8", newline="\n") as handle:
    handle.write("\n".join(result) + "\n")

with open(path, "r", encoding="utf-8", errors="replace") as handle:
    written = handle.read().splitlines()
for key, want in (("shadowmapsize", SHADOW_MAP_SIZE), ("TerrainTextureSize", TERRAIN_TEXTURE_SIZE)):
    found = [line for line in written if line.startswith(key + "=")]
    if found != ["%s=%s" % (key, want)]:
        print(key, "not set to", want, "in", path, found)
        sys.exit(1)

print("configured", path, WIDTH, HEIGHT, "shadowmapsize=" + SHADOW_MAP_SIZE, "TerrainTextureSize=" + TERRAIN_TEXTURE_SIZE)