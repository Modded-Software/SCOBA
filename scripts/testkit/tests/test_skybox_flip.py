from __future__ import annotations

import math
import unittest
from types import SimpleNamespace

from project_root import project_root
from skybox_flip import AXIS, FLIPS, SD3V_KIND, SD4Q_KIND, flip_model, half_turn_quat, half_turn_vec

MAP = project_root() / "out" / "SCOBA256.SC2Map"
ROOT_ROT_ID = 0x10
ROOT_LOC_ID = 0x11
CHILD_ROT_ID = 0x20
CHILD_LOC_ID = 0x21


def quat(x, y, z, w):
    return SimpleNamespace(x=x, y=y, z=z, w=w)


def xyzw(v) -> dict[str, float]:
    """The vector or quaternion components of v, by name."""
    out = {"x": v.x, "y": v.y, "z": v.z}
    if getattr(v, "w", None) is not None:
        out["w"] = v.w
    return out


def vec(x, y, z):
    return SimpleNamespace(x=x, y=y, z=z)


def ref(value, anim_id):
    copy = SimpleNamespace(**xyzw(value))
    return SimpleNamespace(initValue=value, nullValue=copy, header=SimpleNamespace(animId=anim_id))


def bone(parent, rot, loc, rot_id, loc_id):
    return SimpleNamespace(parent=parent, rotation=ref(rot, rot_id), location=ref(loc, loc_id))


def rotate(q, v):
    """Vector v turned by unit quaternion q (x, y, z, w)."""
    x, y, z, w = q
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return (
        v[0] + w * tx + (y * tz - z * ty),
        v[1] + w * ty + (z * tx - x * tz),
        v[2] + w * tz + (x * ty - y * tx),
    )


def fake_model(root_keys=True):
    stc = SimpleNamespace(sd3v=[], sd4q=[], animIds=[], animRefs=[])
    if root_keys:
        stc.sd4q.append(SimpleNamespace(keys=[quat(0.0, 0.0, 0.0, 1.0), quat(0.1, 0.0, 0.0, 0.995)]))
        stc.sd3v.append(SimpleNamespace(keys=[vec(1.0, 2.0, 3.0)]))
        stc.animIds += [ROOT_ROT_ID, ROOT_LOC_ID]
        stc.animRefs += [(SD4Q_KIND << 16) | 0, (SD3V_KIND << 16) | 0]
    root = bone(-1, quat(0.0, 0.0, 0.0, 1.0), vec(0.5, 0.25, -13.0), ROOT_ROT_ID, ROOT_LOC_ID)
    child = bone(0, quat(0.1, 0.0, 0.0, 0.995), vec(0.0, 0.0, 0.0), CHILD_ROT_ID, CHILD_LOC_ID)
    return SimpleNamespace(bones=[root, child], sequenceTransformationCollections=[stc])


