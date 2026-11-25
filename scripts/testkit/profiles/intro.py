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

import workpaths
from hitvolumes import intro_shots as S
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .herodrop import birth_follow, scene_on
from .herodrop_parts.herodrop_land import check_start_state
from .herodrop_parts.herodrop_zoom import (
    ARM_MAX_MS,
    PHASE_ARM,
    PHASE_ZOOM,
    PHASES,
    zoom_armed,
    zoom_follow,
)
from .registry import PROFILE_BANKS, profile_output

ROOT = project_root()
GROUPS = ("boot", "shots", "wrap", "gate", "seats", "deploy")
LOOP_MS = 62.5
STATE_LOOP, STATE_DROP, STATE_DONE = 1, 2, 3
PHASE_FALL = 3  # drop phase (core/hero_drop.galaxy)
ANGLE_TOL = 2.0       # degrees, engine against script
DIST_TOL = 0.03       # share, engine against script
FIRST_CUT_MS = 1500   # gt_MapInit waits 0.5 s real time before the intro starts
SEED_TERRAN, SEED_ZERG = 5, 10
# R-INTRO-10: the pod births first (at most c_DROP_ARM_MAX), then the
# 0.35 s zoom; seen at loop resolution (operator 2026-11-20).
ZOOM_MAX_MS = ARM_MAX_MS + 400 + 1 * 63
COUNT_BEEPS = 3  # one beep on 3, 2 and 1 (operator 2026-11-20)
HOST_DEADLINE_S = 240.0


def selected_group() -> str:
    group = os.environ.get("SC2_TEST_GROUP", "all")
    if group != "all" and group not in GROUPS:
        raise SystemExit(f"unknown intro group: {group}; choose all or one of {', '.join(GROUPS)}")
    return group


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="intro",
        source=workpaths.path("SC2_BUILT_MAP"),
        output=profile_output("intro"),
        bank_names=PROFILE_BANKS["intro"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "intro_seats.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "intro.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/intro/common",
            "scripts/test/intro/intro_seats",
            "scripts/test/intro/intro",
        ),
        init_calls=(f'gv_dbgGroup = "{selected_group()}";', "gt_IntroTest_Init();"),
    )


def _docs() -> Path:
    return workpaths.path("SC2_DOCUMENTS")


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
        # Per-player hold: player 1 held, no trigger disabled, player 2 not held.
        checks.true(s, t, "InputHeld")
        checks.false(s, t, "InputHeld2")
        checks.eq(s, t, "TrigOn", checks.value(s, t, "TrigAll"))
        checks.true(s, t, "JumpKeyOn")
        checks.true(s, t, "TickOn")
        # R-INTRO-15: the theme plays; the id resolves (U5).
        checks.true(s, t, "Music")
        checks.true(s, t, "MusicValid")
        checks.true(s, t, "HumValid")
        checks.true(s, t, "SilenceValid")
    print(f"{s} raw dialog masks t0={checks.value(s, 't0', 'DialogMask')} t1={checks.value(s, 't1', 'DialogMask')} t6={checks.value(s, 't6', 'DialogMask')} reshown t6={checks.value(s, 't6', 'DialogReshown')}")
    checks.gt(s, "t0", "DialogsKept", 0)
    checks.gt(s, "t0", "TrigAll", 0)
    for key in ("HeroX10", "HeroY10"):
        checks.eq(s, "t6", key, checks.value(s, "t0", key))
    # R-INTRO-13: both groups start back from the X, walk in, meet at the X
    # and fight there.
    checks.eq(s, "", "seeded", SEED_TERRAN + SEED_ZERG)
    checks.eq(s, "", "seedTerran", SEED_TERRAN)
    checks.eq(s, "", "seedZerg", SEED_ZERG)
    print(f"{s} raw seed t1ToX10 terran={checks.value(s, '', 't1TerranToX10')} zerg={checks.value(s, '', 't1ZergToX10')} "
          f"meetMs={checks.value(s, '', 'meetMs')} fightMs={checks.value(s, '', 'fightMs')} "
          f"t1 near X: terran={checks.value(s, '', 't1TerranAtX')} zerg={checks.value(s, '', 't1ZergAtX')}")
    # Negative: no fight at the start (operator 2026-11-17).
    checks.eq(s, "", "t1TerranHurt100", 0)
    checks.eq(s, "", "t1ZergHurt100", 0)
    checks.gt(s, "", "t1TerranToX10", 160)
    checks.gt(s, "", "t1ZergToX10", 160)
    checks.gt(s, "", "meetMs", -1)
    checks.lt(s, "", "fightMs", 640 * 62)
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
    """Table samples over the window the script value can come from: the
    goto, two waited loops, one loop of event order, and the tick's one-loop
    lead (systems/intro.galaxy gf_IntroTickSeat: lv_t + c_INTRO_TICK)."""
    span = 4 * (LOOP_MS / 1000.0) / shot.length
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
                # Scene sound: Doodad channel down in S4 only; hum in S9 only
                # (operator 2026-11-18). Script flags; the loudness is an operator check.
                _report(checks, f"{name} quiet", bool(section.get(key + "Quiet")) == shot.name.startswith("S4"), f"quiet={section.get(key + 'Quiet')}")
                _report(checks, f"{name} hum", bool(section.get(key + "Hum")) == shot.name.startswith("S9"), f"hum={section.get(key + 'Hum')}")
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
    _report(checks, "shots sampled", count == 3 * sum(2 if s.variant != S.VAR_NONE else 1 for s in S.SHOTS), f"samples={count}")


