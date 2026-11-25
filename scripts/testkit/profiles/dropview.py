"""Operator view: the intro deploy as in game (the real Space path), then the
hero is killed and the revive pod comes down on its own timer. The operator
judges both drops by eye; not a pass/fail test. Raw times go to the
SCOBADROPVIEW bank.

Run: scripts/playtest.sh dropview  (launches the map for manual viewing)
"""

from __future__ import annotations

import workpaths
from project_root import project_root

from ..map_builder import TestMapSpec, build_instrumented_map

ROOT = project_root()


def built():
    return workpaths.path("SC2_BUILT_MAP")


def output_path():
    return workpaths.path("SC2_OUT") / "SCOBA256_dropview.SC2Map"


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="dropview",
        source=built(),
        output=output_path(),
        bank_names=("SCOBADROPVIEW",),
        galaxy_files=(ROOT / "scripts" / "testkit" / "galaxy" / "dropview.galaxy",),
        galaxy_includes=("scripts/test/dropview/dropview",),
        init_calls=("gt_DropView_Init();",),
    )


def main() -> None:
    print(build_instrumented_map(map_spec()))


if __name__ == "__main__":
    main()
