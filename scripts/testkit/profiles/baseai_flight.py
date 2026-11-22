"""baseai flight group: the Alt+4 regular unit (speed, PNC only, flight
height), and the flight checks the macro group shares. Scenarios in
scripts/testkit/galaxy/baseai/baseai_flight.galaxy."""

from __future__ import annotations

from .baseai_common import _ok
from .baseai_feel import check_feel_extra
from .baseai_viking import check_right_hold, check_side_keys, check_viking_form, check_viking_morph

FLIGHT_STEP_100 = 400  # c_FLIGHT_RATE 4 per s, held 1 s
FLIGHT_TOL_100 = 100   # one tick each end (0.0625 s x 8 = 0.5) plus blend


def check_flight(checks, s: str) -> None:
    """Wraith flight (systems/flight): climb, descend, camera follows, no jump."""
    keys = ("H100", "Flight100", "Cam100", "FlightIs", "JumpPhase")
    for t in ("fly0", "flyUp", "flyDown"):
        print(f"{s} raw {t}: " + " ".join(f"{k}={checks.value(s, t, k)}" for k in keys))
    base = checks.value(s, "", "camBase100") or 0
    h0 = checks.value(s, "fly0", "H100") or 0
    up = checks.value(s, "flyUp", "H100") or 0
    down = checks.value(s, "flyDown", "H100") or 0
    traces = {}
    for t in ("traceUp", "traceHoldUp", "traceDown", "traceHoldDown"):
        raw = checks.value(s, "", t) or ""
        traces[t] = [int(v) for v in str(raw).split()]
        print(f"{s} raw {t}: {traces[t]}")
    # Negative: no drift while no key is held.
    for t in ("traceHoldUp", "traceHoldDown"):
        v = traces[t]
        _ok(checks, s, f"{t} holds", len(v) == 4 and max(v) - min(v) <= FLIGHT_TOL_100, f"{t}={v}")
    checks.true(s, "fly0", "FlightIs")
    _ok(checks, s, "climb", abs(up - h0 - FLIGHT_STEP_100) <= FLIGHT_TOL_100, f"h0={h0} up={up}")
    _ok(checks, s, "descend", abs(up - down - FLIGHT_STEP_100) <= FLIGHT_TOL_100, f"up={up} down={down}")
    for t in ("flyUp", "flyDown"):
        cam = checks.value(s, t, "Cam100") or 0
        fl = checks.value(s, t, "Flight100") or 0
        _ok(checks, s, f"{t} camera = base + flight", abs(cam - base - fl) <= 2, f"cam={cam} base={base} flight={fl}")
        # The engine height matches the tracked flight height.
        _ok(checks, s, f"{t} engine height = flight", abs((checks.value(s, t, 'H100') or 0) - fl) <= FLIGHT_TOL_100,
            f"engine={checks.value(s, t, 'H100')} flight={fl}")
        # Negative: no jump on the flyer.
        checks.eq(s, t, "JumpPhase", checks.value(s, "fly0", "JumpPhase"))


SPEED_TOL = 0.10        # +-10 % of the reference ground speed
HEIGHT_KEYS = (("mA", "Blend", "After"), ("mB", "Blend", "After"), ("mC", "Climb", "After"), ("mD", "Climb", "After"),
               ("mE", "Blend", "After"), ("mF", "Blend", "After"))


VISTA_OVERLORDS = 2                 # SCOBAVistaOverlord in Objects


