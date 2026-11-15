"""WASD / TPS profile.

Every check reads the test bank. Nothing here needs visual inspection.
"""

from __future__ import annotations

import math
import os
from pathlib import Path

from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .combat import _delta, _report, _walk_scale, _yaw_off
from .registry import PROFILE_BANKS, PROFILE_OUTPUTS
from .tps_pick import check_pick

ROOT = project_root()

def selected_group() -> str:
    """One scenario group for a fast run, or `all` for the full suite."""
    group = os.environ.get("SC2_TEST_GROUP", "all")
    if group != "all" and group not in GROUPS:
        raise SystemExit(f"unknown tps group: {group}; choose all or one of {', '.join(GROUPS)}")
    return group


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="tps",
        source=ROOT / "out" / "SCOBA256.SC2Map",
        output=PROFILE_OUTPUTS["tps"],
        bank_names=PROFILE_BANKS["tps"],
        galaxy_files=(
            ROOT / "scripts" / "testkit" / "galaxy" / "common.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "tps.galaxy",
            ROOT / "scripts" / "testkit" / "galaxy" / "tpspick.galaxy",
        ),
        galaxy_includes=(
            "scripts/test/tps/common",
            "scripts/test/tps/tps",
            "scripts/test/tps/tpspick",
        ),
        init_calls=(f'gv_dbgGroup = "{selected_group()}";', "gt_TpsTest_Init();"),
    )


def on_ready(ctx, data: dict) -> None:
    return


def _tps_move(checks, section: str, want_forward: int, want_left: int, lower: int, direction: int) -> None:
    """R-TPS-10, R-TPS-11: facing stays on the camera yaw; the hero moves on the input axis."""
    start = _yaw_off(checks, section, "t0000")
    _report(checks, f"{section} starts turned away", start is not None and start >= 90, f"off={start}")
    checks.false(section, "t0000", "TpsMode")
    checks.eq(section, "t0000", "NoTurn", 0)
    for tag in ("ttps", "tmove", "tstop", "tturn"):
        checks.true(section, tag, "TpsMode")
        checks.true(section, tag, "HoldStrafe")
        checks.eq(section, tag, "NoTurn", 1)
        off = _yaw_off(checks, section, tag)
        _report(checks, f"{section} {tag} facing on camera yaw", off is not None and off <= 15, f"off={off}")
    yaw = math.radians(checks.value(section, "tmove", "CamYaw") or 0)
    dx = (_delta(checks, section, "ttps", "tmove", "HeroX10") or 0) / 10
    dy = (_delta(checks, section, "ttps", "tmove", "HeroY10") or 0) / 10
    forward = dx * math.cos(yaw) + dy * math.sin(yaw)
    left = -dx * math.sin(yaw) + dy * math.cos(yaw)
    # On the wanted axis at least 1.5 in the wanted direction. Off it under 1.
    ok = True
    for got, want in ((forward, want_forward), (left, want_left)):
        ok = ok and (got * want >= 1.5 if want else abs(got) < 1.0)
    _report(checks, f"{section} moves on the input axis", ok, f"forward={forward:.1f} left={left:.1f}")
    checks.true(section, "tmove", "MoveOrder")
    checks.eq(section, "tmove", "LowerState", lower)
    checks.eq(section, "tmove", "AimDir", direction)
    _walk_scale(checks, section, "tmove")
    checks.false(section, "tstop", "MoveOrder")
    # The camera turned 90 degrees while the hero stood.
    turned = _delta(checks, section, "tstop", "tturn", "CamYaw")
    turned = None if turned is None else abs((turned + 180) % 360 - 180)
    _report(checks, f"{section} camera turned", turned is not None and turned >= 80, f"turned={turned}")
    # Negative case: leaving TPS ends the strafe state.
    checks.false(section, "tend", "TpsMode")
    checks.false(section, "tend", "HoldStrafe")
    checks.eq(section, "tend", "NoTurn", 0)
    checks.false(section, "tend", "MoveOrder")


def _check_move(checks) -> None:
    # Lower state 3 is walk back, 2 is walk. Direction 4 is back, 2 is left.
    _tps_move(checks, "tps_back", -1, 0, 3, 4)
    _tps_move(checks, "tps_left", 0, 1, 2, 2)


def _tps_free(checks, section: str, tag: str, free: bool) -> None:
    """Cursor freed (PNC or the free-cursor state) against TPS mouse look."""
    flag = checks.true if free else checks.false
    anti = checks.false if free else checks.true
    flag(section, tag, "CursorVisible")
    anti(section, tag, "ControlRelative")
    anti(section, tag, "Crosshair")
    anti(section, tag, "HoldStrafe")
    checks.eq(section, tag, "NoTurn", 0 if free else 1)


