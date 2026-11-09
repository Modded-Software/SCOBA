#!/usr/bin/env python3
"""Write the minimal MapScript bootstrap for a built map folder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

BOOTSTRAP = """// Generated bootstrap. Do not edit the built copy.
include "TriggerLibs/NativeLib"
include "TriggerLibs/SwarmCampaignLib"
include "scripts/app/main"

void InitTriggers () { main(); }
void InitMap () {
    InitLibs();
    RegionPlayableMapSet(RegionRect(0.0, 0.0, 254.0, 254.0));
    CameraSetBounds(PlayerGroupAll(), RegionRect(0.0, 0.0, 254.0, 254.0), true);
    InitTriggers();
}
"""


def write_bootstrap(map_dir: Path) -> Path:
    if not map_dir.is_dir():
        raise SystemExit(f"map folder not found: {map_dir}")
    target = map_dir / "MapScript.galaxy"
    target.write_text(BOOTSTRAP, encoding="utf-8", newline="\n")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_dir", type=Path)
    args = parser.parse_args()
    target = write_bootstrap(args.map_dir)
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())