from __future__ import annotations

import math
import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from character_anim_assets import AIM_DIRECTIONS
from jumpanim import bake as jump
from jumpanim.bake import (
    AIR,
    AIR_ANKLE_DEG,
    AIR_KNEE_DEG,
    APEX_MS,
    CROUCH_ANKLE_DEG,
    CROUCH_KNEE_DEG,
    CROUCH_MS,
    CROUCH_PEAK_MS,
    END,
    FALL_GAIN,
    FEET,
    FLIGHT_PHASE,
    FLIGHT_PHASE_BACK,
    GATHER_FEET,
    GATHER_REFERENCE,
    JUMP_BASES,
    JUMP_GROUPS,
    JUMP_HEROES,
    LAND_ANKLE_DEG,
    LAND_CYCLE,
    LAND_KNEE_DEG,
    LEGS,
    PELVIS,
    PUSH_CYCLE,
    REFERENCE,
    STAND_BASE,
    START,
    STRIDES,
    TIME_UP_MS,
    TOUCHDOWN_MS,
    WALK_DIRECTIONS,
    Rig,
    ankle_change,
    base_ms,
    base_time,
    baked_name,
    bone_world,
    crouch_shift,
    crouch_weight,
    flight_phase,
    gather_weight,
    joint_width,
    knee_change,
    knee_position,
    make_rig,
    point_weight,
    sample_times,
    shape_pose,
    tuck_weight,
    walk_phase,
)
from testkit.profiles import jump as jump_profile

SCRIPTS = Path(__file__).resolve().parents[2]
APP = SCRIPTS.parent / "src" / "SCOBA.SC2Map" / "scripts" / "app"
JUMP_CORE = APP / "core" / "jump.galaxy"
JUMP_SYSTEM = APP / "systems" / "jump.galaxy"


def galaxy_number(name: str) -> float:
    match = re.search(rf"const (?:fixed|int) {name} = ([0-9.]+);", JUMP_CORE.read_text(encoding="utf-8"))
    if match is None:
        raise AssertionError(f"{name} not in {JUMP_CORE}")
    return float(match.group(1))


galaxy_fixed = galaxy_number