def _check_cursor(checks) -> None:
    """R-TPS-30 to 35."""
    section = "tps_cursor"
    _tps_free(checks, section, "t0000", True)
    checks.false(section, "t0000", "MiddleHold")
    # Negative case: the middle press alone (tdown) changes nothing.
    for tag in ("ttps", "tdown", "trel", "taim"):
        _tps_free(checks, section, tag, False)
        checks.false(section, tag, "MiddleHold")
    # A middle click frees the cursor; the state holds with the button
    # released (tmid, taimmid). A second click ends it (trel).
    for tag in ("tmid", "tmidaim", "taimmid"):
        _tps_free(checks, section, tag, True)
        checks.true(section, tag, "MiddleHold")
        checks.true(section, tag, "TpsMode")
        # Negative case: no aim with the cursor free, and it ends a running aim.
        checks.false(section, tag, "AimActive")
    checks.false(section, "ttps", "AimActive")
    checks.true(section, "taim", "AimActive")
    # The switch to PNC ends the free-cursor state.
    _tps_free(checks, section, "tend", True)
    checks.false(section, "tend", "MiddleHold")
    checks.false(section, "tend", "AimActive")


def _check_target(checks) -> None:
    """R-TPS-80, R-TPS-51, and the aim click that leaves the UI target alone."""
    section = "tps_target"
    life = checks.value(section, "tlook", "EnemyHp")
    checks.true(section, "tlook", "CrossEnemy")
    checks.true(section, "tlook", "TargetNone")
    checks.true(section, "tclick", "TargetEnemy")
    # Negative case: the click never attacks.
    checks.false(section, "tclick", "AttackOrder")
    checks.eq(section, "tclick", "EnemyHp", life)
    checks.eq(section, "tclick", "Shots", checks.value(section, "tlook", "Shots"))
    checks.false(section, "taway", "CrossEnemy")
    checks.true(section, "taway", "TargetEnemy")
    checks.true(section, "tground", "TargetNone")
    checks.true(section, "taim", "AimActive")
    checks.true(section, "taim", "CrossEnemy")
    checks.true(section, "taim", "TargetNone")
    checks.true(section, "taimclick", "TargetNone")
    checks.false(section, "taimclick", "TargetEnemy")


FLOATERS = ("FloatRange", "FloatMiss", "FloatFriendly")

# Crosshair kinds, R-TPS-23 to 26: white, green, yellow, gray.
RETICLE_NORMAL, RETICLE_ENEMY, RETICLE_FRIENDLY, RETICLE_ENEMY_FAR = 0, 1, 2, 3


def _tps_shot(checks, section: str, floater: str | None, shots: int = 1) -> None:
    """One aim click plus one click on cooldown: `shots` shots, one text at most."""
    aiming = shots == 1
    (checks.true if aiming else checks.false)(section, "taim", "AimActive")
    checks.eq(section, "taim", "ShotKind", 0)
    # R-TPS-50, R-TPS-58: two clicks, the second on cooldown, one shot.
    checks.eq(section, "tend", "Presses", (checks.value(section, "taim", "Presses") or 0) + 2 * shots)
    checks.eq(section, "tend", "Shots", (checks.value(section, "taim", "Shots") or 0) + shots)
    (checks.true if aiming else checks.false)(section, "tshot", "ShotSeen")
    # R-TPS-70 to 72: exactly one text of the right kind, none of the others.
    for key in FLOATERS:
        want = (checks.value(section, "taim", key) or 0) + (1 if key == floater else 0)
        checks.eq(section, "tend", key, want)
    # R-TPS-57: the shot starts the hero cooldown and the button clock.
    if aiming:
        checks.gt(section, "tshot", "CooldownMs", 0)
        checks.gt(section, "tshot", "ButtonCdMs", 0)
    # R-TPS-60: the hero does not move.
    moved = max(abs(_delta(checks, section, "taim", "tend", key) or 0) for key in ("HeroX10", "HeroY10"))
    _report(checks, f"{section} hero stays", moved <= 2, f"moved10={moved}")
    # The shot is over: no order, no pending outcome, root as before, no UI target.
    checks.false(section, "tend", "AttackOrder")
    checks.eq(section, "tend", "ShotKind", 0)
    checks.eq(section, "tend", "Root", checks.value(section, "taim", "Root"))
    checks.true(section, "tend", "TargetNone")


