"""Jump leg IK and pose shaping on a synthetic two-leg rig."""

from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from jumpanim import bake as jump
from jumpanim.bake import (
    AIR_ANKLE_DEG,
    AIR_KNEE_DEG,
    CROUCH_ANKLE_DEG,
    CROUCH_KNEE_DEG,
    FEET,
    GATHER_FEET,
    LAND_ANKLE_DEG,
    LAND_KNEE_DEG,
    LEGS,
    PELVIS,
    Rig,
    ankle_change,
    bone_world,
    crouch_shift,
    joint_width,
    knee_change,
    knee_position,
    make_rig,
    shape_pose,
)


def track(anim_id: int, **value) -> SimpleNamespace:
    return SimpleNamespace(header=SimpleNamespace(animId=anim_id), initValue=SimpleNamespace(**value))


def quat_about_z(degrees: float) -> dict:
    half = math.radians(degrees) / 2.0
    return {"x": 0.0, "y": 0.0, "z": math.sin(half), "w": math.cos(half)}


def rig() -> SimpleNamespace:
    """A two-leg rig like Tosh's: scaled and turned model root, bent knees."""
    identity = {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}
    rows = [
        # name, parent, location, rotation, scale
        ("Main", -1, (0.0, 0.0, 0.0), quat_about_z(90.0), 1.6),
        (PELVIS, 0, (0.0, 0.0, 0.45), quat_about_z(-20.0), 0.84),
        ("BoneLegL", 1, (0.08, 0.0, -0.03), identity, 1.18),
        ("BoneCalfL", 2, (0.01, -0.07, -0.15), quat_about_z(10.0), 1.0),
        ("BoneFootL", 3, (0.01, 0.08, -0.16), identity, 1.0),
        ("BoneLegR", 1, (-0.08, 0.0, -0.03), identity, 1.18),
        ("BoneCalfR", 5, (-0.01, -0.07, -0.15), identity, 1.0),
        ("BoneFootR", 6, (-0.01, 0.01, -0.17), identity, 1.0),
    ]
    bones = []
    for index, (name, parent, loc, rot, scale) in enumerate(rows):
        bones.append(
            SimpleNamespace(
                name=name,
                parent=parent,
                location=track(index * 3, x=loc[0], y=loc[1], z=loc[2]),
                rotation=track(index * 3 + 1, **rot),
                scale=track(index * 3 + 2, x=scale, y=scale, z=scale),
            )
        )
    return SimpleNamespace(bones=bones)


def bone_lengths(model, pose) -> list[float]:
    out = []
    for thigh, calf, foot in LEGS:
        world = bone_world(model, pose, (thigh, calf, foot))
        out += [math.dist(world[thigh][0], world[calf][0]), math.dist(world[calf][0], world[foot][0])]
    return out


