"""Intro profile (REQ-INTRO, SPEC-INTRO 4.2).

Every check reads the test bank. Camera yaw, pitch, distance and target are
engine getters; FOV, height offset and depth of field have no getter and are
script state (SPEC-INTRO F5). How a shot looks, the blur, the music and the
prompt's look are operator checks (REQ-INTRO 4).

Groups: boot (always runs), shots, wrap, gate, deploy. Deploy ends the
intro and runs last.
"""

from __future__ import annotations

import math
import os
import time
from pathlib import Path

from hitvolumes import intro_shots as S
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .herodrop import birth_follow
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS

ROOT = project_root()
GROUPS = ("boot", "shots", "wrap", "gate", "deploy")
LOOP_MS = 62.5
STATE_LOOP, STATE_ZOOM, STATE_FALL, STATE_DONE = 1, 2, 3, 4
ANGLE_TOL = 2.0       # degrees, engine against script
DIST_TOL = 0.03       # share, engine against script
FIRST_CUT_MS = 1500   # gt_MapInit waits 0.5 s real time before the intro starts
SEED_TERRAN, SEED_ZERG = 5, 10
ZOOM_MAX_MS = 400 + 1 * 63  # R-INTRO-10, seen at loop resolution
HOST_DEADLINE_S = 240.0


def selected_group() -> str:
    group = os.environ.get("SC2_TEST_GROUP", "all")
    if group != "all" and group not in GROUPS:
        raise SystemExit(f"unknown intro group: {group}; choose all or one of {', '.join(GROUPS)}")
    return group


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="intro",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["intro"],
        bank_names=PROFILE_BANKS["intro"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "intro.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/intro/common",
            "scripts/test/intro/intro",
        ),
        init_calls=(f'gv_dbgGroup = "{selected_group()}";', "gt_IntroTest_Init();"),
    )


def _docs() -> Path:
    prefix = Path(os.environ.get("SC2_GAME_PREFIX", str(Path.home() / "Games" / "battlenet-prefix")))
    return Path(os.environ.get("SC2_DOCUMENTS", str(prefix / "pfx/drive_c/users/steamuser/Documents/StarCraft II")))


def on_ready(ctx, data: dict) -> None:
    """Inject the keys the harness asks for, until the run is done."""
    from .. import input_driver
    from ..bank import find_latest_bank, read_bank

    docs = _docs()
    seen = 0
    deadline = time.monotonic() + HOST_DEADLINE_S
    while time.monotonic() < deadline:
        path = find_latest_bank(docs, PROFILE_BANKS["intro"][0], 0.0)
        bank = None
        if path is not None:
            try:
                bank = read_bank(path)
            except RuntimeError:
                bank = None
        if bank:
            if bank.get("meta", {}).get("done") == 1:
                return
            host = bank.get("intro_host", {})
            req = host.get("req") or 0
            if req > seen:
                seen = req
                keys = [k for k in str(host.get("keys") or "").split(",") if k]
                hold = int(host.get("holdMs") or 60)
                gap = int(host.get("gapMs") or 0)
                input_driver.focus()
                for i, key in enumerate(keys):
                    if i:
                        time.sleep(gap / 1000.0)
                    input_driver.key(key, hold)
                print(f"host keys req={req} keys={keys} hold={hold} gap={gap}", flush=True)
        time.sleep(0.05)
    ctx.errors.append("host key loop: run not done before the deadline")


def _report(checks, name: str, ok: bool, detail: str) -> None:
    status = "PASS" if ok else "FAIL"
    print(f"{name}: {detail} {status}")
    checks.results.append({"section": name, "tag": "", "key": "", "got": detail, "want": "", "status": status})
    if not ok:
        checks.failures += 1


