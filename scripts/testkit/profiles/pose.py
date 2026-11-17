"""Shooting pose checks: combat group pose (R-PNC-80) and tps group pose (R-TPS-17)."""

from __future__ import annotations

from .bank_checks import _delta, _report, _shots, _still


def _pose_held(checks, section: str, samples: int) -> None:
    """Every sample has a pose state and a pitch pose on the upper bracket."""
    got = checks.value(section, "", "Samples")
    none = checks.value(section, "", "NoneSamples")
    no_pitch = checks.value(section, "", "NoPitchSamples")
    order = checks.value(section, "", "OrderSamples")
    ok = got == samples and none == 0 and no_pitch == 0
    _report(
        checks,
        f"{section} pose held in every sample",
        ok,
        f"samples={got} want={samples} none={none} noPitch={no_pitch} (raw: attackOrder={order})",
    )


def check_combat_pose(checks) -> None:
    # R-PNC-80: Tosh holds the shooting pose between shots.
    # Upper state 0 is none, 2 is ready, 6 is attack.
    s = "pose_single_seq"
    checks.true(s, "t0000", "HeroIsTosh")
    checks.eq(s, "t0000", "UpperState", 0)
    for key in ("shot1Seen", "shot2Seen", "shot3Seen"):
        checks.true(s, "", key)
    # Engine state: three commands, three shots, three equal damage steps.
    _shots(checks, s, "t0000", "thold", 3)
    steps = [
        _delta(checks, s, "t0000", "tshot1", "EnemyHp"),
        _delta(checks, s, "tshot1", "tshot2", "EnemyHp"),
        _delta(checks, s, "tshot2", "tshot3", "EnemyHp"),
    ]
    # The target regenerates about one point between snapshots.
    ok = all(step is not None and step < 0 for step in steps) and max(steps) - min(steps) <= 4
    _report(checks, f"{s} three equal damage steps", ok, f"steps={steps}")
    # The attack order ends after each single shot: only the linger holds.
    checks.false(s, "thold", "AttackOrder")
    _pose_held(checks, s, 48)
    for tag in ("tshot1", "tshot2", "tshot3", "thold"):
        checks.gt(s, tag, "UpperState", 0)
    checks.eq(s, "thold", "UpperState", 2)
    clears = _delta(checks, s, "tshot1", "thold", "UpperClears")
    _report(checks, f"{s} upper bracket never cleared between shots", clears == 0, f"clears={clears}")
    # Negative: the pose ends after the linger.
    checks.false(s, "ttail", "AttackOrder")
    checks.eq(s, "ttail", "UpperState", 0)
    checks.eq(s, "ttail", "PitchStep", 0)
    checks.false(s, "ttail", "ReadyHold")
    dropped = _delta(checks, s, "thold", "ttail", "UpperClears")
    _report(checks, f"{s} pose dropped once after the linger", dropped == 1, f"clears={dropped}")
    _shots(checks, s, "thold", "ttail", 0)
    _still(checks, s, "t0000", "ttail")

    # Attack auto: held through the whole attack.
    s = "pose_auto"
    checks.true(s, "", "shot1Seen")
    repeat = _delta(checks, s, "t0000", "tend", "Shots")
    _report(checks, f"{s} repeats", repeat is not None and repeat >= 3, f"shots={repeat}")
    checks.damage(s, "t0000", "tend")
    _pose_held(checks, s, 64)
    clears = _delta(checks, s, "t0000", "tend", "UpperClears")
    _report(checks, f"{s} upper bracket never cleared", clears == 0, f"clears={clears}")

    # Cancel drops the pose at once.
    s = "pose_cancel"
    checks.true(s, "", "shot1Seen")
    checks.eq(s, "t0000", "UpperState", 2)
    checks.true(s, "t0000", "ReadyHold")
    checks.false(s, "tend", "AttackOrder")
    checks.true(s, "tend", "TargetNone")
    checks.eq(s, "tend", "UpperState", 0)
    checks.eq(s, "tend", "PitchStep", 0)
    checks.false(s, "tend", "ReadyHold")
    _shots(checks, s, "t0000", "tend", 0)

    # Negative: no attack, no pose.
    s = "pose_idle"
    checks.true(s, "t0000", "InRange")
    got = checks.value(s, "", "Samples")
    none = checks.value(s, "", "NoneSamples")
    _report(checks, f"{s} no pose in any sample", got == 32 and none == 32, f"samples={got} none={none}")
    clears = _delta(checks, s, "t0000", "tend", "UpperClears")
    _report(checks, f"{s} no upper clear", clears == 0, f"clears={clears}")
    _shots(checks, s, "t0000", "tend", 0)
    checks.false(s, "tend", "AttackOrder")

    # Negative: Kerrigan is unchanged. No pose once her attack clip is over.
    s = "pose_kerrigan"
    checks.false(s, "t0000", "HeroIsTosh")
    checks.true(s, "", "shot1Seen")
    _shots(checks, s, "t0000", "tend", 1)
    checks.eq(s, "tend", "UpperState", 0)
    checks.false(s, "tend", "ReadyHold")

    check_attack_rate(checks)


