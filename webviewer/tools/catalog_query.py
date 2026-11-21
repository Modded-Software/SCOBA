"""Print facts from the unit catalog: stats, or the records of the given unit ids.

usage: catalog_query.py CATALOG.json [--modified] [UNIT_ID ...]
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

ONE = [1.0, 1.0, 1.0]


def main() -> int:
    data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    args = sys.argv[2:]
    units = data["units"]
    if not args:
        print(json.dumps(data["stats"], indent=1))
        for field in ("race", "kind", "family"):
            print(field, dict(collections.Counter(u[field] for u in units).most_common()))
        print("inMap", sorted(u["id"] for u in units if u["inMap"]))
        reasons = collections.Counter(v.split(":")[0] for v in data["failedTextures"].values())
        print("failedTextures", dict(reasons))
        return 0
    if args[0] == "--modified":
        # Units whose data changes the look, a few of each sort.
        tests = {
            "actorScale": lambda u: u["actorScale"] != ONE,
            "modelScale": lambda u: u["modelScaleMax"] != ONE or u["modelScaleMin"] != ONE,
            "scaleRange": lambda u: u["modelScaleMax"] != u["modelScaleMin"],
            "eventScale": lambda u: u["eventScale"] != ONE,
            "animSpeed": lambda u: u["animSpeed"] != 1.0,
            "timeScale": lambda u: u["timeScale"] != 1.0,
            "walk": lambda u: u["walkAnimMoveSpeed"] is not None,
            "height": lambda u: u["height"] != 0.0,
            "tint": lambda u: u["tint"] is not None,
            "opacity": lambda u: u["opacity"] is not None,
        }
        for name, test in tests.items():
            hits = [u for u in units if test(u)]
            print(name, len(hits), [u["id"] for u in hits[:14]])
        return 0
    by_id = {u["id"]: u for u in units}
    for ident in args:
        print(json.dumps(by_id.get(ident, {"id": ident, "missing": True})))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
