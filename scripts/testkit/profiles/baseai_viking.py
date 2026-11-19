"""baseai flight group: the Alt+4 Viking checks (form, morphs, right hold,
A / D). Split out of baseai.py (512-line limit)."""

from __future__ import annotations


def _ok(checks, s: str, name: str, ok: bool, detail: str) -> None:
    print(f"{s} {name}: {detail} {'PASS' if ok else 'FAIL'}")
    if not ok:
        checks.failures += 1


VIKING_TYPE = "SCOBAVikingHero"           # c_HERO_VIKING_TYPE, flight mode
VIKING_LANDED = "SCOBAVikingHeroAssault"  # hero ground form (SCOBAHeroAssaultMode)
STOCK_FIGHTER = "VikingFighter"           # stock forms: must not appear on the hero
STOCK_LANDED = "VikingAssault"
VIKING_SPEED_100 = 1200                   # UnitData SCOBAVikingHero Speed 12 (2026-11-18)
MORPH_KEYS = ("Order", "Type", "AssaultMorph", "FighterMorph", "Speed100", "Height100", "Abils")


def check_viking_form(checks, s: str, key: str) -> None:
    """The Alt+4 hero is the Viking in flight mode, not landed, not a Wraith."""
    print(f"{s} raw {key}: " + " ".join(f"{k}={checks.value(s, '', key + k)}" for k in ("Type", "Mover", "Height100")))
    checks.eq(s, "", key + "Type", VIKING_TYPE)
    checks.eq(s, "", key + "Mover", "Fly")
    t = checks.value(s, "", key + "Type")
    _ok(checks, s, f"{key} not landed, not a Wraith", t not in (VIKING_LANDED, STOCK_LANDED, "SCOBAWraithHero", None),
        f"type={t}")


def check_viking_morph(checks, s: str) -> None:
    """Land and lift through the hero morph pair. The transition-model probe
    (ActorFromScope by name) is raw only: run 20261118-130934 showed it True
    before any morph and on a stock Viking."""
    for m in ("pre", "stockPre", "land", "stockLand", "lift"):
        print(f"{s} raw {m}: " + " ".join(f"{k}={checks.value(s, '', m + k)}" for k in MORPH_KEYS))
    # Negative: the stock morphs are gone from both hero forms, read from the
    # unit's ability list. UnitAbilityCheck is raw only: it returned True for
    # the stock name while the list lacked it (run 20261118-142817).
    print(f"{s} raw UnitAbilityCheck: hero AssaultMode={checks.value(s, '', 'heroStockAbil')}"
          f" landed FighterMode={checks.value(s, '', 'landStockAbil')}")
    for m, own, stock in (("pre", "SCOBAHeroAssaultMode", "AssaultMode"), ("land", "SCOBAHeroFighterMode", "FighterMode"),
                          ("lift", "SCOBAHeroAssaultMode", "AssaultMode")):
        abils = str(checks.value(s, "", m + "Abils") or "").split()
        _ok(checks, s, f"{m}: hero morph, no stock {stock}", own in abils and stock not in abils, f"abils={abils}")
    checks.true(s, "", "landOrder")
    checks.eq(s, "", "landType", VIKING_LANDED)
    h = checks.value(s, "", "landHeight100")
    _ok(checks, s, "landed Viking on the ground", h is not None and abs(h) <= 50, f"h100={h}")
    # Lift-off keeps the hero type and its air speed (operator 2026-11-18:
    # the stock FighterMode made a stock VikingFighter, speed 2.75).
    checks.true(s, "", "liftOrder")
    checks.eq(s, "", "liftType", VIKING_TYPE)
    sp = checks.value(s, "", "liftSpeed100")
    _ok(checks, s, "lift: hero air speed", sp == VIKING_SPEED_100, f"speed100={sp} want={VIKING_SPEED_100}")
    _ok(checks, s, "lift: not a stock fighter", checks.value(s, "", "liftType") != STOCK_FIGHTER,
        f"type={checks.value(s, '', 'liftType')}")
    # The stock Viking still lands with the stock morph.
    checks.eq(s, "", "stockLandType", STOCK_LANDED)
    # Landing after Space / Ctrl and over other terrain (baseai_land.galaxy;
    # operator report 2026-11-18: the landed model floats).
    print(f"{s} raw lfTerrain (x,y:marineZ/ground/air/point x100/cliff): {checks.value(s, '', 'lfTerrain')}")
    print(f"{s} raw lfStockTrace (stock VikingFighter): {checks.value(s, '', 'lfStockTrace')}")
    for k in LAND_KEYS:
        print(f"{s} raw {k}: " + " ".join(f"{f}={checks.value(s, '', k + f)}" for f in
                                          ("Ground100", "Pre100", "Probe100", "Rest100", "Type", "Final100", "Prop100")))
        print(f"{s} raw {k}Trace (above100/prop100): {checks.value(s, '', k + 'Trace')}")
        checks.eq(s, "", k + "Type", VIKING_LANDED)
        f = checks.value(s, "", k + "Final100")
        _ok(checks, s, f"{k}: landed on the ground", f is not None and abs(f) <= 50, f"above100={f}")
    check_stomp(checks, s)


