"""baseai flight group: hero Viking feel (operator 2026-11-18). Camera
refollow, turn-in-place clip, landed speed, footfall dust and splash.
Scenarios in scripts/testkit/galaxy/baseai_feel.galaxy."""

from __future__ import annotations


def _ok(checks, s: str, name: str, ok: bool, detail: str) -> None:
    print(f"{s} {name}: {detail} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1


CAM_NEAR_100 = 400        # camera target within 4 of the hero after a refollow
TURN_SCALE_100 = 50       # gf_TurnAnimDefaults: at least 2x slower than the clip
SPEED_RATIO = 1.25        # SCOBAVikingHeroAssault Speed 2.8125 = stock 2.25 + 25 %
SPEED_TOL = 0.05
FX_TICKS = 48             # gf_BeFxSeen samples


def _v(checks, s: str, k: str):
    return checks.value(s, "", k)


def check_cam(checks, s: str) -> None:
    keys = ("Refollows", "Reason", "Follows", "Dist100")
    for k in ("camNeg", "camLost", "camDrop", "camAfter"):
        print(f"{s} raw {k}: " + " ".join(f"{f}={_v(checks, s, k + f)}" for f in keys))
    checks.eq(s, "", "camNegRefollows", 0)
    checks.true(s, "", "camNegFollows")
    checks.false(s, "", "camLostBefore")
    _ok(checks, s, "lost follow restored", (_v(checks, s, "camLostRefollows") or 0) >= 1 and _v(checks, s, "camLostFollows") is True,
        f"refollows={_v(checks, s, 'camLostRefollows')} follows={_v(checks, s, 'camLostFollows')}")
    d = _v(checks, s, "camLostDist100")
    _ok(checks, s, "camera back on the hero", d is not None and d <= CAM_NEAR_100, f"dist100={d}")
    checks.eq(s, "", "camDropRefollows", 0)
    _ok(checks, s, "after the drop: restored", (_v(checks, s, "camAfterRefollows") or 0) >= 1 and _v(checks, s, "camAfterFollows") is True,
        f"refollows={_v(checks, s, 'camAfterRefollows')} follows={_v(checks, s, 'camAfterFollows')}")


def check_turn_anim(checks, s: str) -> None:
    for k in ("taFly", "taLand"):
        print(f"{s} raw {k}: " + " ".join(f"{f}={_v(checks, s, k + f)}" for f in ("OnMid", "OnEnd", "Starts", "Stops", "Scale100")))
    checks.eq(s, "", "feelLandType", "SCOBAVikingHeroAssault")
    checks.true(s, "", "taLandOnMid")
    checks.false(s, "", "taLandOnEnd")
    checks.eq(s, "", "taLandStarts", 1)
    _ok(checks, s, "turn clip stopped", (_v(checks, s, "taLandStops") or 0) >= 1, f"stops={_v(checks, s, 'taLandStops')}")
    # Script state: the clip is sent at half speed or slower. The look is an
    # operator check.
    sc = _v(checks, s, "taLandScale100")
    _ok(checks, s, "turn clip time scale <= 0.5", sc is not None and 0 < sc <= TURN_SCALE_100, f"scale100={sc}")
    # Negatives: flying (not configured) and walking play no turn clip.
    checks.eq(s, "", "taFlyStarts", 0)
    for k in ("fxDry", "fxWet"):
        checks.false(s, "", k + "TurnOn")
        checks.eq(s, "", k + "TurnStarts", 0)


def check_speed(checks, s: str) -> None:
    keys = ("spHero100", "spStock100", "spHeroWalk100")
    v = {k: _v(checks, s, k) or 0 for k in keys}
    print(f"{s} raw speed: " + " ".join(f"{k}={v[k]}" for k in keys))
    r = v["spHero100"] / v["spStock100"] if v["spStock100"] else 0.0
    _ok(checks, s, f"landed speed = stock x {SPEED_RATIO}", abs(r - SPEED_RATIO) <= SPEED_TOL, f"ratio={r:.3f}")
    # Engine: the walk over 2 s at that speed.
    w = v["spHeroWalk100"] / (2 * v["spHero100"]) if v["spHero100"] else 0.0
    _ok(checks, s, "landed walk 2 s = speed x 2", abs(w - 1.0) <= SPEED_TOL, f"ratio={w:.3f}")


def _ticks(checks, s: str, k: str, f: str) -> int:
    return sum(1 for t in range(1, FX_TICKS + 1) if _v(checks, s, f"{k}{f}{t}"))


def check_footfall(checks, s: str) -> None:
    checks.true(s, "", "feelDryOk")
    checks.true(s, "", "feelWetOk")
    n = {}
    for k in ("fxFly", "fxDry", "fxWet", "fxGDry"):
        n[k] = {f: _ticks(checks, s, k, f) for f in ("D", "W", "S")}
        dust = next((_v(checks, s, f"{k}D{t}") for t in range(1, FX_TICKS + 1) if _v(checks, s, f"{k}D{t}")), "")
        print(f"{s} raw {k}: dust={n[k]['D']} splash={n[k]['W']} sound={n[k]['S']} ground={_v(checks, s, k + 'Ground')}"
              f" inWater={_v(checks, s, k + 'InWater')} wet={_v(checks, s, k + 'Wet')} slot={_v(checks, s, k + 'Slot')}"
              f" at={_v(checks, s, k + 'At')} dustActor={dust[:160]!r}")
    # Dry ground: dust and sound, no splash. Goliath: the control.
    for k, who in (("fxDry", "Viking"), ("fxGDry", "Goliath")):
        _ok(checks, s, f"{who} dry: dust actor", n[k]["D"] > 0, f"ticks={n[k]['D']}")
        _ok(checks, s, f"{who} dry: sound actor", n[k]["S"] > 0, f"ticks={n[k]['S']}")
        _ok(checks, s, f"{who} dry: no splash", n[k]["W"] == 0, f"ticks={n[k]['W']}")
    # Water: splash, no dust.
    _ok(checks, s, "Viking wet: splash actor", n["fxWet"]["W"] > 0, f"ticks={n['fxWet']['W']}")
    _ok(checks, s, "Viking wet: no dust", n["fxWet"]["D"] == 0, f"ticks={n['fxWet']['D']}")
    # Flying: nothing.
    _ok(checks, s, "flying: no footfall actors", sum(n["fxFly"].values()) == 0, f"ticks={n['fxFly']}")


def check_feel_extra(checks, s: str) -> None:
    checks.true(s, "", "feelBound")
    print(f"{s} raw feelType={_v(checks, s, 'feelType')}")
    check_cam(checks, s)
    check_turn_anim(checks, s)
    check_speed(checks, s)
    check_footfall(checks, s)