def _tps_proxy_shot(checks, section: str) -> None:
    """R-TPS-53, 54, 59: the shot went to the proxy, inside weapon range, undamaged."""
    checks.true(section, "tshot", "ProxyValid")
    reach = checks.value(section, "tshot", "WeaponRange10")
    dist = checks.value(section, "tshot", "ProxyDist10")
    ok = dist is not None and reach is not None and 0 < dist <= reach
    _report(checks, f"{section} proxy inside weapon range", ok, f"dist10={dist} range10={reach}")
    checks.eq(section, "tshot", "ProxyHp", 1000)
    checks.false(section, "tend", "CrossEnemy")


# A proxy above this height (times 100) is in the air: the shot shows no hit.
AIR_Z100 = 10
TOSH_SHOT, TOSH_AIR_SHOT = "SCOBAToshShot", "SCOBAToshAirShot"


def _air_rule(checks, section: str) -> None:
    """A proxy in the air takes the shot effect without a hit; on the ground the weapon effect."""
    height = checks.value(section, "tshot", "ProxyZ100")
    want = TOSH_AIR_SHOT if height is not None and height > AIR_Z100 else TOSH_SHOT
    print(f"{section} raw ProxyZ100={height}")
    checks.eq(section, "tshot", "ShotEffect", want)


def _shot_cases(checks, prefix: str) -> None:
    for name in ("enemy", "far"):
        raw = {key: checks.value(f"{prefix}_{name}", "taim", key) for key in ("EnemyRayT100", "PickRay", "CrossType", "CamPitch")}
        print(f"{prefix}_{name} raw pick {raw}")
    section = f"{prefix}_enemy"
    checks.true(section, "taim", "CrossEnemy")
    checks.true(section, "taim", "InRange")
    checks.eq(section, "taim", "ReticleKind", RETICLE_ENEMY)
    _tps_shot(checks, section, None)
    # R-TPS-52: the enemy takes the damage. Raw: life at tend, before a slow
    # missile may have landed.
    print(f"{section} raw EnemyHp tend={checks.value(section, 'tend', 'EnemyHp')} tlate={checks.value(section, 'tlate', 'EnemyHp')}")
    checks.lt(section, "tlate", "EnemyHp", checks.value(section, "taim", "EnemyHp"))
    # One shot only: no further shot or text after tend.
    checks.eq(section, "tlate", "Shots", checks.value(section, "tend", "Shots"))

    section = f"{prefix}_far"
    checks.true(section, "taim", "CrossEnemy")
    checks.false(section, "taim", "InRange")
    checks.eq(section, "taim", "ReticleKind", RETICLE_ENEMY_FAR)
    _tps_shot(checks, section, "FloatRange")
    # R-TPS-53: the shot fires, the enemy takes nothing, also after flight time.
    checks.eq(section, "tend", "EnemyHp", checks.value(section, "taim", "EnemyHp"))
    checks.eq(section, "tlate", "EnemyHp", checks.value(section, "taim", "EnemyHp"))
    checks.true(section, "tshot", "ProxyValid")
    checks.eq(section, "tshot", "ProxyHp", 1000)

    section = f"{prefix}_sky"
    pitch = checks.value(section, "taim", "CamPitch")
    _report(checks, f"{section} camera looks up", pitch is not None and (pitch < 0 or pitch > 180), f"pitch={pitch}")
    _tps_shot(checks, section, "FloatMiss")
    _tps_proxy_shot(checks, section)
    checks.eq(section, "taim", "ReticleKind", RETICLE_NORMAL)
    # R-TPS-73: the sky shot aims above the ground.
    checks.gt(section, "tshot", "ProxyZ100", 100)
    # R-TPS-85: the crosshair and the text are layout frames, hooked up.
    checks.true(section, "taim", "CrosshairHooked")
    checks.eq(section, "tshot", "TextHooked", 4)
    checks.gt(section, "tshot", "TextShown", 0)

    section = f"{prefix}_friendly"
    checks.true(section, "taim", "CrossAlly")
    checks.eq(section, "taim", "ReticleKind", RETICLE_FRIENDLY)
    _tps_shot(checks, section, "FloatFriendly")
    # R-TPS-55: a real shot at the unit, no damage.
    life = checks.value(section, "taim", "AllyHp")
    _report(checks, f"{section} ally alive", life is not None and life > 0, f"life={life}")
    checks.eq(section, "tend", "AllyHp", life)


