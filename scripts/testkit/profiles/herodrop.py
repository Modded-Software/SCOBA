"""Hero drop profile (REQ-HERO-DROP).

Every check reads the test bank: alive state, life, level and XP, position,
unit height, camera target and the applied camera height offset. How the
pod looks and sounds is an operator check.
"""

from __future__ import annotations

from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
# c_DROP_HEIGHT 40 and c_DROP_FALL 2.2 s (core/hero_drop.galaxy).
DROP_H100 = 4000
FALL_MS = 2200
LOOP_MS = 62
# The pod appears in the loop after the reinforcement; the harness starts
# its clock in the loop it first sees the pod. Touchdown: the first loop at
# or after the fall time, seen by the harness up to two loops later.
LAND_MS = (FALL_MS - 2 * LOOP_MS, FALL_MS + 3 * LOOP_MS)
# The camera height is set to the pod's target for the next loop. One loop
# of the fastest fall part (40 x 0.94 / 1.6 s) is about 1.5.
CAM_LAG_H100 = 160
CAM_ON_TARGET_100 = 100  # camera target to pod or hero, horizontal


def _report(checks, name: str, ok: bool, detail: str) -> None:
    print(f"{name}: {detail} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1


def _fall(checks, s: str) -> None:
    """R-DROP-3, R-DROP-4: the pod falls from the drop height to the ground; the camera carries it."""
    text = checks.value(s, "", "fall") or ""
    rows = []
    for item in text.split():
        ms, rest = item.split(":", 1)
        pod, cam, dist, alive = (int(v) for v in rest.split("/"))
        rows.append((int(ms), pod, cam, dist, alive))
    print(f"{s} raw fall rows={len(rows)} first={rows[:3]} last={rows[-3:]}")
    cams = [checks.value(s, "", f"camXY{i}") for i in range(4)]
    print(f"{s} raw pod={checks.value(s, '', 'podXY')} death={checks.value(s, '', 'deathXY')} cam={cams}")
    _report(checks, f"{s} fall sampled", len(rows) >= 20, f"rows={len(rows)}")
    if not rows:
        return
    ground = checks.value(s, "tland", "HeroH100") or 0
    base = checks.value(s, "", "camBase100") or 0
    first = rows[0][1] - ground
    _report(checks, f"{s} pod starts at the drop height", DROP_H100 - 200 <= first <= DROP_H100 + 50, f"first={first} ground={ground}")
    rises = [r for a, r in zip(rows, rows[1:]) if r[1] > a[1] + 5]
    _report(checks, f"{s} pod never rises", not rises, f"rises={rises[:3]}")
    last = rows[-1][1] - ground
    _report(checks, f"{s} pod near the ground at the last loop", last <= 300, f"last={last}")
    lag = [(ms, pod - ground, cam - base) for ms, pod, cam, _, _ in rows if abs((pod - ground) - (cam - base)) > CAM_LAG_H100]
    _report(checks, f"{s} camera height carries the pod height", not lag, f"off={lag[:4]}")
    # The camera XY lock is an operator check: CameraGetTarget is right only
    # in the loop after a pan (T26). Raw: the first row is that loop.
    print(f"{s} raw camera to pod, first loop={rows[0][3]}")
    _report(checks, f"{s} camera panned onto the pod", rows[0][3] <= CAM_ON_TARGET_100, f"dist100={rows[0][3]}")
    # The arm is long enough for the pod (c_DROP_CAM_DISTANCE 20).
    dist = checks.value(s, "", "midCamDist100")
    _report(checks, f"{s} camera arm behind the pod", dist is not None and 1500 <= dist <= 2000, f"dist100={dist}")
    # Negative: the hero stays dead while the pod falls.
    alive = [ms for ms, _, _, _, a in rows if a]
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