def _angle(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def check_boot(checks) -> None:
    s = "boot"
    # R-INTRO-1: the loop state from the first loop; the first cut soon after.
    checks.eq(s, "", "earlyState", STATE_LOOP)
    checks.lt(s, "", "firstCutMs", FIRST_CUT_MS)
    for t in ("t0", "t1", "t6"):
        checks.eq(s, t, "State", STATE_LOOP)
        checks.true(s, t, "Active")
        # R-INTRO-2, 8: no map dialog, cinematic mode, prompt on.
        checks.eq(s, t, "Dialogs", 0)
        # No hero pod before SPACE (engine count, whole map).
        checks.eq(s, t, "HeroPodUnits", 0)
        checks.true(s, t, "Cinematic")
        checks.true(s, t, "Prompt")
        # R-INTRO-9: hero out of the world, no input trigger on.
        checks.true(s, t, "Alive")
        checks.true(s, t, "Hidden")
        checks.true(s, t, "Paused")
        checks.false(s, t, "Selectable")
        checks.false(s, t, "Selected")
        checks.eq(s, t, "Orders", 0)
        checks.eq(s, t, "TrigOn", 0)
        checks.false(s, t, "JumpKeyOn")
        checks.true(s, t, "TickOn")
        # R-INTRO-15: the theme plays; the id resolves (U5).
        checks.true(s, t, "Music")
        checks.true(s, t, "MusicValid")
        checks.true(s, t, "SilenceValid")
    print(f"{s} raw dialog masks t0={checks.value(s, 't0', 'DialogMask')} t1={checks.value(s, 't1', 'DialogMask')} t6={checks.value(s, 't6', 'DialogMask')} reshown t6={checks.value(s, 't6', 'DialogReshown')}")
    checks.gt(s, "t0", "DialogsKept", 0)
    checks.gt(s, "t0", "TrigKept", 0)
    for key in ("HeroX10", "HeroY10"):
        checks.eq(s, "t6", key, checks.value(s, "t0", key))
    # R-INTRO-13: both groups at the X at 1 s, both hurt by 6 s.
    checks.eq(s, "", "seeded", SEED_TERRAN + SEED_ZERG)
    checks.eq(s, "", "seedTerran", SEED_TERRAN)
    checks.eq(s, "", "seedZerg", SEED_ZERG)
    checks.gt(s, "", "t1TerranSeedAtX", 0)
    checks.gt(s, "", "t1ZergSeedAtX", 0)
    print(f"{s} raw t1 near X: terran={checks.value(s, '', 't1TerranAtX')} zerg={checks.value(s, '', 't1ZergAtX')}")
    checks.gt(s, "", "t6TerranHurt100", 0)
    checks.gt(s, "", "t6ZergHurt100", 0)
    # Negative: no extra units on the other lanes.
    checks.eq(s, "", "laneUnits6", checks.value(s, "", "laneUnits0"))
    # R-INTRO-14: the world runs.
    clock0 = checks.value(s, "t0", "Clock100") or 0
    checks.gt(s, "t6", "Clock100", clock0 + 500)
    left0 = checks.value(s, "t0", "SpawnLeft100") or 0
    checks.lt(s, "t6", "SpawnLeft100", left0)
    # R-INTRO-11 negative: a reinforcement in the loop drops no hero pod.
    checks.eq(s, "treinf", "Pods", checks.value(s, "t0", "Pods"))
    checks.false(s, "treinf", "Pending")
    checks.true(s, "treinf", "Hidden")
    checks.eq(s, "treinf", "State", STATE_LOOP)


def _shot_row(shot: S.Shot, pass_: int, u: float) -> tuple[list[S.Sample], float]:
    """Table samples over the window the script value can come from."""
    span = 3 * (LOOP_MS / 1000.0) / shot.length
    return [S.sample(shot, min(1.0, u + span * k / 6), pass_ == 1) for k in range(7)], span


def _within(value: float, samples: list[float], tol: float) -> bool:
    return min(samples) - tol <= value <= max(samples) + tol


def check_shots(checks) -> None:
    section = checks.data.get("shots", {})
    _report(checks, "shots done", section.get("done") == 1, f"done={section.get('done')}")
    print(
        f"shots raw ground hero={section.get('groundHero100')} x={section.get('groundX100')} hybrid={section.get('groundHybrid100')} "
        f"heroZ={section.get('heroZ100')} hm={section.get('heightMapGround')} xAir={section.get('xAir100')} xGlide={section.get('xGlide100')} "
        f"xFlat={section.get('xGroundFlat100')} marineZ={section.get('marineZ100')}"
    )
    count = 0
    for row, shot in enumerate(S.SHOTS):
        for pass_ in ((0, 1) if shot.variant != S.VAR_NONE else (0,)):
            for u10 in (1, 5, 9):
                key = f"s{row}p{pass_}u{u10}"
                raw = section.get(key)
                if raw is None:
                    _report(checks, f"shots {key}", False, "missing")
                    continue
                count += 1
                v = [int(x) for x in str(raw).split("/")]
                shot_i, pass_i, eyaw, epitch, edist, syaw, spitch, sdist, sfov, sh, sground, dof, tgt, tx, ty, ex, ey, gap = v
                print(f"shots {key} raw {raw}")
                name = f"shots {shot.name} p{pass_} u{u10 / 10:.1f}"
                _report(checks, f"{name} row", shot_i == row and pass_i == pass_, f"shot={shot_i} pass={pass_i}")
                # R-INTRO-4: the engine follows the script values.
                _report(checks, f"{name} engine yaw", _angle(eyaw / 100, syaw / 100) <= ANGLE_TOL, f"engine={eyaw / 100} script={syaw / 100}")
                # The engine reads pitch in 0..360: -5 reads 355.
                _report(checks, f"{name} engine pitch", _angle(epitch / 100, spitch / 100) <= ANGLE_TOL, f"engine={epitch / 100} script={spitch / 100}")
                _report(checks, f"{name} engine distance", abs(edist - sdist) <= DIST_TOL * sdist, f"engine={edist / 100} script={sdist / 100}")
                # CameraGetTarget reads (12, 8) here, also in the tick after
                # the pan (SPEC-INTRO F12, run 20261117-024416). Raw only; the
                # framed target is an operator check.
                print(f"{name} raw engine target=({ex / 100}, {ey / 100}) dist100={tgt} tickGap100={gap} script=({tx / 100}, {ty / 100})")
                # The script values are the table's at this time.
                rows, _ = _shot_row(shot, pass_, u10 / 10)
                checks_ = (
                    ("yaw", syaw / 100, [r.yaw for r in rows], 0.05),
                    ("pitch", spitch / 100, [r.pitch for r in rows], 0.05),
                    ("distance", sdist / 100, [r.dist for r in rows], 0.05),
                    ("fov", sfov / 100, [r.fov for r in rows], 0.05),
                    ("target x", tx / 100, [r.x for r in rows], 0.05),
                    ("target y", ty / 100, [r.y for r in rows], 0.05),
                )
                for label, got, want, tol in checks_:
                    _report(checks, f"{name} table {label}", _within(got, want, tol), f"script={got:.2f} table={min(want):.2f}..{max(want):.2f}")
                z = sh / 100
                _report(checks, f"{name} table height", _within(z, [r.z for r in rows], 0.05), f"z={z:.2f} rawGround={sground / 100}")
                # R-INTRO-6: depth of field in S2 only.
                _report(checks, f"{name} dof", dof == int(shot.dof), f"dof={dof}")
                if shot.ease == "Z":
                    # R-INTRO-7 on the engine distance.
                    k = edist / 100 * math.tan(math.radians(sfov / 200))
                    _report(checks, f"{name} dolly invariant", abs(k - S.dolly_k()) <= 0.03 * S.dolly_k(), f"k={k:.3f} want={S.dolly_k():.3f}")
    _report(checks, "shots sampled", count == 30, f"samples={count}")


def check_wrap(checks) -> None:
    s = "wrap"
    checks.eq(s, "t0", "Shot", len(S.SHOTS) - 1)
    checks.eq(s, "t1", "Shot", 0)
    checks.eq(s, "t1", "Pass", (checks.value(s, "t0", "Pass") or 0) + 1)
    length = checks.value(s, "", "s7LenMs") or 0
    checks.between(s, "", "s7Ms", length - 2 * LOOP_MS, length + 3 * LOOP_MS)
    checks.eq(s, "", "afterS7", 7)


def check_gate(checks) -> None:
    s = "gate"
    for t in ("tw", "t1", "tf"):
        for key in ("HeroX10", "HeroY10", "HeroTag", "JumpPresses", "Pods"):
            checks.eq(s, t, key, checks.value(s, "t0", key))
        checks.eq(s, t, "Orders", 0)
        checks.eq(s, t, "State", STATE_LOOP)
        checks.eq(s, t, "Shot", 2)
        checks.false(s, t, "OrderMode")
        checks.true(s, t, "HeroIsTosh")
        checks.true(s, t, "Hidden")
        checks.eq(s, t, "TrigOn", 0)
        yaw, syaw = checks.value(s, t, "CamYaw100"), checks.value(s, t, "InYaw100")
        dist, sdist = checks.value(s, t, "CamDist100"), checks.value(s, t, "InDist100")
        ok = None not in (yaw, syaw, dist, sdist) and _angle(yaw / 100, syaw / 100) <= ANGLE_TOL and abs(dist - sdist) <= DIST_TOL * sdist
        _report(checks, f"{s} {t} camera is the row's", ok, f"yaw={yaw}/{syaw} dist={dist}/{sdist}")


def check_deploy(checks) -> None:
    s = "deploy"
    # R-INTRO-10: SPACE starts the zoom; the prompt and the music go.
    checks.eq(s, "", "seenState", STATE_ZOOM)
    checks.false(s, "tzoom", "Prompt")
    checks.false(s, "tzoom", "Music")
    checks.eq(s, "tzoom", "Deploys", 1)
    zoom = checks.value(s, "", "zoom") or ""
    print(f"{s} raw zoom {zoom}")
    fovs = [int(r.split(":")[1].split("/")[1]) for r in zoom.split()]
    _report(checks, f"{s} crash zoom narrows the lens", len(fovs) >= 2 and fovs[-1] < fovs[0], f"fov100={fovs}")
    checks.lt(s, "", "zoomToFallMs", ZOOM_MAX_MS)
    checks.eq(s, "tfall", "State", STATE_FALL)
    checks.true(s, "", "podSeen")
    checks.eq(s, "", "podType", "SCOBAHeroPod")
    checks.lt(s, "", "podToDrop100", 100)
    # The stock drop; the camera on the Birth root (SPEC-HERO-DROP 3).
    fall = birth_follow(checks, s, checks.value(s, "", "landHeroH100") or 0)
    # Negative: the hero stays hidden while the pod falls.
    shown = [r[0] for r in fall if r[5] == 0]
    _report(checks, f"{s} hero hidden during the fall", not shown, f"shownAt={shown[:4]}")
    # R-INTRO-12: touchdown.
    pods = checks.value(s, "t0", "Pods") or 0
    landings = checks.value(s, "t0", "Landings") or 0
    for t in ("tland", "tafter"):
        checks.eq(s, t, "State", STATE_DONE)
        checks.false(s, t, "Active")
        checks.true(s, t, "Alive")
        checks.false(s, t, "Hidden")
        checks.false(s, t, "Paused")
        checks.true(s, t, "Selectable")
        checks.eq(s, t, "Direct", 1)
        checks.false(s, t, "Cinematic")
        checks.eq(s, t, "Dialogs", checks.value("boot", "t0", "DialogsKept"))
        checks.eq(s, t, "TrigOn", checks.value("boot", "t0", "TrigKept"))
        checks.true(s, t, "JumpKeyOn")
        checks.false(s, t, "TickOn")
        checks.false(s, t, "Dof")
        checks.false(s, t, "Music")
        checks.false(s, t, "Prompt")
        checks.false(s, t, "Pending")
        checks.false(s, t, "DropIntro")
        checks.true(s, t, "HeroTps")
        checks.eq(s, t, "Pods", pods + 1)
        checks.eq(s, t, "Landings", landings + 1)
        checks.eq(s, t, "HeroTag", checks.value(s, "t0", "HeroTag"))
        checks.lt(s, t, "HeroToPod100", 150)
        # R-INTRO-11 negative: no jump from any SPACE; no second deploy.
        checks.eq(s, t, "JumpPresses", checks.value(s, "t0", "JumpPresses"))
        checks.eq(s, t, "Deploys", 1)
    checks.eq(s, "tland", "Life", checks.value(s, "tland", "LifeMax"))
    # The no-intro defaults: Attack single, Chase stand, Point & Click.
    checks.eq(s, "tafter", "Single", 1)
    checks.eq(s, "tafter", "Stand", 1)
    checks.false(s, "tafter", "TpsMode")
    checks.eq(s, "tafter", "CamDesired100", 150)
    # Both extra presses were seen and ignored.
    checks.gt(s, "tafter", "SpaceIgnored", (checks.value(s, "t0", "SpaceIgnored") or 0) + 1)


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    checks.eq("meta", "", "done", 1)
    checks.eq("intro_end", "", "RealClicks", 0)
    group = selected_group()
    check_boot(checks)
    if group in ("all", "shots"):
        check_shots(checks)
    if group in ("all", "wrap"):
        check_wrap(checks)
    if group in ("all", "gate"):
        check_gate(checks)
    if group in ("all", "deploy"):
        check_deploy(checks)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="intro",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["intro"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["intro"],
        ready_section="intro_start",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