# Hero weapon ranges as the engine reports them, times 10. They include the
# +2 of the hero behavior UnitDirectControl. The ranged weapons reach twice
# their stock in-game range (Tosh 7, Psi Blast 6). The melee weapon keeps
# its stock in-game range (1 + 2).
RANGED_RANGE10 = {"Tosh": 140, "ToshAuto": 140, "QueenOfBladesPsiBlast": 120, "QueenOfBladesPsiBlastAuto": 120}
MELEE_RANGE10 = {"RazorTalons": 30, "RazorTalonsAuto": 30}


def _check_ranges(checks, section: str, weapons: dict) -> None:
    for weapon, range10 in weapons.items():
        checks.eq(section, "taim", f"Range10_{weapon}", range10)


def _check_shot(checks) -> None:
    _check_ranges(checks, "tps_shot_enemy", {k: v for k, v in RANGED_RANGE10.items() if k.startswith("Tosh")})
    # The enemy stands beyond the stock range 7 and inside the doubled one.
    checks.between("tps_shot_enemy", "taim", "Distance", 80, 135)
    # The far enemy stands outside the doubled range, on the crosshair ray.
    checks.between("tps_shot_far", "taim", "Distance", 145, 200)
    _shot_cases(checks, "tps_shot")
    # A hit on a unit runs the weapon effect. A sky shot is in the air.
    checks.eq("tps_shot_enemy", "tshot", "ShotEffect", TOSH_SHOT)
    # Negative case: a hit shows no shot text.
    checks.eq("tps_shot_enemy", "tshot", "TextShown", 0)
    checks.eq("tps_shot_friendly", "tshot", "ShotEffect", TOSH_SHOT)
    checks.eq("tps_shot_sky", "tshot", "ShotEffect", TOSH_AIR_SHOT)
    _air_rule(checks, "tps_shot_far")
    section = "tps_shot_ground"
    _tps_shot(checks, section, "FloatMiss")
    _tps_proxy_shot(checks, section)
    checks.eq(section, "taim", "ReticleKind", RETICLE_NORMAL)
    # Negative case: a miss that lands on the ground keeps its hit.
    checks.between(section, "tshot", "ProxyZ100", 0, AIR_Z100)
    checks.eq(section, "tshot", "ShotEffect", TOSH_SHOT)
    # Negative case, R-TPS-51: a click while not aiming fires nothing.
    section = "tps_shot_noaim"
    checks.true(section, "taim", "CrossEnemy")
    _tps_shot(checks, section, None, shots=0)
    checks.eq(section, "tend", "EnemyHp", checks.value(section, "taim", "EnemyHp"))
    checks.false(section, "tshot", "AttackOrder")
    _check_shot_walk(checks)
    _check_shot_stop(checks)


def _check_shot_stop(checks) -> None:
    """A stop order after the click does not cancel the shot or block the next click."""
    section = "tps_shot_stop"
    shots = checks.value(section, "taim", "Shots") or 0
    miss = checks.value(section, "taim", "FloatMiss") or 0
    checks.eq(section, "taim", "CrossType", "none")
    # Negative case: the click never holds an attack order.
    checks.false(section, "tpress", "AttackOrder")
    checks.eq(section, "tstop", "Shots", shots + 1)
    checks.eq(section, "tstop", "FloatMiss", miss + 1)
    checks.eq(section, "tstop", "ShotKind", 0)
    # The next click fires one more shot with its one text.
    checks.true(section, "tshot", "ShotSeen")
    checks.eq(section, "tend", "Shots", shots + 2)
    checks.eq(section, "tend", "FloatMiss", miss + 2)
    checks.eq(section, "tend", "ShotKind", 0)


def _check_shot_walk(checks) -> None:
    """R-TPS-61: one click while walking, one shot, and the walk does not slow."""
    section = "tps_shot_walk"
    checks.true(section, "taim", "AimActive")
    checks.true(section, "taim", "Forward")
    checks.true(section, "taim", "MoveOrder")
    base = checks.value(section, "", "BasePath1000")
    shot = checks.value(section, "", "ShotPath1000")
    # The hero really walks in the second before the click.
    _report(checks, f"{section} walks before the click", base is not None and base >= 2000, f"base1000={base}")
    # The second after the click covers the same path. One stalled game
    # loop out of 16 would cost 6%.
    ok = base is not None and shot is not None and shot >= base * 0.97
    _report(checks, f"{section} walk keeps its speed through the shot", ok, f"shot1000={shot} base1000={base}")
    # Negative case: the click never replaces the move order.
    for tag in ("tpress", "tshot", "tend"):
        checks.false(section, tag, "AttackOrder")
        checks.true(section, tag, "MoveOrder")
    # The shot fires: effect, text, cooldown, button clock.
    checks.eq(section, "tend", "Shots", (checks.value(section, "taim", "Shots") or 0) + 1)
    for key in FLOATERS:
        want = (checks.value(section, "taim", key) or 0) + (1 if key == "FloatMiss" else 0)
        checks.eq(section, "tend", key, want)
    checks.gt(section, "tshot", "CooldownMs", 0)
    checks.gt(section, "tshot", "ButtonCdMs", 0)
    _tps_proxy_shot(checks, section)
    # No shot state is left.
    checks.eq(section, "tend", "ShotKind", 0)
    checks.true(section, "tend", "TargetNone")


