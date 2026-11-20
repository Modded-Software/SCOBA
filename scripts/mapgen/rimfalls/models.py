"""The measured models of the rim falls.

The normal waterfall and the rock come from the water features' file
(scripts/data/water_models.json). The rock waterfalls have their own file
(scripts/data/rim_models.json, measure.py): the water features measure no
rock waterfall.
"""

from __future__ import annotations

import json
from pathlib import Path

from mapgen.waterfeatures import models as water_models
from mapgen.waterfeatures.models import Fall, Models
from project_root import project_root

from . import config

DATA = project_root() / "scripts" / "data" / "rim_models.json"


def load(path: Path = DATA) -> Models:
    base = water_models.load()
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    falls = dict(base.falls)
    for kind, variations in data["falls"].items():
        falls[kind] = {
            int(v): Fall(kind, int(v), tuple(f["min"]), tuple(f["max"]), float(f["base_z"]), tuple((float(x), float(y)) for x, y in f["splashes"]))
            for v, f in variations.items()
        }
    for kind in (config.ROCK_FALL, config.FALL):
        if kind not in falls:
            raise ValueError(f"rim falls: no measured model of {kind}")
    if config.ROCK_SOURCE not in base.rocks:
        raise ValueError(f"rim falls: no measured model of {config.ROCK_SOURCE}")
    return Models(falls, base.pipes, base.rocks)
