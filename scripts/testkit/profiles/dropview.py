"""Operator view: the intro deploy as in game (the real Space path), then the
hero is killed and the revive pod comes down on its own timer. The operator
judges both drops by eye; not a pass/fail test. Raw times go to the
SCOBADROPVIEW bank.

Run: scripts/playtest.sh dropview  (launches the map for manual viewing)
"""

from __future__ import annotations

from project_root import project_root

from ..map_builder import TestMapSpec, build_instrumented_map

ROOT = project_root()
BUILT = ROOT / "out" / "SCOBA256.SC2Map"
OUTPUT = ROOT / "out" / "SCOBA256_dropview.SC2Map"


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="dropview",
        source=BUILT,
        output=OUTPUT,
        bank_names=("SCOBADROPVIEW",),
        galaxy_files=(ROOT / "scripts" / "testkit" / "galaxy" / "dropview.galaxy",),
        galaxy_includes=("scripts/test/dropview/dropview",),
        init_calls=("gt_DropView_Init();",),
    )


def main() -> None:
    print(build_instrumented_map(map_spec()))


if __name__ == "__main__":
    main()
