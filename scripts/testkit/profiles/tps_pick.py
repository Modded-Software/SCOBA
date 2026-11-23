"""R-TPS-84 checks of the tps `pick` group (scripts/testkit/galaxy/tpspick.galaxy).

The crosshair ray picks a unit through its hit volume. Each section aims at
points in the target's model space; the points are checked on the host
against scripts/hitvolumes/ray.py (test_hit_volumes.py, InGameCaseTests).
"""

from __future__ import annotations

import re

from hitvolumes import galaxy

# section -> (tags the pick must return the target for, tags it must not)
CASES = {
    "tps_pick_medic": (("thead",), ("tabove",)),
    "tps_pick_marine": (("tthigh", "tmid"), ("tside", "tside2")),
    "tps_pick_ultra": (("tfront",), ("tback",)),
    "tps_pick_flyer": (("tbody",), ("tunder",)),
    "tps_pick_far": (("tbody",), ("tside",)),
    "tps_pick_thor": (("tchest",), ()),
    # Types the old unit list missed or the classic skins changed.
    "tps_pick_scv": (("tbody",), ("tside",)),
    "tps_pick_drone": (("tbody",), ("tabove",)),
    "tps_pick_dehaka": (("tbody",), ("tside",)),
    "tps_pick_fargroup": (("tbody",), ()),
    # The Hive is unpickable scenery: no ray picks it.
    "tps_pick_hive": ((), ("ttop", "tnorth", "tover")),
}
SCENERY = ("Hive", "PsiDecimator")
SCENERY_KEYS = ("FilterIn", "StateInvuln")
# Missing: unit types near the lane the pick met without a volume (raw).
RAW = ("Pick", "PickT100", "Ray", "Aim", "Missing")


SKY = ("MengskBC", "Mothership", "Overlord", "Battlecruiser", "lane")


def check_pick(checks) -> None:
    for key in SKY:
        print(f"tps_pick_sky raw {key}: {checks.value('tps_pick_sky', '', key)}")
    for section, (hits, misses) in CASES.items():
        print(f"{section} raw: dist100={checks.value(section, '', 'Dist100')} facing={checks.value(section, '', 'Facing')} z100={checks.value(section, '', 'Z100')} height100={checks.value(section, '', 'Height100')} ground100={checks.value(section, '', 'Ground100')}")
        for tag in hits + misses:
            print(f"  {tag}: " + " ".join(f"{key}={checks.value(section, tag, key)}" for key in RAW))
        for tag in hits:
            checks.true(section, tag, "PickIsUnit")
        # Negative cases: a ray outside the volume does not pick the unit.
        for tag in misses:
            checks.false(section, tag, "PickIsUnit")
    # The Marine in front of the Hive is picked; over it, nothing.
    checks.true("tps_pick_hive", "tmarine", "PickIsUnit")
    checks.eq("tps_pick_hive", "tmarine", "Pick", "Marine")
    checks.eq("tps_pick_hive", "tover", "Pick", "none")
    checks.eq("tps_pick_hive", "ttop", "Pick", "none")
    # Scenery: the engine holds it invulnerable, and the Invulnerable target
    # filter excludes it. Marine control: the opposite on both points.
    for kind in (*SCENERY, "Marine"):
        print(f"tps_pick_scenery raw {kind}: " + " ".join(f"{k}={checks.value('tps_pick_scenery', '', kind + k)}" for k in SCENERY_KEYS))
    for kind in SCENERY:
        checks.false("tps_pick_scenery", "", kind + "FilterIn")
        checks.true("tps_pick_scenery", "", kind + "StateInvuln")
    checks.true("tps_pick_scenery", "", "MarineFilterIn")
    checks.false("tps_pick_scenery", "", "MarineStateInvuln")
    # The operator's Thor case, aim held: reticle enemy (1), status bar on
    # the Thor, the shot a hit (1) at the Thor.
    for key in ("tchestAim", "tchestReticle", "tchestStatus", "tchestShotKind", "tchestShotThor"):
        print(f"tps_pick_thor raw {key}={checks.value('tps_pick_thor', '', key)}")
    checks.true("tps_pick_thor", "", "tchestAim")
    checks.eq("tps_pick_thor", "", "tchestReticle", 1)
    checks.true("tps_pick_thor", "", "tchestStatus")
    checks.eq("tps_pick_thor", "", "tchestShotKind", 1)
    checks.true("tps_pick_thor", "", "tchestShotThor")
    # The click on the body sets the UI target.
    checks.true("tps_pick_marine", "tclick", "TargetEnemy")
    check_table(checks)


# Raw: the reload time is an unconfirmed probe (a real-time timer may not
# move within one script run).
LOAD_RAW = ("Types", "Shapes", "FarTypes", "FarUnits", "ReloadRealMs", "ReloadGameMs")


def check_table(checks) -> None:
    """The full table loads, a far type made after start is in the far
    group, and a near type is not."""
    for key in LOAD_RAW:
        print(f"tps_pick_load raw {key}={checks.value('tps_pick_load', '', key)}")
    want = hit_volume_sizes()
    checks.eq("tps_pick_load", "", "Types", want["c_HV_TYPES"])
    checks.eq("tps_pick_load", "", "Shapes", want["c_HV_SHAPES"])
    checks.eq("tps_pick_load", "", "FarTypes", want["c_HV_FAR_TYPES"])
    checks.eq("tps_pick_load", "", "TypesAfter", want["c_HV_TYPES"])
    checks.eq("tps_pick_load", "", "ShapesAfter", want["c_HV_SHAPES"])
    checks.eq("tps_pick_load", "", "FarTypesAfter", want["c_HV_FAR_TYPES"])
    checks.true("tps_pick_load", "", "ScvKnown")
    checks.true("tps_pick_load", "", "DehakaKnown")
    checks.false("tps_pick_load", "", "BurrowedKnown")
    checks.true("tps_pick_fargroup", "", "FarType")
    checks.true("tps_pick_fargroup", "", "InFarGroup")
    checks.false("tps_pick_fargroup", "", "MarineInFarGroup")


def hit_volume_sizes() -> dict[str, int]:
    """The table sizes the generator wrote (hit_volumes_size.galaxy)."""
    text = (galaxy.OUT_DIR / galaxy.SIZE).read_text(encoding="utf-8")
    return {m.group(1): int(m.group(2)) for m in re.finditer(r"const int (c_HV_\w+) = (\d+);", text)}
