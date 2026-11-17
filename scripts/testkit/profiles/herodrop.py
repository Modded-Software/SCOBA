"""Hero drop profile (REQ-HERO-DROP).

Every check reads the test bank: alive state, life, level and XP, position,
unit height, camera target and the applied camera height offset. How the
pod looks and sounds is an operator check.
"""

from __future__ import annotations

from pathlib import Path

from hitvolumes import pod_birth
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
# The pod falls in its Birth clip; the camera follows the clip root
# (scripts/hitvolumes/pod_birth.py). Touchdown: the first loop at or after the land key,
# times from the pod's create loop.
FALL_MS = pod_birth.LAND_MS
LOOP_MS = 62
LAND_MS = (FALL_MS, FALL_MS + 3 * LOOP_MS)
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


def _window(ms: int, facing: float) -> list[tuple[float, float, float]]:
    """The Birth root offset (world, x100) over this loop and the next."""
    return [tuple(v * 100.0 for v in pod_birth.world(m, facing)) for m in range(max(ms - LOOP_MS, 0), ms + LOOP_MS + 1, 5)]


def birth_follow(checks, s: str, ground: int) -> list[tuple[int, int, int, int, int, int]]:
    """A stock pod drop; the camera follows the Birth root (herodrop and intro).

    Rows: ms from the create loop, unit height, applied camera height,
    camera target x, y (x100), and a last flag column for the caller.
    """
    text = checks.value(s, "", "fall") or ""
    rows = []
    for item in text.split():
        ms, rest = item.split(":", 1)
        unit_h, cam_h, cam_xy, alive = rest.split("/")
        cx, cy = (int(v) for v in cam_xy.split(","))
        rows.append((int(ms), int(unit_h), int(cam_h), cx, cy, int(alive)))
    print(f"{s} raw fall rows={len(rows)} first={rows[:3]} last={rows[-3:]}")
    pod_at = checks.value(s, "", "podAt100") or "0,0"
    px, py = (int(v) for v in str(pod_at).split(","))
    facing = (checks.value(s, "", "podFacing100") or 0) / 100.0
    print(f"{s} raw podAt100={pod_at} facing={facing} seenMs={checks.value(s, '', 'seenMs')} death={checks.value(s, '', 'deathXY')}")
    _report(checks, f"{s} fall sampled", len(rows) >= 20, f"rows={len(rows)}")
    if not rows:
        return rows
    base = checks.value(s, "", "camBase100") or 0
    # Stock drop: the unit is never lifted; the model falls (negative of
    # the old design, a landed pod carried down in the air).
    lifted = [(ms, h - ground) for ms, h, *_ in rows if abs(h - ground) > UNIT_GROUND_H100]
    _report(checks, f"{s} pod unit stays on the ground", not lifted, f"lifted={lifted[:3]}")
    # The camera target (engine) on the root, recomputed here from the
    # engine pod position and facing.
    off_xy = []
    off_h = []
    for ms, _, cam_h, cx, cy, _ in rows:
        win = _window(ms, facing)
        dxy = min(((px + wx - cx) ** 2 + (py + wy - cy) ** 2) ** 0.5 for wx, wy, _ in win)
        dh = min(abs(max(wz, 0.0) - (cam_h - base)) for _, _, wz in win)
        if dxy > ROOT_TOL_100:
            off_xy.append((ms, int(dxy)))
        if dh > ROOT_TOL_100:
            off_h.append((ms, int(dh)))
    print(f"{s} raw camera to root xy per loop={[(r[0], r[3] - px, r[4] - py) for r in rows[:6]]}")
    _report(checks, f"{s} camera target on the Birth root", not off_xy, f"off={off_xy[:4]}")
    _report(checks, f"{s} camera height on the Birth root", not off_h, f"off={off_h[:4]}")
    # Negative: early in the fall the camera is far from the pod unit (it
    # follows the drawn pod, not the unit on the ground).
    ms0, _, _, cx0, cy0, _ = rows[0]
    d0 = ((cx0 - px) ** 2 + (cy0 - py) ** 2) ** 0.5
    _report(checks, f"{s} camera off the pod unit early", ms0 > 800 or d0 >= 3000, f"ms={ms0} dist100={int(d0)}")
    # The camera height falls with the root: never rises past one window.
    rises = [(a[0], b[0]) for a, b in zip(rows, rows[1:]) if b[2] > a[2] + 20]
    _report(checks, f"{s} camera height never rises", not rises, f"rises={rises[:3]}")
    return rows


def _fall(checks, s: str) -> None:
    """R-DROP-3, R-DROP-4."""
    rows = birth_follow(checks, s, checks.value(s, "tland", "HeroH100") or 0)
    # The arm is long enough for the pod (c_DROP_CAM_DISTANCE 20).
    dist = checks.value(s, "", "midCamDist100")
    _report(checks, f"{s} camera arm behind the pod", dist is not None and 1500 <= dist <= 2000, f"dist100={dist}")
    # Negative: the hero stays dead while the pod falls.
    alive = [r[0] for r in rows if r[5]]
    _report(checks, f"{s} hero dead during the fall", not alive, f"aliveAt={alive[:4]}")