def check_wrap(checks) -> None:
    s = "wrap"
    checks.eq(s, "t0", "Shot", len(S.SHOTS) - 1)
    checks.eq(s, "t1", "Shot", 0)
    checks.eq(s, "t1", "Pass", (checks.value(s, "t0", "Pass") or 0) + 1)
    # The Psi Destroyer hum: on in S9, off after the cut to S1 (2026-11-18).
    checks.true(s, "t0", "Hum")
    checks.false(s, "t1", "Hum")
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
        checks.true(s, t, "InputHeld")
        checks.eq(s, t, "TrigOn", checks.value(s, t, "TrigAll"))
        yaw, syaw = checks.value(s, t, "CamYaw100"), checks.value(s, t, "InYaw100")
        dist, sdist = checks.value(s, t, "CamDist100"), checks.value(s, t, "InDist100")
        ok = None not in (yaw, syaw, dist, sdist) and _angle(yaw / 100, syaw / 100) <= ANGLE_TOL and abs(dist - sdist) <= DIST_TOL * sdist
        _report(checks, f"{s} {t} camera is the row's", ok, f"yaw={yaw}/{syaw} dist={dist}/{sdist}")


def check_deploy(checks) -> None:
    s = "deploy"
    # R-INTRO-10: SPACE starts the drop sequence; the prompt goes.
    checks.eq(s, "", "seenState", STATE_DROP)
    # The pod exists and births before the camera changes (2026-11-20).
    phase = checks.value(s, "tzoom", "Phase")
    _report(checks, f"{s} tzoom drop in ARM or the zoom", phase in (PHASE_ARM, PHASE_ZOOM), f"phase={phase}")
    checks.eq(s, "t0", "Phase", 0)  # negative: no drop in the loop
    zoom_armed(checks, s, go_loop=False)
    # The intro shot keeps the camera until the zoom; released after.
    checks.eq(s, "tzoom", "CamHeld", phase == PHASE_ARM)
    checks.false(s, "tfall", "CamHeld")
    checks.false(s, "t0", "CamHeld")  # negative: not in the loop
    # One beep per countdown number; none before SPACE (negative).
    checks.true(s, "t0", "BeepValid")
    beeps0 = checks.value(s, "t0", "Beeps") or 0
    checks.eq(s, "tzoom", "Beeps", beeps0 + COUNT_BEEPS)
    checks.eq(s, "tland", "Beeps", beeps0 + COUNT_BEEPS)
    # Countdown 3, 2, 1 on the prompt line, then the zoom (~3 s after SPACE).
    checks.eq(s, "", "countTrace", "321")
    count_ms = checks.value(s, "", "countMs") or 0
    # countMs: from the engine's press (gv_introCountAt) to the zoom;
    # requestMs adds the host's key latency (raw only).
    print(f"{s} raw countMs={count_ms} requestMs={checks.value(s, '', 'requestMs')} keyLatencyMs={checks.value(s, '', 'keyLatencyMs')} thirdState={checks.value(s, '', 'thirdState')}")
    # The third press reached the engine in the drop; else the no-jump
    # check below would test the wrong state.
    checks.true(s, "", "thirdSent")
    checks.eq(s, "", "thirdState", STATE_DROP)
    _report(checks, f"{s} zoom starts about 3 s after SPACE", 2500 <= count_ms <= 4000, f"ms={count_ms}")
    checks.false(s, "tzoom", "Prompt")  # negative: the countdown line is gone
    # The theme plays on after SPACE; it stops at touchdown (2026-11-18).
    checks.true(s, "tzoom", "Music")
    checks.true(s, "tfall", "Music")
    checks.eq(s, "tzoom", "Deploys", 1)
    # R-DROP-10: the drop's own zoom, checked as in herodrop drop_main.
    zoom_follow(checks, s)
    checks.lt(s, "", "zoomToFallMs", ZOOM_MAX_MS)
    checks.eq(s, "tfall", "State", STATE_DROP)
    checks.eq(s, "tfall", "Phase", PHASE_FALL)
    checks.eq(s, "", "phases", PHASES)
    checks.true(s, "", "podSeen")
    checks.eq(s, "", "podType", "SCOBAHeroPod")
    # The same drop scene as a revive (R-DROP-10), over the intro's own.
    for t in ("tzoom", "tfall"):
        scene_on(checks, s, t, True)
        checks.true(s, t, "SceneIntro")
    checks.false(s, "t0", "SceneDrop")  # negative: not before SPACE
    # R-INTRO-18: no chat display from the loop to touchdown.
    frame = checks.value(s, "t0", "ChatFrame") or 0
    _report(checks, f"{s} chat frame hooked", frame > 0, f"ChatFrame={frame}")
    for t in ("t0", "tzoom", "tfall"):
        checks.true(s, t, "ChatHidden")
        checks.false(s, t, "ChatShown")
        # R-INTRO-19: hidden by relative mouse mode, not by a cursor send.
        checks.true(s, t, "MouseHidden")
    rule = [t for t in ("t0", "tzoom", "tfall") if checks.value(s, t, "CursorRule")]
    print(f"{s} raw cursor rule true at: {rule}")
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
        checks.false(s, t, "SceneDrop")
        checks.false(s, t, "SceneIntro")
        # Negative for R-INTRO-18: the chat display is back after the intro.
        checks.false(s, t, "ChatHidden")
        checks.true(s, t, "ChatShown")
        # Negative for R-INTRO-19: after touchdown the mouse hide is off and
        # the cursor and mouse look follow the control rule.
        checks.false(s, t, "MouseHidden")
        checks.eq(s, t, "SentCursor", checks.value(s, t, "CursorRule"))
        checks.eq(s, t, "SentRelative", not checks.value(s, t, "CursorRule"))
        checks.eq(s, t, "Phase", 0)
        checks.eq(s, t, "Dialogs", checks.value("boot", "t0", "DialogsKept"))
        checks.false(s, t, "InputHeld")
        checks.eq(s, t, "TrigOn", checks.value(s, t, "TrigAll"))
        checks.true(s, t, "JumpKeyOn")
        checks.false(s, t, "TickOn")
        checks.false(s, t, "Dof")
        checks.false(s, t, "Music")
        checks.false(s, t, "Prompt")
        checks.false(s, t, "Pending")
        checks.false(s, t, "InputHeld")
        checks.true(s, t, "HeroTps")
        checks.eq(s, t, "Pods", pods + 1)
        checks.eq(s, t, "Landings", landings + 1)
        checks.eq(s, t, "HeroTag", checks.value(s, "t0", "HeroTag"))
        checks.lt(s, t, "HeroToPod100", 150)
        # R-INTRO-11 negative: no jump from any SPACE; no second deploy.
        checks.eq(s, t, "JumpPresses", checks.value(s, "t0", "JumpPresses"))
        checks.eq(s, t, "Deploys", 1)
    checks.eq(s, "tland", "Life", checks.value(s, "tland", "LifeMax"))
    # The toggle defaults: Attack single, Chase stand. Touchdown start state
    # (operator 2026-11-20): TPS, arm 1.0, pitch 0 (was Point & Click, 1.5).
    checks.eq(s, "tafter", "Single", 1)
    checks.eq(s, "tafter", "Stand", 1)
    check_start_state(checks, s, "tafter")
    # Both extra presses were seen and ignored.
    checks.gt(s, "tafter", "SpaceIgnored", (checks.value(s, "t0", "SpaceIgnored") or 0) + 1)


