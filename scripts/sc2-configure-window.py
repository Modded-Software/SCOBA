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

values = {
    "displaymode": "0",
    "windowwidth": WIDTH,
    "windowheight": HEIGHT,
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

print("configured", path, WIDTH, HEIGHT)