LAND_KEYS = ("lfFlat0", "lfFlatUp", "lfMove", "lfDown")
STOMP_KEYS = ("Type", "Slot", "Moved100", "FxSent", "Shake10k", "Crushed")


def check_stomp(checks, s: str) -> None:
    """Stomp config (systems/stomp) on the hero Viking (operator 2026-11-18:
    the Goliath's thump, effects, shake and doodad crushing). Flying: none.
    Landed, defaults: slot, fx switch on, shake, crush. Landed, all off by
    gf_StompConfig: none. The sound and effect look is an operator check."""
    print(f"{s} raw stomp row={checks.value(s, '', 'stRow')} liftSlot={checks.value(s, '', 'stLiftSlot')}")
    v = {}
    for k in ("stFly", "stLand", "stOff"):
        v[k] = {f: checks.value(s, "", k + f) for f in STOMP_KEYS}
        print(f"{s} raw {k}: " + " ".join(f"{f}={x}" for f, x in v[k].items()))
    _ok(checks, s, "stomp row configured", (checks.value(s, "", "stRow") or -1) >= 0, f"row={checks.value(s, '', 'stRow')}")
    checks.eq(s, "", "stFlyType", VIKING_TYPE)
    checks.eq(s, "", "stFlySlot", -1)
    checks.eq(s, "", "stFlyFxSent", 0)
    checks.eq(s, "", "stFlyShake10k", 0)
    checks.eq(s, "", "stFlyCrushed", False)
    checks.eq(s, "", "stLandType", VIKING_LANDED)
    _ok(checks, s, "landed: stomp slot", (v["stLand"]["Slot"] if v["stLand"]["Slot"] is not None else -1) >= 0,
        f"slot={v['stLand']['Slot']}")
    _ok(checks, s, "landed: walked", (v["stLand"]["Moved100"] or 0) > 300, f"moved100={v['stLand']['Moved100']}")
    _ok(checks, s, "landed: fx switch sent", (v["stLand"]["FxSent"] or 0) > 0, f"sent={v['stLand']['FxSent']}")
    _ok(checks, s, "landed: camera shake", (v["stLand"]["Shake10k"] or 0) > 0, f"shake10k={v['stLand']['Shake10k']}")
    checks.true(s, "", "stLandCrushed")
    checks.eq(s, "", "stOffType", VIKING_LANDED)
    _ok(checks, s, "off: walked", (v["stOff"]["Moved100"] or 0) > 300, f"moved100={v['stOff']['Moved100']}")
    checks.eq(s, "", "stOffFxSent", 0)
    checks.eq(s, "", "stOffShake10k", 0)
    checks.eq(s, "", "stOffCrushed", False)
    checks.eq(s, "", "stLiftSlot", -1)
    check_feel(checks, s)


TURN_RATE = 90            # UnitData SCOBAVikingHeroAssault, degrees per second
TURN_05_MAX = 60          # 0.5 s at 90/s = 45, plus a start window
TURN_FAST_MIN = 150       # a stock-rate turn is (nearly) done in 0.5 s


def check_feel(checks, s: str) -> None:
    """Operator 2026-11-18: landed Viking turns slowly (also in place);
    landing has an impact and shake at touchdown."""
    for k in ("tnFly", "tnLand"):
        print(f"{s} raw {k}: " + " ".join(f"{f}={checks.value(s, '', k + f)}" for f in ("Order05", "Order3", "Script05", "Script3")))
    for f in ("Order05", "Script05"):
        v = checks.value(s, "", "tnLand" + f)
        _ok(checks, s, f"landed {f}: slow turn", v is not None and v <= TURN_05_MAX, f"turned={v} max={TURN_05_MAX}")
        w = checks.value(s, "", "tnLand" + f.replace("05", "3"))
        _ok(checks, s, f"landed {f}: turns round", w is not None and w >= TURN_FAST_MIN, f"turned3s={w}")
        c = checks.value(s, "", "tnFly" + f)
        _ok(checks, s, f"flying {f}: fast (control)", c is not None and c >= TURN_FAST_MIN, f"turned={c}")
    # Footfall dust / splash actors: baseai_feel.check_footfall.
    for k in ("imLand", "imLift", "imOff"):
        print(f"{s} raw {k}: " + " ".join(f"{f}={checks.value(s, '', k + f)}" for f in ("Fired", "Waited100", "Shake10k")))
    checks.eq(s, "", "imLandFired", 1)
    w = checks.value(s, "", "imLandWaited100")
    _ok(checks, s, "landing impact at touchdown", w is not None and 100 <= w <= 300, f"waited100={w}")
    _ok(checks, s, "landing shake", (checks.value(s, "", "imLandShake10k") or 0) > 0, f"shake10k={checks.value(s, '', 'imLandShake10k')}")
    checks.eq(s, "", "imLiftFired", 0)
    checks.eq(s, "", "imLiftShake10k", 0)
    checks.eq(s, "", "imOffShake10k", 0)