class FlipTest(unittest.TestCase):
    def test_axis_is_y(self) -> None:
        self.assertEqual(AXIS, (0.0, 1.0, 0.0))

    def test_half_turn_about_y(self) -> None:
        q = half_turn_quat(0.0, 0.0, 0.0, 1.0)
        for got, want in (
            (rotate(q, (0.0, 1.0, 0.0)), (0.0, 1.0, 0.0)),  # the axis stays
            (rotate(q, (1.0, 0.0, 0.0)), (-1.0, 0.0, 0.0)),
            (rotate(q, (0.0, 0.0, 1.0)), (0.0, 0.0, -1.0)),
        ):
            for a, b in zip(got, want):
                self.assertAlmostEqual(a, b)

    def test_vector_and_quaternion_turns_agree(self) -> None:
        q = half_turn_quat(0.0, 0.0, 0.0, 1.0)
        v = (0.3, 0.7, -0.2)
        for a, b in zip(rotate(q, v), half_turn_vec(*v)):
            self.assertAlmostEqual(a, b)

    def test_old_z_turn_still_computes(self) -> None:
        # The generic formula with the z axis gives the earlier z result.
        self.assertEqual(half_turn_quat(0.0, 0.0, 0.0, 1.0, (0.0, 0.0, 1.0)), (0.0, 0.0, 1.0, -0.0))

    def test_half_turn_is_applied_after_the_old_rotation(self) -> None:
        tilt = (math.sin(0.2), 0.0, 0.0, math.cos(0.2))
        turned = half_turn_quat(*tilt)
        v = (0.3, 0.7, 0.2)
        want = rotate(half_turn_quat(0.0, 0.0, 0.0, 1.0), rotate(tilt, v))
        for a, b in zip(rotate(turned, v), want):
            self.assertAlmostEqual(a, b)

    def test_root_turns_child_stays(self) -> None:
        model = fake_model()
        counts = flip_model(model)
        self.assertEqual(counts, {"roots": 1, "rotation_keys": 2, "location_keys": 1})
        root, child = model.bones
        self.assertEqual(xyzw(root.rotation.initValue), {"x": 0.0, "y": 1.0, "z": 0.0, "w": -0.0})
        self.assertEqual(xyzw(root.location.initValue), {"x": -0.5, "y": 0.25, "z": 13.0})
        self.assertEqual(xyzw(root.location.nullValue), {"x": -0.5, "y": 0.25, "z": 13.0})
        # Negative case: the child bone is not touched.
        self.assertEqual(xyzw(child.rotation.initValue), {"x": 0.1, "y": 0.0, "z": 0.0, "w": 0.995})
        self.assertEqual(xyzw(child.location.initValue), {"x": 0.0, "y": 0.0, "z": 0.0})
        stc = model.sequenceTransformationCollections[0]
        self.assertEqual(xyzw(stc.sd3v[0].keys[0]), {"x": -1.0, "y": 2.0, "z": -3.0})

    def test_two_flips_restore_the_model(self) -> None:
        model = fake_model()
        flip_model(model)
        flip_model(model)
        root = model.bones[0]
        # A quaternion and its negation are the same rotation.
        q = xyzw(root.rotation.initValue)
        self.assertAlmostEqual(abs(q["w"]), 1.0)
        self.assertEqual(xyzw(root.location.initValue), {"x": 0.5, "y": 0.25, "z": -13.0})

    def test_unkeyed_root_turns(self) -> None:
        counts = flip_model(fake_model(root_keys=False))
        self.assertEqual(counts, {"roots": 1, "rotation_keys": 0, "location_keys": 0})

    def test_wrong_block_kind_fails(self) -> None:
        model = fake_model()
        model.sequenceTransformationCollections[0].animRefs[0] = (SD3V_KIND << 16) | 0
        with self.assertRaises(ValueError):
            flip_model(model)

    def test_no_root_fails(self) -> None:
        model = fake_model()
        model.bones[0].parent = 1
        with self.assertRaises(ValueError):
            flip_model(model)


class BuiltSkyTest(unittest.TestCase):
    @unittest.skipUnless(MAP.is_dir(), "built map is absent")
    def test_built_sky_root_is_half_turned(self) -> None:
        import sys

        sys.path.insert(0, str(project_root() / "scripts" / "vendor" / "m3addon"))
        import m3

        for _entry, target in FLIPS:
            model = m3.loadModel(str(MAP / target))
            roots = [b for b in model.bones if b.parent == -1]
            self.assertEqual(len(roots), 1)
            q = roots[0].rotation.initValue
            self.assertAlmostEqual(abs(float(q.y)), 1.0, places=5)
            self.assertAlmostEqual(float(q.z), 0.0, places=5)
            self.assertAlmostEqual(float(q.w), 0.0, places=5)
            # Negative case: the dome bone keeps its stock tilt about x.
            child = [b for b in model.bones if b.parent == 0][0].rotation.initValue
            self.assertAlmostEqual(float(child.x), 0.10765177756547928, places=6)
            self.assertAlmostEqual(float(child.z), 0.0, places=6)


if __name__ == "__main__":
    unittest.main()