def check_flight_group(checks) -> None:
    """Viking speed through WASD and LMB+RMB, and the raw height methods."""
    s = "ba_flight"
    checks.true(s, "", "wraithActive")
    # Regular unit: PNC only. TPS on is refused (operator 2026-11-18).
    checks.eq(s, "", "wraithTps", False)
    checks.eq(s, "", "backTps", False)
    checks.eq(s, "", "tpsBehavior", 0)
    print(f"{s} raw tps refuse: " + " ".join(f"{k}={checks.value(s, '', k)}" for k in ("tpsOnOrder", "tpsRefused")))
    check_right_hold(checks, s)
    check_side_keys(checks, s)
    checks.eq(s, "", "chaseStand0", 0)       # regular unit: Chase always Move
    checks.eq(s, "", "chaseStand1", 0)
    moved = checks.value(s, "", "chaseMoved100")
    _ok(checks, s, "ground right click moves the regular unit", moved is not None and moved > 500,
        f"moved100={moved} refused={checks.value(s, '', 'chaseRefused')} move={checks.value(s, '', 'chaseMoveOrder')}")
    check_viking_form(checks, s, "vikStart")
    check_viking_form(checks, s, "vikEnd")
    # The two vista Overlords: special type, player 8, height 64; no stock
    # Overlord (it is tech-blocked and would give supply).
    vista = checks.value(s, "", "vistaOwnerHeight") or ""
    print(f"{s} raw vista: count={checks.value(s, '', 'vistaCount')} stock={checks.value(s, '', 'vistaStock')} at={vista}")
    checks.eq(s, "", "vistaCount", VISTA_OVERLORDS)
    checks.eq(s, "", "vistaStock", 0)
    _ok(checks, s, "vista Overlords player 8 at height 64", vista.split() == ["8@6400"] * VISTA_OVERLORDS, f"at={vista}")
    check_viking_morph(checks, s)
    check_feel_extra(checks, s)
    keys = ("speedData100", "speedProp100", "speedNormal100", "speedTosh100", "speedW100", "speedMouse100",
            "speedFree100")
    v = {k: checks.value(s, "", k) or 0 for k in keys}
    print(f"{s} raw speed: " + " ".join(f"{k}={v[k]}" for k in keys) +
          f" camYaw={checks.value(s, '', 'camYaw')} mouseForward={checks.value(s, '', 'mouseForward')}"
          f" forward={checks.value(s, '', 'forward')}")
    checks.eq(s, "", "freeTps", False)
    for t in ("W", "M", "F"):
        path = str(checks.value(s, t, "Path") or "")
        print(f"{s} raw {t}: move={checks.value(s, t, 'Move')} cur100={checks.value(s, t, 'Cur100')} path={path}")
        pts = [tuple(int(c) for c in p.split(",")) for p in path.replace("|", " ").split()]
        steps = [round(((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5) for a, b in zip(pts, pts[1:])]
        # Negative: no slow step (a stop between move orders). Each 0.25 s
        # step at least 90 % of full speed.
        floor = (1 - SPEED_TOL) * v["speedProp100"] * 0.25
        _ok(checks, s, f"{t} no slow step", len(steps) == 8 and min(steps) >= floor,
            f"steps100={steps} floor={floor:.0f}")
    # Reference: the controlled unit's own speed (engine property), which
    # is its data speed (no speed behavior on the Wraith).
    ref = v["speedProp100"]
    _ok(checks, s, "speed property = unit data speed", ref > 0 and abs(ref - v["speedData100"]) <= SPEED_TOL * ref,
        f"prop={ref} data={v['speedData100']}")
    for k in ("speedW100", "speedMouse100", "speedFree100"):
        _ok(checks, s, f"{k} = Wraith speed", ref > 0 and abs(v[k] - ref) <= SPEED_TOL * ref, f"{k}={v[k]} ref={ref}")
        # Negative: not the hero's (Tosh) speed.
        _ok(checks, s, f"{k} not Tosh speed", abs(v[k] - v["speedTosh100"]) > SPEED_TOL * ref,
            f"{k}={v[k]} tosh={v['speedTosh100']}")
    check_flight(checks, s)
    # Key repeat (release+press every tick) must not slow the climb.
    rep = checks.value(s, "", "repeatClimb100")
    _ok(checks, s, "climb with key repeat = rate", rep is not None and abs(rep - FLIGHT_STEP_100) <= 50,
        f"climb100={rep} want={FLIGHT_STEP_100}")
    for m, a, b in HEIGHT_KEYS:
        print(f"{s} raw {m}: start={checks.value(s, m, 'Start100')} stop={checks.value(s, m, 'Stop100')}")
        print(f"{s} raw {m}{a}: {checks.value(s, m, a)}")
        print(f"{s} raw {m}{b}: {checks.value(s, m, b)}")
