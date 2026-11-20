"""Pod Birth profile (SPEC-HERO-DROP 3).

Proves from engine reads that the pod model plays Birth and that the map's
camera runs on the clip time the engine reports. The clip is read as the
split-body probe does: AnimLengthQueryByName on the pod's main actor, slot
"Default"; length, remaining, clip time = length - remaining. How the pod
looks is an operator check.
"""

from __future__ import annotations

import math
from pathlib import Path

from hitvolumes import pod_birth
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .herodrop_zoom import ARM_MAX_MS, ZOOM_LENGTH
from .herodrop_zoom import CAM_DISTANCE as CAM_ARM
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
LOOP_MS = 62
BIRTH_MS = pod_birth.LENGTH_MS
LEN_TOL_MS = 50  # the map's c_DROP_CLIP_LEN_TOL
# Clip time against script time: one loop of read order either way.
SYNC_TOL_MS = 2 * LOOP_MS
ROOT_TOL_100 = 100  # camera on the root, XY and height, world x100
# Each engine clip read (AnimLengthQueryWait) waits into a later loop, so a
# harness row is 2 to 3 loops apart (podbirth/20261117-105617: 187 ms with
# two reads per row, 125 ms with one). Coverage is checked, not row counts.
MAX_GAP_MS = 4 * LOOP_MS


def _covers(ms: list[int], start: int, end: int) -> tuple[bool, str]:
    if not ms:
        return False, "no rows"
    gaps = [b - a for a, b in zip(ms, ms[1:])]
    worst = max(gaps, default=0)
    ok = ms[0] <= start and ms[-1] >= end and worst <= MAX_GAP_MS
    return ok, f"first={ms[0]} last={ms[-1]} want {start}..{end} maxGap={worst}"