class JumpClipPlanTest(unittest.TestCase):
    """The clip plan matches REQ-JUMP and the script (R-JUMP-10, 11, 16, 18)."""

    def test_poses_come_from_the_hero_not_a_donor(self) -> None:
        self.assertEqual(JUMP_HEROES, frozenset({"tosh"}))
        self.assertFalse(hasattr(jump, "JUMP_DONORS"))
        for name in ("jumpanim/bake.py", "jumpanim/kin.py", "jumpanim/ik.py", "character_anim_assets.py"):
            text = (SCRIPTS / name).read_text(encoding="utf-8").lower()
            self.assertNotIn("spectre.m3", text, name)
            self.assertNotIn("unload end", text.replace("no donor", ""), name)

    def test_clip_times_match_the_script(self) -> None:
        self.assertAlmostEqual(galaxy_fixed("c_JUMP_RISE_TIME"), START.length_ms / 1000.0, places=3)
        self.assertAlmostEqual(galaxy_fixed("c_JUMP_LAND_TIME"), END.length_ms / 1000.0, places=3)
        self.assertAlmostEqual(galaxy_fixed("c_JUMP_CROUCH"), CROUCH_MS / 1000.0, places=3)
        self.assertTrue(AIR.looping)
        self.assertFalse(START.looping or END.looping)
        # The flight the gather follows is the script's flight.
        self.assertAlmostEqual(galaxy_fixed("c_JUMP_TIME_UP"), TIME_UP_MS / 1000.0, places=3)
        self.assertAlmostEqual(galaxy_fixed("c_JUMP_FALL_GAIN"), FALL_GAIN, places=3)
        self.assertAlmostEqual(TOUCHDOWN_MS, 687.0, delta=1.0)  # crouch 150 + rise 300 + fall 237
        # The air clip does not wrap before touchdown, with one game loop to spare.
        self.assertGreaterEqual(AIR.length_ms, TOUCHDOWN_MS - START.length_ms + galaxy_fixed("c_JUMP_TICK") * 1000.0)

    def test_script_names_match_the_baked_clips(self) -> None:
        text = JUMP_SYSTEM.read_text(encoding="utf-8")
        prefixes = re.findall(r'gf_JumpConfigClip\(c_ANIM_HERO_TOSH, c_JUMP_\w+, "([^"]+)"\)', text)
        walks = re.findall(r'gv_jumpDirName\[c_ANIM_DIR_\w+\] = "([^"]+)";', text)
        names = set()
        for prefix in prefixes:
            names.add(f"{prefix} Stand Leg".replace(",", " "))
            for walk in walks:
                # Every phase on a walk exists once per stride, as gf_JumpClipNow names them.
                names.update(f"{prefix} {walk} 0{k} Leg".replace(",", " ") for k in range(1, STRIDES + 1))
        self.assertEqual(names, set(JUMP_GROUPS))
        self.assertEqual(len(JUMP_GROUPS), 3 + 3 * 8 * STRIDES)

    def test_walk_bases_match_the_aim_walk_clips(self) -> None:
        self.assertEqual(WALK_DIRECTIONS, tuple(name for name, _, _ in AIM_DIRECTIONS))
        self.assertEqual((STAND_BASE.token, STAND_BASE.group, STAND_BASE.walk), ("Stand", "Attack Stand", False))
        self.assertEqual(baked_name(START, JUMP_BASES[1], 1), "Jump Start Walk Forward 02 Leg")
        self.assertEqual(baked_name(AIR, STAND_BASE), "Jump Stand Leg")

    def test_clip_time_message_uses_the_accepted_form(self) -> None:
        # libNtve_gf_AnimSetTime writes "False"; the engine rejects it
        # (ScriptError 2026-11-16 18.41.38). SetAnimationTime writes 0/1.
        text = JUMP_SYSTEM.read_text(encoding="utf-8")
        self.assertNotIn("libNtve_gf_AnimSetTime(", text)
        self.assertIn("libNtve_gf_SetAnimationTime(", text)

    def test_no_bare_jump_clip_is_played(self) -> None:
        text = JUMP_SYSTEM.read_text(encoding="utf-8")
        for bare in ("Jump,Start,Leg", "Jump,Leg", "Jump,End,Leg"):
            self.assertNotIn(f'"{bare}"', text)

    def test_thump_is_the_light_dust_and_the_dirt_impact_sound(self) -> None:
        from footfall.fx import FOOTFALL_UNITS, sound_xml

        units = {spec.unit: spec for spec in FOOTFALL_UNITS}
        text = JUMP_CORE.read_text(encoding="utf-8")
        model = re.search(r'c_JUMP_THUMP_MODEL = "([^"]+)"', text).group(1)
        sound = re.search(r'c_JUMP_THUMP_SOUND = "([^"]+)"', text).group(1)
        data = (APP.parents[1] / "Base.SC2Data" / "GameData" / "ModelData.xml").read_text(encoding="utf-8")
        block = re.search(rf'<CModel id="{model}"[^>]*>(.*?)</CModel>', data, re.S)
        self.assertIsNotNone(block, f"{model} not in the source ModelData")
        # The light physics impact puff; JumpLandDust was too large (operator).
        self.assertIn(r"PhysicsImpactDustLight\PhysicsImpactDustLight.m3", block.group(1))
        self.assertNotIn("JumpLandDust", block.group(0))
        # A light dirt impact (operator 2026-11-20), not a footfall: the Queen's
        # were stone footsteps, the Goliath's too big (operator 2026-11-17).
        sounds = (APP.parents[1] / "Base.SC2Data" / "GameData" / "SoundData.xml").read_text(encoding="utf-8")
        entry = re.search(rf'<CSound id="{sound}"[^>]*>(.*?)</CSound>', sounds, re.S)
        self.assertIsNotNone(entry, f"{sound} not in the source SoundData")
        files = re.findall(r'<AssetArray File="([^"]+)"', entry.group(1))
        self.assertEqual(len(files), 10)
        for file in files:
            self.assertIn("PhysicsImpactSound_Dirt_Light", file)
        for unit in ("Queen", "Goliath"):
            self.assertNotIn(f'<CSound id="{sound}"', sound_xml(units[unit]))

    def test_constants_match_requirement(self) -> None:
        self.assertEqual(galaxy_fixed("c_JUMP_PEAK"), 0.6)
        self.assertEqual(galaxy_fixed("c_JUMP_TICK"), 0.0625)
        self.assertGreater(galaxy_fixed("c_JUMP_FALL_GAIN"), 1.0)