def check_seats(checks) -> None:
    """R-INTRO-16: seat 2 deploys and lands; seat 1 stays in its loop."""
    s = "seats"
    keys = ("State", "Active", "Held", "Cinematic", "Phase", "Music", "Prompt", "Deploys", "Pods", "HeroHidden", "HeroAlive")
    for t in ("t0", "tfall", "tdone"):
        for p in (1, 2):
            print(f"{s} raw {t}p{p}: " + " ".join(f"{k}={checks.value(s, f'{t}p{p}', k)}" for k in keys))
    print(f"{s} raw fallSeen={checks.value(s, '', 'fallSeen')} doneMs={checks.value(s, '', 'doneMs')}")
    for p in (1, 2):
        checks.eq(s, f"t0p{p}", "State", STATE_LOOP)
        checks.true(s, f"t0p{p}", "Held")
        checks.true(s, f"t0p{p}", "Prompt")
    checks.true(s, "", "fallSeen")
    checks.false(s, "tfallp2", "Prompt")
    checks.true(s, "tfallp2", "Music")  # on until touchdown (2026-11-18)
    checks.true(s, "tfallp2", "Held")
    checks.true(s, "tfallp2", "Cinematic")
    checks.eq(s, "tfallp2", "Phase", PHASE_FALL)
    checks.eq(s, "tdonep2", "State", STATE_DONE)
    checks.eq(s, "tdonep2", "Phase", 0)
    checks.false(s, "tdonep2", "Active")
    checks.false(s, "tdonep2", "Held")
    checks.false(s, "tdonep2", "Cinematic")
    checks.false(s, "tdonep2", "Music")
    checks.true(s, "tdonep2", "HeroAlive")
    checks.false(s, "tdonep2", "HeroHidden")
    checks.gt(s, "tdonep2", "Pods", 0)
    # Negative: seat 1 untouched by seat 2's deploy, fall and touchdown.
    for t in ("tfall", "tdone"):
        checks.eq(s, f"{t}p1", "State", STATE_LOOP)
        checks.true(s, f"{t}p1", "Active")
        checks.true(s, f"{t}p1", "Held")
        checks.true(s, f"{t}p1", "Cinematic")
        checks.eq(s, f"{t}p1", "Phase", 0)
        checks.true(s, f"{t}p1", "Music")
        checks.true(s, f"{t}p1", "Prompt")
        checks.true(s, f"{t}p1", "HeroHidden")
        checks.eq(s, f"{t}p1", "Deploys", checks.value(s, "t0p1", "Deploys"))
        checks.eq(s, f"{t}p1", "Pods", checks.value(s, "t0p1", "Pods"))


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
    if group in ("all", "seats"):
        check_seats(checks)
    if group in ("all", "deploy"):
        check_deploy(checks)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="intro",
        map_name="SCOBA.SC2Map",
        map_source=profile_output("intro"),
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