class LegSolveTest(unittest.TestCase):
    """Crouch and tuck keep the feet and the bone lengths (two-bone IK)."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.model = rig()
        cls.rig = make_rig(cls.model, {})  # solved once: the reference depths
        cls.rest = bone_world(cls.model, {}, FEET + (PELVIS,))
        cls.lengths = bone_lengths(cls.model, {})

    def shaped(self, crouch, tuck: float, point: float, rig: Rig | None = None) -> dict:
        """crouch: a straight drop (number) or a rig depth (down, back)."""
        shift = crouch_shift(self.rig.forward, crouch, 1.0) if isinstance(crouch, tuple) else (0.0, 0.0, -crouch)
        pose = {}
        shape_pose(self.model, pose, rig or self.rig, shift, tuck, point)
        return pose

    def assert_lengths_kept(self, pose) -> None:
        for got, want in zip(bone_lengths(self.model, pose), self.lengths):
            self.assertAlmostEqual(got, want, places=6)

    def test_scale_is_part_of_the_pose(self) -> None:
        # Main is scaled 1.6: the pelvis is at 0.45 * 1.6.
        self.assertAlmostEqual(self.rest[PELVIS][0][2], 0.72, places=6)

    def test_crouch_drops_the_pelvis_and_plants_the_feet(self) -> None:
        pose = self.shaped(0.08, 0.0, 0.0)
        world = bone_world(self.model, pose, FEET + (PELVIS,))
        self.assertAlmostEqual(world[PELVIS][0][2], self.rest[PELVIS][0][2] - 0.08, places=6)
        for axis in (0, 1):
            self.assertAlmostEqual(world[PELVIS][0][axis], self.rest[PELVIS][0][axis], places=6)
        for foot in FEET:
            for axis in range(3):
                self.assertAlmostEqual(world[foot][0][axis], self.rest[foot][0][axis], places=6)
            for got, want in zip(world[foot][1], self.rest[foot][1]):
                self.assertAlmostEqual(abs(got), abs(want), places=6)  # the foot keeps its rotation
        self.assert_lengths_kept(pose)

    def test_tuck_lifts_the_feet_straight_up(self) -> None:
        pose = self.shaped(0.0, 0.05, 0.0)
        world = bone_world(self.model, pose, FEET + (PELVIS,))
        self.assertAlmostEqual(world[PELVIS][0][2], self.rest[PELVIS][0][2], places=6)
        for foot in FEET:
            self.assertAlmostEqual(world[foot][0][0], self.rest[foot][0][0], places=6)
            self.assertAlmostEqual(world[foot][0][1], self.rest[foot][0][1], places=6)
            self.assertAlmostEqual(world[foot][0][2], self.rest[foot][0][2] + 0.05, places=6)
        self.assert_lengths_kept(pose)

    def test_tuck_brings_the_thighs_forward(self) -> None:
        # The air pose: feet up under the hips, so the thigh goes forward
        # (knee up) by about half the knee bend, as in the reference (F17).
        pose = self.shaped(0.0, self.rig.tuck, 0.0)
        hip = jump.hip_change(self.model, pose, {}, self.rig)
        knee = knee_change(self.model, pose, self.rig)
        self.assertGreater(hip, 0.3 * knee)
        self.assertLess(hip, 0.8 * knee)
        # Negative: no tuck, no hip change.
        self.assertAlmostEqual(jump.hip_change(self.model, {}, {}, self.rig), 0.0, places=6)

    def test_nothing_asked_changes_nothing(self) -> None:
        self.assertEqual(self.shaped(0.0, 0.0, 0.0), {})

    def test_depths_give_the_reference_angles(self) -> None:
        self.assertAlmostEqual(knee_change(self.model, {}, self.rig), 0.0, places=6)
        self.assertAlmostEqual(ankle_change(self.model, {}, self.rig), 0.0, places=6)
        for depth, knee, ankle in ((self.rig.crouch, CROUCH_KNEE_DEG, CROUCH_ANKLE_DEG), (self.rig.land, LAND_KNEE_DEG, LAND_ANKLE_DEG)):
            pose = self.shaped(depth, 0.0, 0.0)
            self.assertAlmostEqual(knee_change(self.model, pose, self.rig), knee, places=2)
            self.assertAlmostEqual(ankle_change(self.model, pose, self.rig), ankle, places=2)
        self.assertAlmostEqual(knee_change(self.model, self.shaped(0.0, self.rig.tuck, 0.0), self.rig), AIR_KNEE_DEG, places=2)
        self.assertGreater(self.rig.crouch[0], self.rig.land[0])

    def test_crouch_bends_the_ankle_over_a_flat_foot(self) -> None:
        # The foot keeps its rotation and the shin leans: dorsiflexion.
        down, back = self.rig.crouch
        straight = ankle_change(self.model, self.shaped(down, 0.0, 0.0), self.rig)
        self.assertLess(straight, -5.0)
        # The pelvis moving back keeps the shin more upright.
        self.assertGreater(back, 0.0)
        self.assertGreater(ankle_change(self.model, self.shaped((down, back), 0.0, 0.0), self.rig), straight)

    def test_crouch_moves_the_pelvis_back_along_the_knees(self) -> None:
        down, back = self.rig.crouch
        world = bone_world(self.model, self.shaped((down, back), 0.0, 0.0), (PELVIS,) + FEET)
        moved = tuple(a - b for a, b in zip(world[PELVIS][0], self.rest[PELVIS][0]))
        self.assertAlmostEqual(moved[2], -down, places=6)
        self.assertAlmostEqual(moved[0] * self.rig.forward[0] + moved[1] * self.rig.forward[1], -back, places=6)
        for foot in FEET:  # the feet stay planted
            self.assertAlmostEqual(math.dist(world[foot][0], self.rest[foot][0]), 0.0, places=6)

    def test_point_turns_the_foot_to_the_reference_angle(self) -> None:
        pose = self.shaped(0.0, 0.0, 1.0)
        self.assertAlmostEqual(ankle_change(self.model, pose, self.rig), AIR_ANKLE_DEG, places=4)
        self.assertAlmostEqual(ankle_change(self.model, self.shaped(0.0, 0.0, 0.5), self.rig), AIR_ANKLE_DEG / 2.0, places=4)
        # Only the foot turns: the ankle stays where it is and the knee as it is.
        world = bone_world(self.model, pose, FEET)
        for foot in FEET:
            self.assertAlmostEqual(math.dist(world[foot][0], self.rest[foot][0]), 0.0, places=6)
        self.assertAlmostEqual(knee_change(self.model, pose, self.rig), 0.0, places=6)
        # The same flight angle whatever the knee does.
        self.assertAlmostEqual(ankle_change(self.model, self.shaped(0.0, self.rig.tuck, 1.0), self.rig), AIR_ANKLE_DEG, places=4)

    def test_a_foot_in_the_air_goes_down_with_the_pelvis(self) -> None:
        # FootL counts as lifted: its standing height is far below.
        ground = dict(self.rig.ground)
        ground[FEET[0]] -= 1.0
        world = bone_world(self.model, self.shaped(0.08, 0.0, 0.0, self.rig._replace(ground=ground)), FEET)
        self.assertAlmostEqual(world[FEET[0]][0][2], self.rest[FEET[0]][0][2] - 0.08, places=6)
        self.assertAlmostEqual(world[FEET[1]][0][2], self.rest[FEET[1]][0][2], places=6)

    def test_gather_brings_feet_and_knees_together_sideways(self) -> None:
        forward = self.rig.forward
        before = [joint_width(self.model, {}, forward, joint) for joint in (0, 1, 2)]
        self.assertGreater(before[2], GATHER_FEET * self.rig.hips)  # the stand is wider than the target
        pose = {}
        shape_pose(self.model, pose, self.rig, (0.0, 0.0, 0.0), 0.0, 0.0, 1.0)
        after = [joint_width(self.model, pose, forward, joint) for joint in (0, 1, 2)]
        # The same feet without the knee swivel: the swivel does not bend the knee.
        feet_only = {}
        middle = sum(jump.dot(bone_world(self.model, {}, (leg[0],))[leg[0]][0], jump.side_axis(forward)) for leg in LEGS) / len(LEGS)
        for leg in LEGS:
            position, rotation, _ = bone_world(self.model, feet_only, (leg[2],))[leg[2]]
            jump.solve_leg(self.model, feet_only, leg, jump.gather_foot(self.rig, position, middle, 1.0), rotation, 0.0)
        self.assertAlmostEqual(after[0], before[0], places=6)  # the hips stay
        self.assertAlmostEqual(after[2], GATHER_FEET * self.rig.hips, places=5)
        # The knees too: the leg swivels about the hip to foot line.
        self.assertGreater(before[1], jump.GATHER_KNEES * self.rig.hips)
        self.assertAlmostEqual(after[1], jump.GATHER_KNEES * self.rig.hips, places=5)
        self.assertAlmostEqual(knee_change(self.model, pose, self.rig), knee_change(self.model, feet_only, self.rig), places=4)
        # Only sideways: no move along forward, no move up or down.
        world = bone_world(self.model, pose, FEET)
        for foot in FEET:
            moved = tuple(a - b for a, b in zip(world[foot][0], self.rest[foot][0]))
            self.assertAlmostEqual(moved[2], 0.0, places=6)
            self.assertAlmostEqual(moved[0] * forward[0] + moved[1] * forward[1], 0.0, places=6)
        self.assert_lengths_kept(pose)
        # Half the weight: half the way.
        half = {}
        shape_pose(self.model, half, self.rig, (0.0, 0.0, 0.0), 0.0, 0.0, 0.5)
        self.assertAlmostEqual(joint_width(self.model, half, forward, 2), (before[2] + after[2]) / 2.0, places=5)

    def test_gather_never_spreads_the_feet(self) -> None:
        # Hips so wide that the target is outside the stance: the feet stay.
        wide = self.rig._replace(hips=10.0 * self.rig.hips)
        pose = {}
        shape_pose(self.model, pose, wide, (0.0, 0.0, 0.0), 0.0, 0.0, 1.0)
        world = bone_world(self.model, pose, FEET)
        for foot in FEET:
            self.assertAlmostEqual(math.dist(world[foot][0], self.rest[foot][0]), 0.0, places=6)

    def test_knee_stays_on_its_side(self) -> None:
        hip, knee, foot = (0.0, 0.0, 1.0), (0.0, -0.2, 0.5), (0.0, 0.0, 0.0)
        new_knee, reached = knee_position(hip, knee, foot, (0.0, 0.0, 0.3))
        self.assertLess(new_knee[1], -0.2)  # bends further, to the same side
        self.assertAlmostEqual(math.dist(hip, new_knee), math.dist(hip, knee), places=6)
        self.assertAlmostEqual(math.dist(new_knee, reached), math.dist(knee, foot), places=6)
        self.assertAlmostEqual(math.dist(reached, (0.0, 0.0, 0.3)), 0.0, places=9)

    def test_reach_is_clamped_to_what_the_leg_can_do(self) -> None:
        hip, knee, foot = (0.0, 0.0, 1.0), (0.0, -0.2, 0.5), (0.0, 0.0, 0.0)
        _, far = knee_position(hip, knee, foot, (0.0, 0.0, -5.0))
        self.assertLess(math.dist(hip, far), math.dist(hip, knee) + math.dist(knee, foot))
        _, near = knee_position(hip, knee, foot, (0.0, 0.0, 0.99), min_reach=0.3)
        self.assertAlmostEqual(math.dist(hip, near), 0.3, places=6)

    def test_deep_crouch_does_not_fold_the_leg_flat(self) -> None:
        pose = self.shaped(2.0 * self.rig.leg, 0.0, 0.0)  # deeper than the leg is long
        self.assert_lengths_kept(pose)
        for thigh, _, foot in LEGS:
            world = bone_world(self.model, pose, (thigh, foot))
            self.assertGreaterEqual(math.dist(world[thigh][0], world[foot][0]), jump.MIN_REACH * self.rig.leg - 1e-6)


if __name__ == "__main__":
    unittest.main()
