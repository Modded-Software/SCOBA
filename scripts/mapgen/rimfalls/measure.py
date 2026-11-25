"""Measure the rock waterfall models of the rim falls.

Reads the stock models from the game storage (stormex) and writes
scripts/data/rim_models.json, model space, in the format of
water_models.json "falls": bounds, the water surface the model was made
for, and where its streams land.

The result is committed, so the build never reads the models.

usage: make measure-rim-falls
"""

from __future__ import annotations

import json

import workpaths

from mapgen.waterfeatures import measure as water_measure

from . import config, models


def measure() -> dict:
    files = water_measure.stock_files(config.ROCK_FALL, workpaths.path("SC2_TESTKIT") / "water_models")
    return {"falls": {config.ROCK_FALL: {str(v): water_measure.fall(p) for v, p in sorted(files.items())}}}


def main() -> int:
    data = measure()
    for v, f in data["falls"][config.ROCK_FALL].items():
        print(f"{config.ROCK_FALL} {v}: min={f['min']} max={f['max']} base_z={f['base_z']} splashes={len(f['splashes'])}")
    models.DATA.write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"{models.DATA} bytes={models.DATA.stat().st_size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
