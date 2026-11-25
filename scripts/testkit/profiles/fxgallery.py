"""Operator gallery of candidate crush effects; not a pass/fail test.

Build: PYTHONPATH=scripts uv run python -m testkit.profiles.fxgallery
Then launch the printed map with scripts/launch-scoba.sh (SC2_PLAYTEST_ACTIVE=1,
SC2_MAP_SOURCE=<map>). The operator judges each labelled effect.
"""

from __future__ import annotations

import workpaths
from project_root import project_root

from ..map_builder import TestMapSpec, build_instrumented_map

ROOT = project_root()


def output_path():
    return workpaths.path("SC2_OUT") / "SCOBA256_fxgallery.SC2Map"


def map_spec() -> TestMapSpec:
    galaxy = ROOT / "scripts" / "testkit" / "galaxy"
    return TestMapSpec(
        profile="fxgallery",
        source=workpaths.path("SC2_BUILT_MAP"),
        output=output_path(),
        bank_names=(),
        galaxy_files=(galaxy / "fxgallery.galaxy",),
        galaxy_includes=("scripts/test/fxgallery/fxgallery",),
        init_calls=("gt_FxGallery_Init();",),
    )


def main() -> None:
    print(build_instrumented_map(map_spec()))


if __name__ == "__main__":
    main()
