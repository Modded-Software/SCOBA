"""Host tests of the source-clip jump bake (jumpanim.donor, R-JUMP-23):
timing, weights, the per-bone mix, the body rise removal, and the script
config that picks the clips."""

from __future__ import annotations

import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from character_anim_assets import AIM_DIRECTIONS
from heroanim.rig import HEROES
from jumpanim.bake import AIR, CROUCH_MS, END, JUMP_BASES, JUMP_HEROES, START, TOUCHDOWN_MS
from jumpanim.donor import DONOR_HEROES, END_EASE_MS, WALK_WEIGHT, mix_pose, remove_lift, source_ms, source_weight
from jumpanim.kin import TRACK_LOC, TRACK_ROT

ROOT = Path(__file__).resolve().parents[4]
APP = ROOT / "src" / "SCOBA.SC2Map" / "scripts" / "app"
CUT = 1058


def loc(x: float, y: float, z: float) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y, z=z)


def quat(x: float, y: float, z: float, w: float) -> SimpleNamespace:
    return SimpleNamespace(x=x, y=y, z=z, w=w)


class TimingTests(unittest.TestCase):
    def test_source_holds_frame_zero_through_the_crouch(self):
        for ms in (0, 60, CROUCH_MS):
            self.assertEqual(source_ms(START, ms, CUT), 0.0)

    def test_source_reaches_the_cut_at_touchdown(self):
        air_ms = TOUCHDOWN_MS - START.length_ms
        self.assertAlmostEqual(source_ms(AIR, air_ms, CUT), CUT, places=6)
        # Negative: it never runs past the cut (the dive is not used).
        self.assertEqual(source_ms(AIR, AIR.length_ms, CUT), CUT)
        self.assertEqual(source_ms(END, 0, CUT), CUT)

    def test_source_time_rises_through_the_flight(self):
        times = [source_ms(START, ms, CUT) for ms in range(CROUCH_MS, START.length_ms + 1, 10)]
        times += [source_ms(AIR, ms, CUT) for ms in range(0, int(TOUCHDOWN_MS) - START.length_ms, 10)]
        self.assertEqual(times, sorted(times))
        self.assertGreater(times[-1], times[0])


class WeightTests(unittest.TestCase):
    def test_eases_in_over_the_crouch_and_out_over_end(self):
        self.assertEqual(source_weight(START, 0, WALK_WEIGHT), 0.0)
        self.assertAlmostEqual(source_weight(START, CROUCH_MS, WALK_WEIGHT), WALK_WEIGHT)
        self.assertEqual(source_weight(AIR, 100, WALK_WEIGHT), WALK_WEIGHT)
        self.assertAlmostEqual(source_weight(END, 0, 1.0), 1.0)
        self.assertEqual(source_weight(END, END.length_ms, 1.0), 0.0)

    def test_end_eases_out_in_half_the_clip(self):
        self.assertLess(END_EASE_MS, END.length_ms)
        self.assertEqual(source_weight(END, END_EASE_MS, 1.0), 0.0)
        # Negative: still easing just before it.
        self.assertGreater(source_weight(END, END_EASE_MS - 20, 1.0), 0.0)

    def test_walk_weight_is_a_real_mix(self):
        self.assertGreater(WALK_WEIGHT, 0.0)
        self.assertLess(WALK_WEIGHT, 1.0)


class MixTests(unittest.TestCase):
    def setUp(self):
        self.kinds = {1: TRACK_LOC, 2: TRACK_ROT}
        self.base = {1: loc(0.0, 0.0, 0.0), 2: quat(0.0, 0.0, 0.0, 1.0)}
        self.source = {1: loc(1.0, 2.0, 4.0), 2: quat(0.0, 0.0, 0.70710678, 0.70710678)}

    def test_weight_zero_is_the_base_and_one_is_the_source(self):
        low = mix_pose(self.base, self.source, self.kinds, 0.0)
        high = mix_pose(self.base, self.source, self.kinds, 1.0)
        self.assertEqual((low[1].x, low[1].y, low[1].z), (0.0, 0.0, 0.0))
        self.assertAlmostEqual(low[2].w, 1.0)
        self.assertEqual((high[1].x, high[1].y, high[1].z), (1.0, 2.0, 4.0))
        self.assertAlmostEqual(high[2].z, 0.70710678, places=6)

    def test_half_weight_is_halfway(self):
        half = mix_pose(self.base, self.source, self.kinds, 0.5)
        self.assertEqual((half[1].x, half[1].y, half[1].z), (0.5, 1.0, 2.0))
        size = (half[2].x ** 2 + half[2].y ** 2 + half[2].z ** 2 + half[2].w ** 2) ** 0.5
        self.assertAlmostEqual(size, 1.0)
        self.assertGreater(half[2].z, 0.0)
        self.assertLess(half[2].z, 0.70710678)

    def test_remove_lift_moves_only_the_top_bone_down(self):
        pose = {1: loc(0.1, 0.2, 1.0), 2: quat(0.0, 0.0, 0.0, 1.0)}
        remove_lift(pose, 1, 0.85)
        self.assertAlmostEqual(pose[1].z, 0.15)
        self.assertEqual((pose[1].x, pose[1].y), (0.1, 0.2))
        self.assertEqual(pose[2].w, 1.0)


class ConfigTests(unittest.TestCase):
    def test_kerrigan_uses_her_burrow_clip(self):
        donor = DONOR_HEROES["kerrigan"]
        self.assertEqual(donor.source, "Burrow 01")
        self.assertIn("kerrigan", HEROES)
        # Negative: no hero gets both bakes.
        self.assertFalse(set(DONOR_HEROES) & set(JUMP_HEROES))

    def test_walk_directions_match_the_walk_bases(self):
        names = sorted("Walk " + name for name, _, _ in AIM_DIRECTIONS)
        self.assertEqual(names, sorted(base.token for base in JUMP_BASES if base.walk))

    def test_script_configures_both_heroes_and_her_cycle(self):
        text = (APP / "systems" / "jump.galaxy").read_text(encoding="utf-8")
        found = re.findall(r'gf_JumpConfigClip\((c_ANIM_HERO_\w+), c_JUMP_\w+, "([^"]+)"\)', text)
        by_hero = {}
        for hero, prefix in found:
            by_hero.setdefault(hero, []).append(prefix)
        self.assertEqual(sorted(by_hero), ["c_ANIM_HERO_KERRIGAN", "c_ANIM_HERO_TOSH"])
        self.assertEqual(sorted(by_hero["c_ANIM_HERO_KERRIGAN"]), sorted(by_hero["c_ANIM_HERO_TOSH"]))
        self.assertIn("gv_jumpGaitCycle[c_ANIM_HERO_KERRIGAN] = c_JUMP_GAIT_CYCLE_KERRIGAN;", text)
        core = (APP / "core" / "jump.galaxy").read_text(encoding="utf-8")
        self.assertIn("const fixed c_JUMP_GAIT_CYCLE_KERRIGAN = 1.0;", core)
        # Negative: the gait no longer reads Tosh's cycle for every hero.
        self.assertNotIn("/ c_JUMP_GAIT_CYCLE;", text)
        self.assertNotIn("* c_JUMP_GAIT_CYCLE;", text)


if __name__ == "__main__":
    unittest.main()