def check_alive(checks) -> None:
    s = "drop_alive"
    checks.true(s, "t0", "Alive")
    checks.eq(s, "tend", "Pods", checks.value(s, "t0", "Pods"))
    checks.false(s, "tend", "Pending")
    checks.true(s, "tend", "Alive")
    checks.eq(s, "tend", "Landings", checks.value(s, "t0", "Landings"))
    checks.eq(s, "tend", "Deaths", checks.value(s, "t0", "Deaths"))


def check_drop(checks) -> None:
    s = "drop_main"
    pods = checks.value(s, "t0", "Pods") or 0
    deaths = checks.value(s, "t0", "Deaths") or 0
    tag, level = checks.value(s, "t0", "Tag"), checks.value(s, "t0", "Level")
    print(f"{s} raw before: tag={tag} level={level} single={checks.value(s, 't0', 'Single')} savedTps={checks.value(s, 'tdead', 'SavedTps')}")
    checks.true(s, "t0", "TpsMode")
    checks.eq(s, "t0", "Single", 1)
    # R-DROP-1: death is seen, the hero waits.
    checks.false(s, "tdead", "Alive")
    checks.true(s, "tdead", "Pending")
    checks.eq(s, "tdead", "Deaths", deaths + 1)
    # R-DROP-2: the camera stays where the hero died.
    # Read in the pan's own window only (T26); later reads are raw.
    checks.lt(s, "tdead", "CamToDeath100", CAM_ON_TARGET_100)
    print(f"{s} raw twait CamToDeath100={checks.value(s, 'twait', 'CamToDeath100')}")
    # Negative: no pod before the reinforcement; no switch while dead (R-DROP-7).
    checks.eq(s, "twait", "Pods", pods)
    checks.false(s, "twait", "Alive")
    checks.true(s, "twait", "HeroActive")
    checks.gt(s, "twait", "Blocked", checks.value(s, "tdead", "Blocked") or 0)
    # R-DROP-3: one pod of the hero pod type.
    checks.true(s, "", "podSeen")
    checks.eq(s, "", "podType", "SCOBAHeroPod")
    _fall(checks, s)
    checks.between(s, "", "landMs", *LAND_MS)
    # R-DROP-5, 6: the same hero, alive, full life, at the pod, bound.
    for t in ("tland", "tafter"):
        checks.true(s, t, "Alive")
        checks.false(s, t, "Pending")
        checks.true(s, t, "HeroActive")
        checks.true(s, t, "HeroTps")
        checks.true(s, t, "TpsMode")
        checks.eq(s, t, "Pods", pods + 1)
        checks.eq(s, t, "Landings", (checks.value(s, "t0", "Landings") or 0) + 1)
        checks.lt(s, t, "HeroToPod100", 150)
        # The same unit, not a new one; the hero level is kept.
        checks.eq(s, t, "Tag", tag)
        checks.eq(s, t, "Level", level)
        checks.eq(s, t, "Direct", 1)
    # The toggles are set again over the loops after the revive.
    print(f"{s} raw Single tland={checks.value(s, 'tland', 'Single')}")
    checks.eq(s, "tafter", "Single", checks.value(s, "t0", "Single"))
    checks.eq(s, "tland", "Life", checks.value(s, "tland", "LifeMax"))
    # R-DROP-4: the pod part of the camera height is gone. The camera
    # follow on the hero is the hero switch follow; CameraGetTarget is stale
    # under a follow (T26), so it is raw only (operator check).
    print(f"{s} raw camToHero tland={checks.value(s, 'tland', 'CamToHero100')} tafter={checks.value(s, 'tafter', 'CamToHero100')}")
    # The pod quake still shakes at tafter, so the applied height is base
    # plus the quake part (herodrop/20261117-020416: 92 against base 89).
    base = checks.value(s, "", "camBase100") or 0
    for t in ("tland", "tafter"):
        checks.eq(s, t, "DropCam100", 0)
        checks.eq(s, t, "JumpCam100", 0)
    quake = checks.value(s, "tafter", "Quake100") or 0
    checks.between(s, "tafter", "CamApplied100", base + quake - 2, base + quake + 2)
    # Negative: the drop spot is not the death spot; the next reinforcement drops nothing.
    checks.gt(s, "tafter", "HeroToDeath100", 200)
    checks.eq(s, "tnext", "Pods", pods + 1)
    checks.eq(s, "tnext", "Landings", (checks.value(s, "t0", "Landings") or 0) + 1)
    checks.true(s, "tnext", "Alive")


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="herodrop",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["herodrop"],
        bank_names=PROFILE_BANKS["herodrop"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "herodrop.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/herodrop/common",
            "scripts/test/herodrop/herodrop",
        ),
        init_calls=("gt_HeroDropTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    checks.eq("drop_end", "", "RealClicks", 0)
    check_alive(checks)
    check_drop(checks)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="herodrop",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["herodrop"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["herodrop"],
        ready_section="drop_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