def _period_factor(period_ms) -> float | None:
    """The weapon-period speed factor, as gf_AnimAttackSpeed computes it."""
    if not period_ms:
        return None
    return max(0.25, 1000.0 / period_ms)


def check_attack_rate(checks) -> None:
    """Tosh plays the attack clip at 2x the weapon-period rate (operator 2026-11-17)."""
    s = "attack_rate"
    factor = _period_factor(checks.value(s, "", "toshPeriod1000"))
    want = None if factor is None else int(factor * 2.0 * 1000)
    got = checks.value(s, "", "toshSpeed1000")
    ok = want is not None and got is not None and abs(got - want) <= 2
    _report(checks, f"{s} Tosh factor is 2x the weapon factor", ok, f"got={got} want={want}")
    checks.true(s, "", "shotSeen")
    # Engine path: the factor the FSM stored on the real shot.
    stored = checks.value(s, "", "storedSpeed1000")
    ok = want is not None and stored is not None and abs(stored - want) <= 2
    _report(
        checks,
        f"{s} shot stored the 2x factor",
        ok,
        f"stored={stored} want={want} (raw: holdMs={checks.value(s, '', 'holdMs')}"
        f" clipRaw={checks.value(s, '', 'clipRaw')} clipScaled={checks.value(s, '', 'clipScaled')})",
    )
    # The hold is 0.5 / factor: shorter than the old 1x hold.
    if factor is not None:
        checks.lt(s, "", "holdMs", int(500.0 / factor))
    # Negative: Kerrigan keeps the weapon-period factor alone.
    k_factor = _period_factor(checks.value(s, "", "kerriganPeriod1000"))
    k_want = None if k_factor is None else int(k_factor * 1000)
    k_got = checks.value(s, "", "kerriganSpeed1000")
    ok = k_want is not None and k_got is not None and abs(k_got - k_want) <= 2
    _report(checks, f"{s} Kerrigan factor unchanged", ok, f"got={k_got} want={k_want}")


def check_tps_pose(checks) -> None:
    """R-TPS-17: TPS, Attack auto, not aiming: Tosh holds the shooting pose."""
    # Upper state 0 is none, 2 is ready, 4 is aim, 6 is attack.
    s = "tps_pose_auto"
    checks.true(s, "", "shot1Seen")
    for tag in ("t0000", "thold", "twalk0", "twalk"):
        checks.true(s, tag, "TpsMode")
        checks.false(s, tag, "AimActive")
        checks.true(s, tag, "Auto")
        checks.gt(s, tag, "UpperState", 0)
        # R-TPS-12: the torso does not follow the camera pitch.
        checks.eq(s, tag, "PitchStep", 0)
    # Standing: the engine keeps firing; the pose is never dropped.
    shots = _delta(checks, s, "t0000", "thold", "Shots")
    _report(checks, f"{s} standing shots repeat", shots is not None and shots >= 3, f"shots={shots}")
    checks.damage(s, "t0000", "thold")
    _pose_held(checks, s, 64)
    clears = _delta(checks, s, "t0000", "thold", "UpperClears")
    _report(checks, f"{s} upper bracket never cleared", clears == 0, f"clears={clears}")
    # Strafing: the hero moves, the shots go on, the pose is never dropped.
    checks.displacement(s, "thold", "twalk")
    shots = _delta(checks, s, "twalk0", "twalk", "Shots")
    _report(checks, f"{s} walking shots repeat", shots is not None and shots >= 2, f"shots={shots}")
    _pose_held(checks, "tps_pose_walk", 24)
    clears = _delta(checks, s, "twalk0", "twalk", "UpperClears")
    _report(checks, f"{s} upper bracket never cleared while walking", clears == 0, f"clears={clears}")
    # Negative: aiming owns the upper body; the hold is off.
    checks.true(s, "taim", "AimActive")
    checks.false(s, "taim", "ReadyHold")
    checks.eq(s, "taim", "UpperState", 4)
    # After the aim the hold returns.
    checks.false(s, "trel", "AimActive")
    checks.true(s, "trel", "ReadyHold")
    checks.gt(s, "trel", "UpperState", 0)
    # Negative: Attack single ends the hold inside the 2 s linger.
    checks.false(s, "tsingle", "Auto")
    checks.false(s, "tsingle", "ReadyHold")
    checks.eq(s, "tsingle", "UpperState", 0)
    checks.false(s, "tsingle", "AttackOrder")
    single = _delta(checks, s, "tsingle", "tend", "Shots")
    _report(checks, f"{s} no shot in Attack single", single == 0, f"shots={single}")
    checks.eq(s, "tend", "UpperState", 0)

    # Negative: Attack single, enemy in range: no shot, no pose.
    s = "tps_pose_single"
    checks.true(s, "t0000", "TpsMode")
    checks.false(s, "t0000", "Auto")
    checks.true(s, "t0000", "InRange")
    got = checks.value(s, "", "Samples")
    none = checks.value(s, "", "NoneSamples")
    _report(checks, f"{s} no pose in any sample", got == 32 and none == 32, f"samples={got} none={none}")
    idle = _delta(checks, s, "t0000", "tend", "Shots")
    _report(checks, f"{s} no shot", idle == 0, f"shots={idle}")
    checks.false(s, "tend", "ReadyHold")
    checks.false(s, "tend", "AttackOrder")