def ballistic(t: float) -> float:
    """The R-JUMP-3 curve from the Galaxy constants (mirror of gf_JumpArc)."""
    peak, crouch, up, gain = (galaxy_fixed(n) for n in ("c_JUMP_PEAK", "c_JUMP_CROUCH", "c_JUMP_TIME_UP", "c_JUMP_FALL_GAIN"))
    g_up = 2.0 * peak / (up * up)
    g_down = gain * g_up
    down = math.sqrt(2.0 * peak / g_down)
    s = t - crouch
    if s <= 0.0 or s >= up + down:
        return 0.0
    if s < up:
        return g_up * up * s - 0.5 * g_up * s * s
    return max(0.0, peak - 0.5 * g_down * (s - up) ** 2)


class BallisticTest(unittest.TestCase):
    def test_peak_and_continuity(self) -> None:
        crouch, up = galaxy_fixed("c_JUMP_CROUCH"), galaxy_fixed("c_JUMP_TIME_UP")
        self.assertAlmostEqual(ballistic(crouch + up), 0.6, places=6)
        self.assertAlmostEqual(ballistic(crouch + up - 1e-6), ballistic(crouch + up + 1e-6), places=4)

    def test_crouch_stays_on_the_ground(self) -> None:
        self.assertEqual(ballistic(0.0), 0.0)
        self.assertEqual(ballistic(galaxy_fixed("c_JUMP_CROUCH")), 0.0)

    def test_fall_is_faster_than_rise(self) -> None:
        peak, up, gain = galaxy_fixed("c_JUMP_PEAK"), galaxy_fixed("c_JUMP_TIME_UP"), galaxy_fixed("c_JUMP_FALL_GAIN")
        down = up / math.sqrt(gain)
        self.assertLess(down, up)
        airtime = galaxy_fixed("c_JUMP_CROUCH") + up + down
        self.assertTrue(0.6 < airtime < 0.75, airtime)
        self.assertEqual(ballistic(airtime + 1e-6), 0.0)
        self.assertGreater(peak, 0.0)

    def test_takeoff_clip_covers_the_launch(self) -> None:
        # The Start clip is still extending the legs when the hero leaves the ground.
        self.assertLess(galaxy_fixed("c_JUMP_CROUCH"), galaxy_fixed("c_JUMP_RISE_TIME"))