SIDE_MOVE_MAX_100 = 50   # idle drift allowed, x100
SIDE_TURN_MAX = 10       # degrees
HERO_SIDE_TOL = 20       # degrees, travel vs camera yaw + 90 (turn-in at the start)


def check_side_keys(checks, s: str) -> None:
    """Regular unit: A / D do nothing (operator 2026-11-18). No flag, no
    move, no turn; the release does not stop a move order."""
    for k in ("sideA", "sideD"):
        v = {f: checks.value(s, "", k + f) for f in ("Flag", "Moved100", "Turn", "MoveKept")}
        print(f"{s} raw {k}: " + " ".join(f"{f}={x}" for f, x in v.items()))
        checks.eq(s, "", k + "Flag", False)
        _ok(checks, s, f"{k}: no move", v["Moved100"] is not None and v["Moved100"] <= SIDE_MOVE_MAX_100,
            f"moved100={v['Moved100']}")
        _ok(checks, s, f"{k}: no turn", v["Turn"] is not None and v["Turn"] <= SIDE_TURN_MAX, f"turn={v['Turn']}")
        checks.true(s, "", k + "MoveKept")
    # Positive control: a hero still moves on A, left of the camera yaw.
    keys = ("heroSideRegular", "heroSideYaw", "heroSideFlag", "heroSideDist100", "heroSideTravel", "heroSideEndFlag")
    v = {k: checks.value(s, "", k) for k in keys}
    print(f"{s} raw hero side: " + " ".join(f"{k}={v[k]}" for k in keys))
    checks.eq(s, "", "heroSideRegular", False)
    checks.true(s, "", "heroSideFlag")
    checks.eq(s, "", "heroSideEndFlag", False)
    _ok(checks, s, "hero A: moved", v["heroSideDist100"] is not None and v["heroSideDist100"] > 100,
        f"dist100={v['heroSideDist100']}")
    ok = None not in (v["heroSideYaw"], v["heroSideTravel"])
    _ok(checks, s, "hero A: travel = camera yaw + 90",
        ok and _angle_off(v["heroSideTravel"], v["heroSideYaw"] + 90) <= HERO_SIDE_TOL,
        f"travel={v['heroSideTravel']} yaw={v['heroSideYaw']}")


ANGLE_TOL = 10      # degrees, travel vs facing


def _angle_off(a, b) -> int:
    return abs((a - b + 180) % 360 - 180)


def check_right_hold(checks, s: str) -> None:
    """Regular unit, right hold + W: camera orbit only, no facing lock, the
    unit travels along and faces its own direction, not the camera yaw."""
    keys = ("rhFacing0", "rhFacingTrace", "rhCamYaw", "rhTravel", "rhFacing", "rhDist100", "rhStrafe",
            "rhRotateUnit", "rhRotateCamera", "rhNoTurn", "rhTps")
    v = {k: checks.value(s, "", k) for k in keys}
    print(f"{s} raw right hold: " + " ".join(f"{k}={v[k]}" for k in keys))
    checks.eq(s, "", "rhStrafe", False)
    checks.eq(s, "", "rhRotateUnit", False)
    checks.true(s, "", "rhRotateCamera")
    checks.eq(s, "", "rhNoTurn", 0)
    checks.eq(s, "", "rhTps", False)
    nums = [v[k] for k in ("rhFacing0", "rhCamYaw", "rhTravel", "rhFacing", "rhDist100")]
    ok = None not in nums
    _ok(checks, s, "right hold: unit moved", ok and v["rhDist100"] > 100, f"dist100={v['rhDist100']}")
    # Travel along the facing. The start drift (one turn of ~12 at the W
    # press, runs 20261118-130934 / -132438) is raw: rhFacing0 vs trace.
    _ok(checks, s, "right hold: travel = own facing",
        ok and _angle_off(v["rhFacing"], v["rhTravel"]) <= ANGLE_TOL,
        f"travel={v['rhTravel']} facing0={v['rhFacing0']} facing={v['rhFacing']}")
    # Negative: not along the camera yaw (the old facing lock / strafe).
    _ok(checks, s, "right hold: not camera yaw",
        ok and _angle_off(v["rhTravel"], v["rhCamYaw"]) > 45, f"travel={v['rhTravel']} camYaw={v['rhCamYaw']}")
