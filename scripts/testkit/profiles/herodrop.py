"""Hero drop profile (REQ-HERO-DROP).

Every check reads the test bank: alive state, life, level and XP, position,
unit height, camera target and the applied camera height offset. How the
pod looks and sounds is an operator check.
"""

from __future__ import annotations

import math
import re
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


def aim(ms: float, px: float, py: float, facing: float, side: float = CAM_SIDE) -> tuple[float, float, float]:
    """Drop camera target x, y and arm (x100) at ms (SPEC-HERO-DROP 3):
    the look ray through the root meets the ground, then the side arm to
    the right of the travel."""
    wx, wy, wz = pod_birth.world(ms, facing)
    z = max(wz, 0.0)
    p = math.radians(CAM_PITCH)
    t = math.radians(facing + pod_birth.travel()[0])
    r = math.radians(facing + pod_birth.travel()[0] - 90.0)
    ray = z * math.cos(p) / math.sin(p)
    x = px / 100.0 + wx + ray * math.cos(t) + side * math.cos(r)
    y = py / 100.0 + wy + ray * math.sin(t) + side * math.sin(r)
    return x * 100.0, y * 100.0, (CAM_DISTANCE + z / math.sin(p)) * 100.0


def _yaw_off(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def birth_follow(checks, s: str, ground: int) -> list[tuple[int, ...]]:
    """A stock pod drop; the camera rides the Birth root on the side arm
    (herodrop and intro).

    Rows: ms from the create loop, unit height, applied camera height,
    camera target x, y (x100), a flag column for the caller, engine camera
    yaw and distance (x100).
    """
    text = checks.value(s, "", "fall") or ""
    rows = []
    for item in text.split():
        ms, rest = item.split(":", 1)
        unit_h, cam_h, cam_xy, flag, yaw, dist = rest.split("/")
        cx, cy = (int(v) for v in cam_xy.split(","))
        rows.append((int(ms), int(unit_h), int(cam_h), cx, cy, int(flag), int(yaw), int(dist)))
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
    # The engine camera target is right only in the pan's loop (F6): the
    # first row. It is on the side-arm aim, recomputed here from the engine
    # pod position and facing.
    ms0, _, _, cx0, cy0 = rows[0][:5]
    win0 = [aim(m, px, py, facing) for m in range(max(ms0 - LOOP_MS, 0), ms0 + LOOP_MS + 1, 5)]
    d0 = min(((ax - cx0) ** 2 + (ay - cy0) ** 2) ** 0.5 for ax, ay, _ in win0)
    print(f"{s} raw first row ms={ms0} cam={cx0},{cy0} aim={[(int(a), int(b)) for a, b, _ in win0[:2]]}")
    _report(checks, f"{s} first loop camera target on the side arm", ms0 <= LOOP_MS and d0 <= ROOT_TOL_100, f"ms={ms0} off100={int(d0)}")
    # Negative: not right behind the pod. The target is the side arm away
    # from the aim with no side arm.
    nx, ny, _ = aim(ms0, px, py, facing, 0.0)
    dn = ((nx - cx0) ** 2 + (ny - cy0) ** 2) ** 0.5
    _report(checks, f"{s} camera not right behind the pod", dn >= CAM_SIDE * 100 - ROOT_TOL_100, f"toBehind100={int(dn)} side100={int(CAM_SIDE * 100)}")
    # Every loop: the engine yaw is the travel, the engine arm the ray arm.
    travel = (facing + pod_birth.travel()[0]) % 360.0
    # From row 1: the getters show a set one loop late (herodrop/20261118-190606:
    # yaw 90.00 in the create loop, 225 after).
    off_yaw = [(r[0], r[6]) for r in rows[1:] if _yaw_off(r[6] / 100.0, travel) > YAW_TOL]
    _report(checks, f"{s} camera yaw is the travel", not off_yaw, f"travel={travel:.2f} off={off_yaw[:4]}")
    # The arm: set with no blend in the first loop, so exact there. The
    # engine blend between legs is not linear (herodrop/20261118-175411:
    # 112.6 at loop 8 against 94.4 linear), so after that: in range and
    # never growing.
    # The distance getter shows a set one loop late (herodrop/20261118-181519:
    # 1.5 in the create loop, 125.4 the next): the exact check is row 1.
    r1 = rows[1] if len(rows) > 1 else rows[0]
    arm1 = [aim(m, px, py, facing)[2] for m in range(max(r1[0] - 2 * LOOP_MS, 0), r1[0] + 1, 5)]
    _report(checks, f"{s} early camera arm on the root ray", min(arm1) - ARM_TOL_100 <= r1[7] <= max(arm1) + ARM_TOL_100, f"ms={r1[0]} arm100={r1[7]} want={int(min(arm1))}..{int(max(arm1))}")
    lo, hi = aim(FALL_MS, px, py, facing)[2], aim(0, px, py, facing)[2]
    off_arm = [(r[0], r[7]) for r in rows[1:] if not lo - ARM_TOL_100 <= r[7] <= hi + ARM_TOL_100]
    grows = [(a[0], b[0]) for a, b in zip(rows[1:], rows[2:]) if b[7] > a[7] + 20]
    # Raw only: the engine target reads right only in a loop that issues a
    # pan, (12, 8) between (T26; herodrop/20261118-181813, with mouse-relative
    # off). That the view rides the pod is an operator check.
    print(f"{s} raw camera target per loop={[(r[0], r[3], r[4]) for r in rows]}")
    print(f"{s} raw arm per loop={[(r[0], r[7]) for r in rows]}")
    _report(checks, f"{s} camera arm in range", not off_arm, f"want={int(lo)}..{int(hi)} off={off_arm[:4]}")
    _report(checks, f"{s} camera arm never grows", not grows, f"grows={grows[:3]}")
    # Negative of the old design: no pod height in the camera height offset.
    lifted_cam = [(r[0], r[2] - base) for r in rows if abs(r[2] - base) >= ROOT_TOL_100]
    _report(checks, f"{s} no pod height in the camera", not lifted_cam, f"off={lifted_cam[:4]}")
    rises = [(a[0], b[0]) for a, b in zip(rows, rows[1:]) if b[2] > a[2] + 20]
    _report(checks, f"{s} camera height never rises", not rises, f"rises={rises[:3]}")
    return rows


def _fall(checks, s: str) -> None:
    """R-DROP-3, R-DROP-4."""
    rows = birth_follow(checks, s, checks.value(s, "tland", "HeroH100") or 0)
    print(f"{s} raw midCamDist100={checks.value(s, '', 'midCamDist100')}")
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


def check_twice(checks) -> None:
    """Three natural deaths in a row; the hero comes back after each as a
    fresh unit (operator 2026-11-18: not after the second; R-DROP-8)."""
    s = "drop_twice"
    deaths = checks.value(s, "t0", "Deaths") or 0
    landings = checks.value(s, "t0", "Landings") or 0
    returns = checks.value(s, "t0", "Returns") or 0
    life_max = checks.value(s, "t0", "LifeMax")
    # The spent point took: current life max above the data value (normal).
    checks.gt(s, "t0", "LifeMax", checks.value(s, "t0", "LifeMaxBase") or 0)
    for n in (1, 2, 3):
        d, b = f"dead{n}", f"back{n}"
        print(f"{s} raw {d}ByDamage={checks.value(s, '', d + 'ByDamage')} {d}OldValid={checks.value(s, '', d + 'OldValid')} {b}OldValid={checks.value(s, '', b + 'OldValid')} "
              f"{b}Type={checks.value(s, b, 'Type')} {b}LifeMax={checks.value(s, b, 'LifeMax')}")
        checks.false(s, d, "Alive")
        checks.true(s, d, "Pending")
        checks.eq(s, d, "Deaths", deaths + n)
        for key in ("Valid", "Alive", "HeroActive", "HeroTps"):
            checks.true(s, b, key)
        for key in ("Hidden", "Paused", "Pending", "PodValid", "InputHeld"):
            checks.false(s, b, key)
        checks.eq(s, b, "Landings", landings + n)
        checks.eq(s, b, "Returns", returns + n)
        checks.eq(s, b, "Type", checks.value(s, "t0", "Type"))
        checks.eq(s, b, "LifeMax", life_max)
        checks.true(s, "", d + "ByDamage")
        checks.eq(s, b, "Life", checks.value(s, b, "LifeMax"))
        checks.lt(s, b, "HeroToPod100", 150)
        # Negative: the dead unit is gone after the return, not before.
        checks.false(s, "", b + "OldValid")


def check_seat2(checks) -> None:
    """Seat 2 dies and comes back; seat 1 is untouched (R-DROP-9)."""
    s = "drop_seat2"
    keys = ("t0Valid2", "t0Bound2", "t0Owner2", "deadByDamage2", "deadPending2", "deadPending1", "deadDeaths2", "podSeen2",
            "fallHeld1", "fallHeld2", "backAlive2", "backNew2", "backOldValid2", "backOwner2", "backType2",
            "backSeatHero2", "backLandings2", "backHeld2", "backToPod100", "backToSpawn100", "oneSame",
            "oneAlive", "onePods", "oneYawDelta100")
    print(f"{s} raw " + " ".join(f"{k}={checks.value(s, '', k)}" for k in keys))
    checks.true(s, "", "t0Valid2")
    checks.true(s, "", "t0Bound2")
    checks.eq(s, "", "t0Owner2", 2)
    checks.true(s, "", "deadByDamage2")
    checks.true(s, "", "deadPending2")
    checks.gt(s, "", "deadDeaths2", 0)
    checks.true(s, "", "podSeen2")
    checks.true(s, "", "fallHeld2")
    checks.true(s, "", "backAlive2")
    checks.true(s, "", "backNew2")
    checks.false(s, "", "backOldValid2")
    checks.eq(s, "", "backOwner2", 2)
    checks.eq(s, "", "backType2", "ToshSCOBA")
    checks.true(s, "", "backSeatHero2")
    checks.gt(s, "", "backLandings2", 0)
    checks.false(s, "", "backHeld2")
    checks.lt(s, "", "backToPod100", 150)
    # Seat 1: no drop, no hold, same hero, camera yaw unchanged.
    checks.false(s, "", "deadPending1")
    checks.false(s, "", "fallHeld1")
    checks.true(s, "", "oneSame")
    checks.true(s, "", "oneAlive")
    checks.eq(s, "", "onePods", checks.value("drop_twice", "back3", "Pods"))
    checks.lt(s, "", "oneYawDelta100", 100)


def check_drop(checks) -> None:
    s = "drop_main"
    pods = checks.value(s, "t0", "Pods") or 0
    deaths = checks.value(s, "t0", "Deaths") or 0
    tag, level = checks.value(s, "t0", "Tag"), checks.value(s, "t0", "Level")
    print(f"{s} raw before: tag={tag} level={level} single={checks.value(s, 't0', 'Single')} savedTps={checks.value(s, 'tdead', 'SavedTps')}")
    checks.true(s, "t0", "TpsMode")
    # One drop path: input held while the pod falls, back after (same as
    # the intro); the hold is not taken by the death alone.
    for t, held in (("t0", False), ("twait", False), ("tfall", True), ("tafter", False)):
        checks.eq(s, t, "InputHeld", held)
        # Per-player hold: no trigger is disabled; another player is not held.
        checks.true(s, t, "CursorTrigOn")
        checks.true(s, t, "TurnTickOn")
        checks.false(s, t, "InputHeld2")
    # Fixed drop yaw: the camera stood off it before the drop (negative),
    # the pod faces drop yaw - travel, the engine yaw is the drop yaw.
    angle = pod_birth.travel()[0]
    facing = (checks.value(s, "", "podFacing100") or 0) / 100.0
    before = (checks.value(s, "twait", "CamYaw100") or 0) / 100.0
    _report(checks, f"{s} camera yaw before the drop off the drop yaw", _yaw_off(before, CAM_YAW) > 10.0, f"before={before} drop={CAM_YAW}")
    _report(checks, f"{s} pod facing = drop yaw - travel", _yaw_off(facing, CAM_YAW - angle) <= 1.0, f"facing={facing} want={(CAM_YAW - angle) % 360.0:.2f}")
    _report(checks, f"{s} tfall camera yaw = drop yaw", _yaw_off((checks.value(s, 'tfall', 'CamYaw100') or 0) / 100.0, CAM_YAW) <= YAW_TOL, f"yaw={checks.value(s, 'tfall', 'CamYaw100')}")
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
        # A fresh unit of the same type (no revive, R-DROP-6); the hero
        # level is kept.
        checks.eq(s, t, "Type", checks.value(s, "t0", "Type"))
        checks.eq(s, t, "Returns", (checks.value(s, "t0", "Returns") or 0) + 1)
        checks.eq(s, t, "Level", level)
        checks.eq(s, t, "Direct", 1)
    # The toggles are set again over the loops after the revive.
    print(f"{s} raw Single tland={checks.value(s, 'tland', 'Single')}")
    checks.eq(s, "tafter", "Single", checks.value(s, "t0", "Single"))
    checks.eq(s, "tland", "Life", checks.value(s, "tland", "LifeMax"))
    # The revived hero animates at full rate (operator 2026-11-18: frozen
    # after the revive). The death sets AnimSetTimeScaleGlobal 0.125 on the
    # actor (ActorData ToshSCOBAUnit); the baseline must read normal.

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


def check_leave(checks) -> None:
    """Seat 2 leaves mid-fall: drop, hold and seat end (R-ROSTER-8)."""
    s = "drop_leave"
    print(f"{s} raw " + " ".join(f"{k}={checks.value(s, '', k)}" for k in (
        "podSeen", "heldBefore", "podAfter", "heldAfter", "pendingAfter", "playedAfter", "landingsDelta", "leaves")))
    checks.true(s, "", "podSeen")
    checks.true(s, "", "heldBefore")
    checks.false(s, "", "podAfter")
    checks.false(s, "", "heldAfter")
    checks.false(s, "", "pendingAfter")
    checks.false(s, "", "playedAfter")
    checks.eq(s, "", "landingsDelta", 0)
    checks.gt(s, "", "leaves", 0)


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
    check_twice(checks)
    check_seat2(checks)
    check_leave(checks)


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