class ProfileTest(unittest.TestCase):
    """Crouch, tuck, and walk phase over the three clips."""

    def test_reference_targets_are_inside_the_mocap_ranges(self) -> None:
        # CMU subject 16, trials 01, 02, 05 (character_anim_jump docstring).
        targets = (
            ("crouch knee", CROUCH_KNEE_DEG),
            ("crouch ankle", CROUCH_ANKLE_DEG),
            ("landing knee", LAND_KNEE_DEG),
            ("landing ankle", LAND_ANKLE_DEG),
            ("air knee", AIR_KNEE_DEG),
            ("air ankle", AIR_ANKLE_DEG),
        )
        for name, value in targets:
            low, high = REFERENCE[name]
            self.assertTrue(low <= value <= high, name)
        # The takeoff crouch is deeper than the landing; the ground ankle is dorsiflexed.
        self.assertGreater(CROUCH_KNEE_DEG, LAND_KNEE_DEG)
        self.assertLess(REFERENCE["crouch ankle"][1], 0.0)
        self.assertLess(REFERENCE["landing ankle"][1], 0.0)

    def test_start_crouches_on_the_ground_and_extends_through_liftoff(self) -> None:
        self.assertEqual(crouch_weight(START, 0), 0.0)
        self.assertEqual(crouch_weight(START, CROUCH_PEAK_MS), 1.0)
        self.assertLess(CROUCH_PEAK_MS, CROUCH_MS)
        # Reference: at liftoff the knees are about 70% extended.
        self.assertTrue(0.15 <= crouch_weight(START, CROUCH_MS) <= 0.35, crouch_weight(START, CROUCH_MS))
        self.assertEqual(crouch_weight(START, START.length_ms), 0.0)

    def test_crouch_is_explosive_not_eased(self) -> None:
        def speed(phase, ms: float) -> float:
            return abs(crouch_weight(phase, ms + 1.0) - crouch_weight(phase, ms - 1.0)) / 2.0

        # Takeoff: the legs extend faster and faster up to liftoff.
        up = [speed(START, ms) for ms in range(CROUCH_PEAK_MS + 5, CROUCH_MS, 10)]
        self.assertEqual(up, sorted(up))
        self.assertGreater(speed(START, CROUCH_MS), 3.0 * speed(START, CROUCH_PEAK_MS + 5))
        # Landing: the impact is fastest at touchdown and brakes into the low point.
        down = [speed(END, ms) for ms in range(2, jump.LAND_PEAK_MS - 2, 8)]
        self.assertEqual(down, sorted(down, reverse=True))
        # Negative: an eased (smoothstep) crouch starts at speed 0.
        self.assertGreater(speed(END, 2), 0.02)
        self.assertLess(abs(jump.smoothstep(0.0, 60.0, 3.0) - jump.smoothstep(0.0, 60.0, 1.0)) / 2.0, 0.005)
        # Short: both low points within 60 ms, the landing over within 250 ms.
        self.assertLessEqual(CROUCH_PEAK_MS, 60)
        self.assertLessEqual(jump.LAND_PEAK_MS, 60)
        self.assertLessEqual(END.length_ms, 250)

    def test_ground_walk_plays_at_the_walk_rate(self) -> None:
        # At clip time scale 1 the walk under Start and End runs at walk rate 1.
        for phase in (START, END):
            self.assertAlmostEqual(jump.walk_rate(phase, 667.0), 1.0, delta=0.02)
        # Negative: the old clips (0.25 of a cycle in 133 ms; 0.35 in 400 ms).
        self.assertAlmostEqual(0.25 * 667.0 / 133.0, 1.25, delta=0.01)
        self.assertAlmostEqual(0.35 * 667.0 / 400.0, 0.58, delta=0.01)

    def test_feet_stay_flat_and_down_until_liftoff(self) -> None:
        for ms in (0, 33, 66, 99, CROUCH_MS):
            self.assertEqual(tuck_weight(START, ms), 0.0)
            self.assertEqual(point_weight(START, ms), 0.0)
        self.assertEqual(tuck_weight(START, START.length_ms), 1.0)
        self.assertEqual(point_weight(START, START.length_ms), 1.0)
        # The ankle swings faster than the tuck: toes down 66 ms after liftoff.
        self.assertEqual(point_weight(START, CROUCH_MS + 66), 1.0)

    def test_air_is_tucked_and_pointed(self) -> None:
        for ms in (0, 150):
            self.assertEqual((crouch_weight(AIR, ms), tuck_weight(AIR, ms), point_weight(AIR, ms)), (0.0, 1.0, 1.0))

    def test_end_flattens_the_feet_crouches_and_recovers(self) -> None:
        self.assertEqual((crouch_weight(END, 0), tuck_weight(END, 0), point_weight(END, 0)), (0.0, 1.0, 1.0))
        # Toes first: the feet are flat and down 66 ms after touchdown.
        self.assertEqual((tuck_weight(END, 66), point_weight(END, 66)), (0.0, 0.0))
        self.assertEqual(crouch_weight(END, jump.LAND_PEAK_MS), 1.0)
        self.assertEqual(crouch_weight(END, jump.LAND_RECOVER_MS), 0.0)
        self.assertLess(jump.LAND_RECOVER_MS, END.length_ms)
        # The last frame is the plain base pose.
        self.assertEqual((crouch_weight(END, END.length_ms), tuck_weight(END, END.length_ms), point_weight(END, END.length_ms)), (0.0, 0.0, 0.0))

    def test_clips_join_without_a_step(self) -> None:
        # Start ends as Air; End begins as Air.
        for weight in (crouch_weight, tuck_weight, point_weight):
            self.assertEqual(weight(START, START.length_ms), weight(AIR, 0))
            self.assertEqual(weight(END, 0), weight(AIR, 0))

    def test_gather_peaks_at_the_apogee_and_is_gone_on_the_ground(self) -> None:
        # On the ground before liftoff and after touchdown: none.
        for ms in (0, 66, CROUCH_MS):
            self.assertEqual(gather_weight(START, ms), 0.0)
        for ms in (0, 66, END.length_ms):
            self.assertEqual(gather_weight(END, ms), 0.0)
        self.assertEqual(gather_weight(AIR, APEX_MS - START.length_ms), 1.0)
        self.assertAlmostEqual(gather_weight(AIR, TOUCHDOWN_MS - START.length_ms), 0.0, places=9)
        self.assertEqual(gather_weight(AIR, AIR.length_ms), 0.0)
        # It rises all the way to the apogee and falls all the way after it.
        rise = [gather_weight(START, ms) for ms in range(CROUCH_MS, START.length_ms + 1, 10)]
        rise += [gather_weight(AIR, ms) for ms in range(0, APEX_MS - START.length_ms + 1, 10)]
        self.assertEqual(rise, sorted(rise))
        fall = [gather_weight(AIR, ms) for ms in range(APEX_MS - START.length_ms, AIR.length_ms + 1, 10)]
        self.assertEqual(fall, sorted(fall, reverse=True))
        # No step between the clips.
        self.assertEqual(gather_weight(START, START.length_ms), gather_weight(AIR, 0))
        self.assertAlmostEqual(gather_weight(AIR, TOUCHDOWN_MS - START.length_ms), gather_weight(END, 0), places=9)
        # The target is inside the reference.
        low, high = GATHER_REFERENCE["feet"]
        self.assertTrue(low <= GATHER_FEET <= high)

    def test_walk_phase_runs_to_the_flight_frame_and_on(self) -> None:
        forward, back = JUMP_BASES[1], JUMP_BASES[5]
        self.assertEqual((forward.token, back.token), ("Walk Forward", "Walk Back"))
        self.assertEqual((forward.flight, back.flight), (FLIGHT_PHASE, FLIGHT_PHASE_BACK))
        for base in (forward, back):
            for stride in range(STRIDES):
                flight = flight_phase(base, stride)
                self.assertAlmostEqual(walk_phase(START, base, stride, 0), (flight - PUSH_CYCLE) % 1.0)
                self.assertAlmostEqual(walk_phase(START, base, stride, CROUCH_MS), flight)
                # In the air the walk plays on slowly: not a freeze frame.
                touchdown = TOUCHDOWN_MS - START.length_ms
                self.assertAlmostEqual(walk_phase(START, base, stride, START.length_ms), walk_phase(AIR, base, stride, 0))
                self.assertAlmostEqual(walk_phase(AIR, base, stride, touchdown), (flight + jump.AIR_CYCLE) % 1.0)
                self.assertAlmostEqual(walk_phase(AIR, base, stride, AIR.length_ms), (flight + jump.AIR_CYCLE) % 1.0)
                self.assertAlmostEqual(walk_phase(END, base, stride, 0), walk_phase(AIR, base, stride, touchdown))
                self.assertAlmostEqual(walk_phase(END, base, stride, END.length_ms), (flight + LAND_CYCLE) % 1.0)
        # The strides are half a cycle apart: the other foot leads.
        self.assertAlmostEqual((flight_phase(forward, 1) - flight_phase(forward, 0)) % 1.0, 0.5)

    def test_stand_runs_on_under_the_jump(self) -> None:
        self.assertEqual(base_time(START, STAND_BASE, None, 100, 0), 100)
        self.assertEqual(base_time(AIR, STAND_BASE, None, 0, 0), START.length_ms)
        # A walk base moves on from the flight frame in the air, slowly.
        self.assertAlmostEqual(base_time(AIR, JUMP_BASES[1], 0, 50, 667), (FLIGHT_PHASE + jump.air_drift(START.length_ms + 50)) * 667)

    def test_air_drift_is_slow_and_steady(self) -> None:
        self.assertEqual(jump.air_drift(0), 0.0)
        self.assertEqual(jump.air_drift(CROUCH_MS), 0.0)  # on the ground: none
        self.assertAlmostEqual(jump.air_drift(TOUCHDOWN_MS), jump.AIR_CYCLE)
        self.assertEqual(jump.air_drift(TOUCHDOWN_MS + 500), jump.AIR_CYCLE)
        steps = [jump.air_drift(ms + 50) - jump.air_drift(ms) for ms in range(CROUCH_MS, int(TOUCHDOWN_MS) - 50, 50)]
        self.assertTrue(all(step > 0.0 for step in steps))
        self.assertAlmostEqual(max(steps), min(steps), places=9)
        # Very slowly: under a fifth of the walk rate, and less than the landing plays.
        rate = jump.AIR_CYCLE * 667.0 / (TOUCHDOWN_MS - CROUCH_MS)
        self.assertTrue(0.02 <= rate <= 0.2, rate)
        self.assertLess(jump.AIR_CYCLE, LAND_CYCLE)

    def test_galaxy_gait_constants(self) -> None:
        self.assertEqual(galaxy_number("c_JUMP_GAIT_STRIDES"), STRIDES)
        self.assertEqual(galaxy_number("c_JUMP_GAIT_FLIGHT"), FLIGHT_PHASE)
        self.assertEqual(galaxy_number("c_JUMP_GAIT_FLIGHT_BACK"), FLIGHT_PHASE_BACK)
        self.assertEqual(galaxy_number("c_JUMP_GAIT_PUSH"), PUSH_CYCLE)
        self.assertEqual(galaxy_number("c_JUMP_GAIT_LAND"), LAND_CYCLE)
        self.assertEqual(galaxy_number("c_JUMP_GAIT_CYCLE"), 0.667)

    def test_stride_pick_is_the_start_clip_nearest_the_walk_phase(self) -> None:
        # Mirror of gf_JumpGaitStride (testkit.profiles.jump.strides_for).
        cycle = jump_profile.CYCLE_MS
        for stride in range(STRIDES):
            begin = ((flight_phase(JUMP_BASES[1], stride) - PUSH_CYCLE) % 1.0) * cycle
            self.assertEqual(jump_profile.strides_for(round(begin)), {stride})
            self.assertEqual(jump_profile.strides_for(round(begin + 0.2 * cycle) % cycle), {stride})
            self.assertEqual(jump_profile.strides_for(round(begin - 0.2 * cycle) % cycle), {stride})

    def test_sampling(self) -> None:
        self.assertEqual(sample_times(100), [0, 33, 66, 99, 100])
        self.assertEqual(base_ms(100, 1100, 1250, True), 350)
        self.assertEqual(base_ms(100, 1100, 1250, False), 1100)


if __name__ == "__main__":
    unittest.main()