def _report(checks, name: str, ok: bool, detail: str) -> None:
    print(f"{name}: {detail} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1


def _eye(tx: float, ty: float, yaw: float, pitch: float, dist: float) -> tuple[float, float, float]:
    c = dist * math.cos(math.radians(pitch))
    return (tx - c * math.cos(math.radians(yaw)), ty - c * math.sin(math.radians(yaw)), dist * math.sin(math.radians(pitch)))


def _ray_gap(eye, yaw: float, pitch: float, root100) -> float:
    """Distance (world) from a root point (x100 xy, x100 z) to the look ray."""
    p = (root100[0] / 100.0, root100[1] / 100.0, root100[2] / 100.0)
    cp = math.cos(math.radians(pitch))
    d = (cp * math.cos(math.radians(yaw)), cp * math.sin(math.radians(yaw)), -math.sin(math.radians(pitch)))
    v = tuple(p[i] - eye[i] for i in range(3))
    k = sum(v[i] * d[i] for i in range(3))
    if k <= 0.0:
        return 9999.0  # behind the eye: not seen
    return math.sqrt(max(sum(x * x for x in v) - k * k, 0.0))


def _wrap(a: float) -> float:
    return (a + 180.0) % 360.0 - 180.0


def _is_birth(length: int) -> bool:
    return abs(length - BIRTH_MS) <= LEN_TOL_MS


def _lenrem(text: str) -> tuple[int, int]:
    a, b = text.split("/")
    return int(a), int(b)


def check_plays(checks) -> None:
    """Unit: the stock calls make the engine report Birth, running in game time."""
    s = "pb_plays"
    rows = []
    for item in (checks.value(s, "", "trace") or "").split():
        ms, raw, scaled = item.split(":")
        rows.append((int(ms), *_lenrem(raw), *_lenrem(scaled)))
    print(f"{s} raw rows={len(rows)} first={rows[:4]} last={rows[-4:]}")
    _report(checks, f"{s} sampled", len(rows) >= 10, f"rows={len(rows)}")
    if not rows:
        return
    _report(checks, f"{s} Birth reported in the create loop", _is_birth(rows[0][1]), f"len={rows[0][1]} want={BIRTH_MS}")
    birth = [r for r in rows if _is_birth(r[1])]
    ok, detail = _covers([r[0] for r in birth], LOOP_MS, BIRTH_MS - MAX_GAP_MS)
    _report(checks, f"{s} Birth reported over the whole clip", ok, detail)
    # Negative: after the clip ends the slot no longer reports Birth.
    after = [r for r in rows if r[0] > BIRTH_MS + MAX_GAP_MS and _is_birth(r[1])]
    _report(checks, f"{s} Birth ends with the clip", not after, f"after={after[:3]}")
    if not birth:
        return
    # The clip starts with the create: clip time at the first read.
    t0 = birth[0][1] - birth[0][2]
    _report(checks, f"{s} clip starts in the create loop", 0 <= t0 - birth[0][0] <= SYNC_TOL_MS and t0 <= SYNC_TOL_MS, f"ms={birth[0][0]} clip={t0}")
    # The clip runs in game time: clip time - game ms stays constant.
    offs = [(r[1] - r[2]) - r[0] for r in birth if r[2] > 0]
    spread = max(offs) - min(offs) if offs else 9999
    _report(checks, f"{s} clip runs in game time", spread <= SYNC_TOL_MS, f"offset min={min(offs, default=None)} max={max(offs, default=None)}")
    # Negative: the remaining time never rises while Birth plays.
    rises = [(a[0], b[0]) for a, b in zip(birth, birth[1:]) if b[2] > a[2]]
    _report(checks, f"{s} remaining never rises", not rises, f"rises={rises[:3]}")
    print(f"{s} raw scaled len/rem first={rows[0][3:]} unit height100={checks.value(s, '', 'podH100')}")


def check_none(checks) -> None:
    """Negative: a pod with no play call does not report Birth."""
    s = "pb_none"
    rows = [_lenrem(t) for t in (checks.value(s, "", "trace") or "").split()]
    print(f"{s} raw {rows}")
    _report(checks, f"{s} sampled", len(rows) >= 4, f"rows={len(rows)}")
    _report(checks, f"{s} no Birth without the play call", not any(_is_birth(r[0]) for r in rows), f"lens={[r[0] for r in rows]}")


def _root(ms: float, facing: float, px: int, py: int) -> tuple[float, float, float]:
    x, y, z = pod_birth.world(ms, facing)
    return px + x * 100.0, py + y * 100.0, max(z, 0.0) * 100.0


def check_drop(checks) -> None:
    """Integration: the real drop runs its camera on the engine clip time."""
    s = "pb_drop"
    checks.true(s, "", "podSeen")
    rows = []
    yp_rows = []
    for item in (checks.value(s, "", "trace") or "").split():
        ms, raw, map_t, counts, cam_h, cam_xy, pod_h, yp = item.split(":")
        yp_rows.append(tuple(int(v) / 100.0 for v in yp.split(",")))
        ln, rem = _lenrem(raw)
        reads, misses = (int(v) for v in counts.split("/"))
        cx, cy = (int(v) for v in cam_xy.split(","))
        rows.append((int(ms), ln, rem, int(map_t), reads, misses, int(cam_h), cx, cy, int(pod_h)))
    print(f"{s} raw rows={len(rows)} first={rows[:3]} last={rows[-3:]}")
    _report(checks, f"{s} sampled", len(rows) >= 10, f"rows={len(rows)}")
    if not rows:
        return
    reads = checks.value(s, "", "reads") or 0
    misses = checks.value(s, "", "misses") or 0
    _report(checks, f"{s} map read Birth every drop loop", reads >= 20 and misses == 0, f"reads={reads} misses={misses}")
    birth = [r for r in rows if _is_birth(r[1])]
    # The trace starts with the fall camera, after the arm wait and the zoom
    # (operator 2026-11-20: the pod births before the camera changes).
    ok, detail = _covers([r[0] for r in birth], int(ARM_MAX_MS + ZOOM_LENGTH * 1000 + 2 * LOOP_MS), pod_birth.LAND_MS - MAX_GAP_MS)
    _report(checks, f"{s} engine reports Birth over the whole fall", ok and len(birth) == len(rows), f"{detail} birthRows={len(birth)} of {len(rows)}")
    # The map's clip time and the harness's own read agree (same engine).
    gap = [(r[0], (r[1] - r[2]) - r[3]) for r in birth if r[3] >= 0 and abs((r[1] - r[2]) - r[3]) > SYNC_TOL_MS]
    _report(checks, f"{s} map clip time equals the engine clip time", not gap, f"off={gap[:4]}")
    # Script clock against the animation: the drop starts with Birth.
    offs = [(r[1] - r[2]) - r[0] for r in birth]
    print(f"{s} raw clip - script ms: min={min(offs, default=None)} max={max(offs, default=None)}")
    _report(checks, f"{s} script and Birth in sync", bool(offs) and max(abs(o) for o in offs) <= SYNC_TOL_MS, f"max|off|={max((abs(o) for o in offs), default=None)}")
    # Camera aimed through the pod, engine reads only: the look ray from
    # the eye (target, yaw, pitch, distance) passes the Birth root at the
    # clip time, c_DROP_POD_ARM in front of the eye.
    px, py = (int(v) for v in str(checks.value(s, "", "podAt100") or "0,0").split(","))
    facing = (checks.value(s, "", "podFacing100") or 0) / 100.0
    off = []
    for r, yp in zip(rows, yp_rows):
        t = r[1] - r[2]
        if t >= pod_birth.LAND_MS - LOOP_MS:
            continue
        yaw, pt, dist = yp
        eye = _eye(r[7] / 100.0, r[8] / 100.0, yaw, pt, dist)
        best = min(_ray_gap(eye, yaw, pt, _root(m, facing, px, py)) for m in range(max(t - LOOP_MS, 0), t + 2 * LOOP_MS + 1, 5))
        if best > 1.5:
            off.append((t, round(best, 2)))
    _report(checks, f"{s} look ray through the pod (engine camera)", bool(rows) and not off, f"off={off[:4]}")
    # Smooth: the engine arm only shrinks during the fall (negative: no
    # jump back up), and the target moves without reversing along the yaw.
    live = [(r, yp) for r, yp in zip(rows, yp_rows) if r[1] - r[2] < pod_birth.LAND_MS - LOOP_MS]
    ups = [(a[0][0], a[1][2], b[1][2]) for a, b in zip(live, live[1:]) if b[1][2] > a[1][2] + 0.5]
    _report(checks, f"{s} arm never jumps back out", bool(live) and not ups, f"ups={ups[:4]}")
    back = []
    for a, b in zip(live, live[1:]):
        yaw = math.radians(a[1][0])
        step = ((b[0][7] - a[0][7]) * math.cos(yaw) + (b[0][8] - a[0][8]) * math.sin(yaw)) / 100.0
        if step < -0.2:
            back.append((a[0][0], round(step, 2)))
    _report(checks, f"{s} target never moves back", bool(live) and not back, f"back={back[:4]}")
    # Even speed on each linear Birth leg (engine target and arm per loop):
    # no restart steps. Loops touching a key are skipped. Raw steps printed.
    for lo, hi in ((0, 1600), (1600, pod_birth.LAND_MS)):
        leg = [(r, yp) for r, yp in live if lo + LOOP_MS < r[1] - r[2] < hi - 2 * LOOP_MS]
        steps = []
        for a, b in zip(leg, leg[1:]):
            dt = b[0][0] - a[0][0]
            if dt <= 0:
                continue
            d = math.hypot(b[0][7] - a[0][7], b[0][8] - a[0][8]) / 100.0 + abs(b[1][2] - a[1][2])
            steps.append(round(d / dt * 1000.0, 2))
        print(f"{s} raw speed {lo}-{hi} ms: {steps}")
        if len(steps) >= 2:
            ok = max(steps) <= 1.35 * min(steps) and min(steps) > 0.0
        else:
            ok = True  # short leg: nothing to compare
        _report(checks, f"{s} even camera speed on leg {lo}-{hi}", ok, f"min={min(steps or [0])} max={max(steps or [0])}")
    # Eye behind the pod on its line: arm = 20 + ray from root to ground.
    ang, pitch_d, _, _ = pod_birth.travel()
    # The fall camera starts after the zoom (operator 2026-11-20): the arm
    # at the first traced clip time.
    t0 = rows[0][1] - rows[0][2]
    want0 = CAM_ARM + max(pod_birth.world(t0, 0)[2], 0.0) / math.sin(math.radians(pitch_d))
    d0 = yp_rows[0][2] if yp_rows else 0
    _report(checks, f"{s} arm reaches the pod at the first fall loop", abs(d0 - want0) <= 6.0, f"t0={t0} dist={d0} want~{want0:.1f}")
    # Fixed drop yaw (c_DROP_YAW): pod facing = drop yaw - travel offset,
    # whatever the camera yaw was (engine facing and engine yaw).
    angle, pitch, _, _ = pod_birth.travel()
    before = (checks.value(s, "", "yawBefore100") or 0) / 100.0
    yaw0 = (checks.value(s, "", "dropYaw100") or 0) / 100.0
    want = _wrap(yaw0 - angle)
    got = _wrap(facing)
    print(f"{s} raw yawBefore={before} dropYaw={yaw0} travel={(checks.value(s, '', 'travel100') or 0) / 100.0} facing={facing} want={want}")
    _report(checks, f"{s} pod facing = drop yaw - travel offset", abs(_wrap(got - want)) <= 1.0, f"facing={got:.2f} want={want:.2f}")
    # Negative: the camera yaw before was off the drop yaw, and the facing
    # did not follow it.
    _report(checks, f"{s} camera yaw before was off the drop yaw", abs(_wrap(before - yaw0)) > 10.0, f"before={before} drop={yaw0}")
    _report(checks, f"{s} pod facing ignores the camera yaw", abs(_wrap(got - _wrap(before - angle))) > 10.0, f"facing={got:.2f} fromBefore={_wrap(before - angle):.2f}")
    # The camera chases on the pod's line: engine yaw = travel, pitch = descent.
    bad_yaw = [(r[0], y) for r, (y, _, _) in zip(rows, yp_rows) if r[1] - r[2] < pod_birth.LAND_MS and abs(_wrap(y - yaw0)) > 2.0]
    bad_pitch = [(r[0], pt) for r, (_, pt, _) in zip(rows, yp_rows) if r[1] - r[2] < pod_birth.LAND_MS and abs(_wrap(pt - pitch)) > 2.0]
    print(f"{s} raw yaw,pitch per row={yp_rows[:4]}")
    _report(checks, f"{s} camera yaw on the travel line", bool(yp_rows) and not bad_yaw, f"off={bad_yaw[:4]}")
    _report(checks, f"{s} camera pitch on the descent angle", bool(yp_rows) and not bad_pitch, f"off={bad_pitch[:4]}")
    # The camera eye is on the pod's line behind it: target on the root
    # (checked above) plus yaw and pitch along the path.
    # Negative: a camera on the landing spot at arm 20 does not see the pod start.
    neg = _ray_gap(_eye(px / 100.0, py / 100.0, yaw0, pitch_d, CAM_ARM), yaw0, pitch_d, _root(0, facing, px, py))
    _report(checks, f"{s} negative: plain arm 20 misses the pod start", neg > 10.0, f"gap={neg:.1f}")
    # Negative: the unit is never lifted; the model does the fall.
    ground = checks.value(s, "", "groundH100") or 0
    lifted = [(r[0], r[9]) for r in rows if abs(r[9] - ground) > 5]
    _report(checks, f"{s} pod unit stays on the ground", not lifted, f"lifted={lifted[:3]}")
    # Touchdown on the clip's land key.
    last_t = (birth[-1][1] - birth[-1][2]) if birth else -1
    print(f"{s} raw landMs={checks.value(s, '', 'landMs')} last clip={last_t}")
    _report(checks, f"{s} touchdown at the land key", pod_birth.LAND_MS - 2 * LOOP_MS <= last_t <= pod_birth.LAND_MS + LOOP_MS, f"last clip={last_t}")
    print(f"{s} raw pods at create={checks.value(s, '', 'podsAtCreate')} mid={checks.value(s, '', 'podsMid')} heroAt10={checks.value(s, '', 'heroAt10')} podAt100={checks.value(s, '', 'podAt100')}")
    checks.gt(s, "", "landings", 0)
    checks.true(s, "", "heroAlive")


def check_dof(checks) -> None:
    """REQ-CAMERA-DOF strengths per case, from the engine arm. The blur
    itself has no engine getter: operator check."""
    s = "pb_dof"
    rows = {}
    for tag in ("d10", "d40", "aim10", "after10", "min2"):
        raw = str(checks.value(s, "", tag) or "0,0,0")
        print(f"{s} raw {tag} dist100,near100,far100 = {raw}")
        d, n, f = (int(v) / 100.0 for v in raw.split(","))
        rows[tag] = (d, n, f)
    def near(d): return max(min((d - 1) / 39, 1), 0)
    def far(d): return max(min((d - 3) / 37, 1), 0)
    for tag in ("d10", "d40", "after10", "min2"):
        d, n, f = rows[tag]
        _report(checks, f"{s} {tag}: near/far follow the arm", abs(n - near(d)) < 0.02 and abs(f - far(d)) < 0.02, f"d={d} near={n} far={f}")
    _report(checks, f"{s} R-DOF-1/3 max arm: full near and far", rows["d40"][1] >= 0.99 and rows["d40"][2] >= 0.99, str(rows["d40"]))
    _report(checks, f"{s} R-DOF-3 negative: no far below arm 3", rows["min2"][2] == 0.0, str(rows["min2"]))
    _report(checks, f"{s} R-DOF-2/4 aim: full near, no far", rows["aim10"][1] >= 0.99 and rows["aim10"][2] == 0.0, str(rows["aim10"]))


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="podbirth",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["podbirth"],
        bank_names=PROFILE_BANKS["podbirth"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "podbirth.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/podbirth/common",
            "scripts/test/podbirth/podbirth",
        ),
        init_calls=("gt_PodBirthTest_Init();",),
    )


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    checks.eq("pb_end", "", "RealClicks", 0)
    check_plays(checks)
    check_none(checks)
    check_drop(checks)
    check_dof(checks)
    s = "pb_dofprobe"
    print(f"{s} raw arm={checks.value(s, '', 'arm')} " + " ".join(f"{k}={checks.value(s, '', k)}" for k in "ABCDE"))
    _report(checks, f"{s} probe ran (blur per label: operator check)", checks.value(s, "", "done") == 1, "")


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="podbirth",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["podbirth"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["podbirth"],
        ready_section="pb_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
