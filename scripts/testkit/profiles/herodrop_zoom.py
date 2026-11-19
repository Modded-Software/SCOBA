"""Hero drop camera constants and the crash zoom check (SPEC-HERO-DROP 3, 3a).

Split from herodrop.py (file length). Used by herodrop, intro, podbirth."""

from __future__ import annotations

import math
import re

from hitvolumes import pod_birth
from project_root import project_root

ROOT = project_root()

# The pod falls in its Birth clip; the camera follows the clip root
# (scripts/hitvolumes/pod_birth.py). Touchdown: the first loop at or after the land key,
# times from the pod's create loop.
FALL_MS = pod_birth.LAND_MS
LOOP_MS = 62
# The clip clock is anchored on the engine clip time, which reads up to two
# loops ahead (SPEC-HERO-DROP R-DROP-3: 2076..2386).
LAND_MS = (FALL_MS - 2 * LOOP_MS, FALL_MS + 3 * LOOP_MS)
# The harness reads in the same loop as the drop tick, before or after it:
# the camera is at the root of this loop or the next. Within that window it
# must be on the root to 1.0 (XY) and 1.0 (height).
ROOT_TOL_100 = 100
UNIT_GROUND_H100 = 5  # pod unit height: on the ground
CAM_ON_TARGET_100 = 100  # camera target to pod or hero, horizontal


def _report(checks, name: str, ok: bool, detail: str) -> None:
    print(f"{name}: {detail} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1


def _galaxy_const(rel: str, name: str) -> float:
    text = (ROOT / "src" / "SCOBA.SC2Map" / rel).read_text(encoding="utf-8")
    m = re.search(rf"const fixed {name} = (-?[0-9.]+);", text)
    if m is None:
        raise SystemExit(f"{rel}: no {name}")
    return float(m.group(1))


CAM_DISTANCE = _galaxy_const("scripts/app/core/hero_drop.galaxy", "c_DROP_POD_ARM")
CAM_SIDE = _galaxy_const("scripts/app/core/hero_drop.galaxy", "c_DROP_CAM_SIDE")
CAM_PITCH = _galaxy_const("scripts/app/data/pod_birth.galaxy", "c_POD_BIRTH_PITCH")
CAM_YAW = _galaxy_const("scripts/app/core/hero_drop.galaxy", "c_DROP_YAW")
YAW_TOL = 1.0  # degrees
ARM_TOL_100 = 100
# The crash zoom (core/hero_drop.galaxy, SPEC-HERO-DROP 3a).
_HD = "scripts/app/core/hero_drop.galaxy"
ZOOM_LENGTH = _galaxy_const(_HD, "c_DROP_ZOOM_LENGTH")
ZOOM_MOVE = _galaxy_const(_HD, "c_DROP_ZOOM_MOVE")
ZOOM_PITCH = _galaxy_const(_HD, "c_DROP_ZOOM_PITCH")
ZOOM_DIST = _galaxy_const(_HD, "c_DROP_ZOOM_DIST")
ZOOM_FOV0 = _galaxy_const(_HD, "c_DROP_ZOOM_FOV0")
ZOOM_FOV1 = _galaxy_const(_HD, "c_DROP_ZOOM_FOV1")
ZOOM_DIST1 = CAM_DISTANCE + _galaxy_const("scripts/app/data/pod_birth.galaxy", "c_POD_BIRTH_START_Z") / math.sin(math.radians(CAM_PITCH))
ZOOM_TOL = 0.5  # script FOV (deg) and arm (cells)
# Phase trace of one drop: WAIT, ZOOM, FALL, IDLE (gv_dropPhaseTrace).
PHASES = "1230"


def zoom_at(t: float) -> tuple[float, float]:
    """Script FOV and arm at t s into the zoom (gf_HeroDropZoomApply)."""
    w = min(max(t / ZOOM_MOVE, 0.0), 1.0)
    e = 1 - (1 - w) ** 3
    return ZOOM_FOV0 + (ZOOM_FOV1 - ZOOM_FOV0) * e, ZOOM_DIST + (ZOOM_DIST1 - ZOOM_DIST) * e


def zoom_follow(checks, s: str, key: str = "zoom") -> None:
    """The one crash zoom (R-DROP-10), herodrop and intro.

    Rows: ms since the zoom start, script FOV and arm, engine pitch, yaw,
    distance (x100).
    """
    rows = []
    for item in (checks.value(s, "", key) or "").split():
        ms, rest = item.split(":", 1)
        rows.append((int(ms), *(int(v) for v in rest.split("/"))))
    print(f"{s} raw zoom rows={rows}")
    _report(checks, f"{s} zoom sampled", len(rows) >= 3, f"rows={len(rows)}")
    if not rows:
        return
    _report(checks, f"{s} zoom shorter than its length", rows[-1][0] <= ZOOM_LENGTH * 1000 + LOOP_MS, f"last={rows[-1][0]} length={ZOOM_LENGTH}")
    # Script values: the write of this loop or the next (harness order).
    bad = []
    for ms, fov, dist, *_ in rows:
        win = [zoom_at((ms + d) / 1000.0) for d in range(0, 2 * LOOP_MS + 1, 5)]
        if not (min(f for f, _ in win) - ZOOM_TOL <= fov / 100.0 <= max(f for f, _ in win) + ZOOM_TOL and min(a for _, a in win) - ZOOM_TOL <= dist / 100.0 <= max(a for _, a in win) + ZOOM_TOL):
            bad.append((ms, fov, dist))
    _report(checks, f"{s} zoom script FOV and arm on the crash curve", not bad, f"off={bad[:3]}")
    # Engine values from row 1 (getters show a set one loop late).
    lo_p, hi_p = min(ZOOM_PITCH, CAM_PITCH) - YAW_TOL, max(ZOOM_PITCH, CAM_PITCH) + YAW_TOL
    lo_d, hi_d = min(ZOOM_DIST, ZOOM_DIST1) - 1.0, max(ZOOM_DIST, ZOOM_DIST1) + 1.0
    off = [(r[0], r[3], r[4], r[5]) for r in rows[1:] if _yaw_off(r[4] / 100.0, CAM_YAW) > YAW_TOL or not lo_p <= r[3] / 100.0 <= hi_p or not lo_d <= r[5] / 100.0 <= hi_d]
    _report(checks, f"{s} zoom engine yaw, pitch, distance", not off, f"yaw={CAM_YAW} pitch={lo_p:.2f}..{hi_p:.2f} dist={lo_d:.1f}..{hi_d:.1f} off={off[:3]}")
    # The FOV only narrows; the arm only moves toward the fall's first arm.
    sign = 1 if ZOOM_DIST1 >= ZOOM_DIST else -1
    back = [(a[0], b[0]) for a, b in zip(rows, rows[1:]) if b[1] > a[1] + 1 or sign * (b[2] - a[2]) < -1]
    _report(checks, f"{s} zoom never moves back", not back, f"back={back[:3]}")


def _yaw_off(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)