def _check_kerrigan(checks) -> None:
    for section in ("tps_kerr_enemy", "tps_kerr_far", "tps_kerr_sky", "tps_kerr_friendly"):
        checks.false(section, "taim", "HeroIsTosh")
    _check_ranges(checks, "tps_kerr_enemy", {k: v for k, v in RANGED_RANGE10.items() if k.startswith("Queen")})
    # Negative case: the melee weapon is not doubled.
    _check_ranges(checks, "tps_kerr_enemy", MELEE_RANGE10)
    # The enemy stands beyond the stock in-game Psi Blast range 6 and inside 12.
    checks.between("tps_kerr_enemy", "taim", "Distance", 70, 115)
    # The far enemy stands outside the doubled range, on the crosshair ray.
    checks.between("tps_kerr_far", "taim", "Distance", 125, 200)
    _shot_cases(checks, "tps_kerr")


def _check_aim(checks) -> None:
    """R-TPS-40 to 44. The field of view has no getter here: operator check."""
    section = "tps_aim"
    rest = checks.value(section, "ttps", "CamDist100") or 0
    checks.false(section, "ttps", "AimActive")
    checks.false(section, "ttps", "AnchorValid")
    checks.true(section, "taim", "AimActive")
    checks.true(section, "taim", "AnchorValid")
    # R-TPS-41, 42: the camera anchor sits on the right of the hero.
    checks.between(section, "taim", "AnchorRight100", 30, 70)
    # The camera arm is shorter while aiming.
    checks.lt(section, "taim", "CamDist100", rest * 0.9)
    # R-TPS-44, negative case: release removes the anchor and restores the distance.
    checks.false(section, "trel", "AimActive")
    checks.false(section, "trel", "AnchorValid")
    checks.between(section, "trel", "CamDist100", rest * 0.95, rest * 1.05)
    checks.false(section, "tend", "AimActive")


HEAD_STEPS = 9


def _check_head(checks) -> None:
    """R-TPS-12 to 14. Script state only: the look of the tilt is an operator check."""
    section = "tps_head"
    level = (HEAD_STEPS + 1) // 2
    # Negative cases: no head clip in PNC, while aiming, or with the cursor free.
    for tag in ("t0000", "taim", "tmid", "tend"):
        checks.eq(section, tag, "HeadStep", 0)
    checks.eq(section, "tlevel", "HeadStep", level)
    checks.eq(section, "tdown", "HeadStep", 1)
    checks.eq(section, "tup", "HeadStep", HEAD_STEPS)
    checks.eq(section, "trel", "HeadStep", HEAD_STEPS)
    checks.gt(section, "tup", "HeadSends", checks.value(section, "tlevel", "HeadSends") or 0)
    # R-TPS-12: outside aiming the torso pitch clips do not play.
    for tag in ("tlevel", "tdown", "tup", "trel"):
        checks.eq(section, tag, "PitchStep", 0)
    # R-TPS-14: aiming pitches the torso.
    checks.true(section, "taim", "AimActive")
    checks.gt(section, "taim", "PitchStep", 0)


GROUPS = ("move", "cursor", "aim", "head", "target", "pick", "shot", "kerrigan")

GROUP_CHECKS = {
    "pick": check_pick,
    "head": _check_head,
    "aim": _check_aim,
    "move": _check_move,
    "cursor": _check_cursor,
    "target": _check_target,
    "shot": _check_shot,
    "kerrigan": _check_kerrigan,
}


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1

    checks.eq("meta", "", "done", 1)
    # Real mouse input makes the run invalid.
    checks.eq("done", "tend", "RealClicks", 0)
    checks.false("done", "tend", "TpsMode")

    group = selected_group()
    print(f"group: {group}")
    for name in GROUPS:
        if group in ("all", name):
            GROUP_CHECKS[name](checks)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="tps",
        map_name="SCOBA.SC2Map",
        map_source=PROFILE_OUTPUTS["tps"],
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["tps"],
        ready_section="meta",
        ready_key="ready",
        launch_timeout_s=launch_timeout_s,
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
    )
