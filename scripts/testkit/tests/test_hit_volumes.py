"""Host tests of the TPS pick hit volumes (R-TPS-84): reference ray tests,
model frame, Galaxy generator, committed files, and the in-game aim points."""

from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from hitvolumes import galaxy, ray
from hitvolumes.resolve import vec3
from hitvolumes.units import CREATE_RE

AXES = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
EAST = (1.0, 0.0, 0.0)


class SphereTests(unittest.TestCase):
    def test_entry_distance(self) -> None:
        self.assertAlmostEqual(ray.sphere((0, 0, 0), EAST, (5, 0, 0), 1.0), 4.0)

    def test_grazing_offset(self) -> None:
        t = ray.sphere((0, 0, 0), EAST, (5, 0.6, 0), 1.0)
        self.assertAlmostEqual(t, 5.0 - 0.8)

    def test_inside_is_zero(self) -> None:
        self.assertEqual(ray.sphere((5, 0, 0), EAST, (5, 0, 0), 1.0), 0.0)

    def test_misses(self) -> None:
        # Negative cases: beside, and behind the origin.
        self.assertIsNone(ray.sphere((0, 0, 0), EAST, (5, 1.01, 0), 1.0))
        self.assertIsNone(ray.sphere((0, 0, 0), EAST, (-5, 0, 0), 1.0))


class CapsuleTests(unittest.TestCase):
    A, B = (5.0, 0.0, -1.0), (5.0, 0.0, 1.0)

    def test_side_entry(self) -> None:
        self.assertAlmostEqual(ray.capsule((0, 0, 0.5), EAST, self.A, self.B, 0.5), 4.5)

    def test_cap_entry_above_segment(self) -> None:
        # Past the top end: the end sphere at B decides.
        t = ray.capsule((0, 0, 1.3), EAST, self.A, self.B, 0.5)
        self.assertAlmostEqual(t, 5.0 - math.sqrt(0.25 - 0.09))

    def test_along_axis(self) -> None:
        down = (0.0, 0.0, -1.0)
        self.assertAlmostEqual(ray.capsule((5, 0, 4), down, self.A, self.B, 0.5), 2.5)

    def test_inside_is_zero(self) -> None:
        self.assertEqual(ray.capsule((5, 0.2, 0), EAST, self.A, self.B, 0.5), 0.0)

    def test_misses(self) -> None:
        self.assertIsNone(ray.capsule((0, 0, 1.6), EAST, self.A, self.B, 0.5))
        self.assertIsNone(ray.capsule((0, 0.6, 0), EAST, self.A, self.B, 0.5))
        self.assertIsNone(ray.capsule((10, 0, 0), EAST, self.A, self.B, 0.5))


class BoxTests(unittest.TestCase):
    def test_entry_distance(self) -> None:
        self.assertAlmostEqual(ray.box((0, 0, 0), EAST, (5, 0, 0), AXES, (1, 1, 1)), 4.0)

    def test_turned_box(self) -> None:
        s = math.sqrt(0.5)
        axes = [(s, s, 0.0), (-s, s, 0.0), (0.0, 0.0, 1.0)]
        # A cube turned 45 degrees: its corner points at the origin.
        self.assertAlmostEqual(ray.box((0, 0, 0), EAST, (5, 0, 0), axes, (1, 1, 1)), 5.0 - math.sqrt(2.0))

    def test_inside_is_zero(self) -> None:
        self.assertEqual(ray.box((5, 0, 0), EAST, (5, 0, 0), AXES, (1, 1, 1)), 0.0)

    def test_misses(self) -> None:
        self.assertIsNone(ray.box((0, 1.5, 0), EAST, (5, 0, 0), AXES, (1, 1, 1)))
        self.assertIsNone(ray.box((0, 0, 0), (-1.0, 0.0, 0.0), (5, 0, 0), AXES, (1, 1, 1)))


class FrameTests(unittest.TestCase):
    def test_model_minus_y_is_facing(self) -> None:
        for facing in (0.0, 90.0, 200.0):
            w = ray.to_world((0.0, -1.0, 0.0), facing)
            self.assertAlmostEqual(w[0], math.cos(math.radians(facing)))
            self.assertAlmostEqual(w[1], math.sin(math.radians(facing)))

    def test_round_trip(self) -> None:
        v = (1.5, -2.0, 0.7)
        back = ray.to_model(ray.to_world(v, 37.0), 37.0)
        for a, b in zip(v, back):
            self.assertAlmostEqual(a, b)

    def test_unit_hit_turns_with_facing(self) -> None:
        shapes = [{"k": "sphere", "c": [0.0, -3.0, 0.0], "r": 0.5}]
        # Facing east, the sphere is 3 east of the unit.
        self.assertIsNotNone(ray.unit_hit(shapes, (10, 0, 0), 0.0, (0, 0, 0), EAST))
        # Facing north, it is 3 north: the eastward ray misses it.
        self.assertIsNone(ray.unit_hit(shapes, (10, 0, 0), 90.0, (0, 0, 0), EAST))


class ScaleTests(unittest.TestCase):
    def test_vec3(self) -> None:
        self.assertEqual(vec3(None), (1.0, 1.0, 1.0))
        self.assertEqual(vec3("3"), (3.0, 3.0, 3.0))
        self.assertEqual(vec3("1,2,3"), (1.0, 2.0, 3.0))
        with self.assertRaises(ValueError):
            vec3("1,2")

    def test_committed_scale_is_actor_times_model(self) -> None:
        # Actor x model scale: Ultralisk 2.0 x 0.85 = 1.7, Hive 3 x 3 = 9 (from the data; not measured in game).
        units = galaxy.load_json()["units"]
        for name in ("Ultralisk", "Hive", "Marine"):
            rec = units[name]
            for s, a, m in zip(rec["scale"], rec["actorScale"], rec["modelScale"]):
                self.assertAlmostEqual(s, a * m, places=4)
        self.assertAlmostEqual(units["Hive"]["scale"][0], 9.0)


class UnitsTests(unittest.TestCase):
    def test_create_calls(self) -> None:
        self.assertEqual(CREATE_RE.findall('gf_DbgTpsPick("s", "Marine", 5.0, 1.4, 5.0);'), ["Marine"])
        # Negative case: a tag argument is not a unit type.
        self.assertEqual(CREATE_RE.findall('gf_DbgTpsPickAt(lp_section, "tbase", lv_unit, 0.0);'), [])


def fake(units: int, shapes: int) -> dict:
    sphere = {"k": "sphere", "c": [0.0, 0.0, 1.0], "r": 0.5}
    return {"units": {f"U{i:03d}": {"reach": 0.5 + i, "shapes": [sphere] * shapes} for i in range(units)}}


class GalaxyTests(unittest.TestCase):
    def test_num(self) -> None:
        self.assertEqual(galaxy.num(-0.00001), "0.0000")
        self.assertEqual(galaxy.num(1.23456), "1.2346")
        self.assertEqual(galaxy.num(-2.0), "-2.0000")

    def test_capsule_record(self) -> None:
        line = galaxy.shape_call({"k": "capsule", "a": [0, 0, 0], "b": [0, 0, 2], "r": 0.5})
        self.assertEqual(line, "    gf_HvCapsule(0.0000, 0.0000, 0.0000, 0.0000, 0.0000, 1.0000, 2.0000, 0.5000);")
        # A capsule without length is its end sphere.
        self.assertIn("gf_HvSphere(", galaxy.shape_call({"k": "capsule", "a": [1, 0, 0], "b": [1, 0, 0], "r": 0.5}))

    def test_chunks_stay_under_the_line_cap(self) -> None:
        files = galaxy.render(fake(60, 12), far=20.0)
        chunks = [n for n in files if n not in (galaxy.SIZE, galaxy.LOAD)]
        self.assertGreater(len(chunks), 1)
        for name in chunks:
            self.assertLess(files[name].count("\n"), 512)
        self.assertEqual(sum(files[n].count("gf_HvSphere(") for n in chunks), 60 * 12)
        for i in range(1, len(chunks) + 1):
            self.assertIn(f"gf_HvLoad{i}();", files[galaxy.LOAD])

    def test_far_types(self) -> None:
        files = galaxy.render(fake(30, 1), far=20.0)
        text = "".join(files.values())
        # Reach 0.5 + i: U020 .. U029 are past 20.
        self.assertIn('gf_HvType("U020", 1.5000, true);', text)
        self.assertIn('gf_HvType("U019", 1.5000, false);', text)
        self.assertIn("const int c_HV_FAR_TYPES = 10;", files[galaxy.SIZE])
        self.assertIn("const fixed c_HV_NEAR_REACH = 19.5000;", files[galaxy.SIZE])

    def test_stale_and_extra_files(self) -> None:
        files = galaxy.render(fake(3, 1), far=20.0)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            galaxy.write(out, files)
            self.assertEqual(galaxy.stale(out, files), [])
            (out / galaxy.SIZE).write_text("changed", encoding="utf-8")
            (out / "hit_volumes_9.galaxy").write_text("", encoding="utf-8")
            problems = galaxy.stale(out, files)
            self.assertTrue(any("differs" in p for p in problems), problems)
            self.assertTrue(any("not generated" in p for p in problems), problems)

    def test_committed_files_match_the_json(self) -> None:
        files = galaxy.render(galaxy.load_json(), galaxy.crosshair_range())
        self.assertEqual(galaxy.stale(galaxy.OUT_DIR, files), [])


# The tpspick.galaxy cases: (type, dx, facing, model point, picks the unit).
IN_GAME = {
    ("tps_pick_medic", "thead"): ("Medic", 6.0, 0.0, (0.0, 0.0, 0.85), True),
    ("tps_pick_medic", "tabove"): ("Medic", 6.0, 0.0, (0.0, 0.0, 1.35), False),
    ("tps_pick_marine", "tthigh"): ("Marine", 6.0, 0.0, (0.0, 0.0, 0.35), True),
    ("tps_pick_marine", "tmid"): ("Marine", 6.0, 0.0, (0.0, 0.0, 0.6), True),
    ("tps_pick_marine", "tside"): ("Marine", 6.0, 0.0, (1.3, 0.0, 0.6), False),
    ("tps_pick_marine", "tside2"): ("Marine", 6.0, 0.0, (-1.1, 0.0, 0.6), False),
    ("tps_pick_ultra", "tfront"): ("Ultralisk", 12.0, 90.0, (1.4, -4.0, 2.1), True),
    ("tps_pick_ultra", "tback"): ("Ultralisk", 12.0, 90.0, (1.4, 4.0, 2.1), False),
    ("tps_pick_far", "tbody"): ("Zergling", 18.5, 0.0, (0.0, 0.0, 0.4), True),
    ("tps_pick_far", "tside"): ("Zergling", 18.5, 0.0, (0.7, 0.0, 0.4), False),
    ("tps_pick_hive", "ttop"): ("Hive", 30.0, 0.0, (0.0, 0.0, 28.0), True),
    ("tps_pick_hive", "tnorth"): ("Hive", 30.0, 0.0, (30.0, 30.0, 1.5), False),
}
# The ray origin is the camera focus (hero, or hero and shoulder proxy centre)
# at the camera height offset; it sits within this of the hero, sideways.
EYE = 0.9
ORIGIN_SPREAD = (-0.8, 0.0, 0.8)


class InGameCaseTests(unittest.TestCase):
    """The in-game aim points hit or miss with margin, from any origin the
    camera focus can take."""

    def setUp(self) -> None:
        self.units = galaxy.load_json()["units"]

    def hit(self, kind: str, dx: float, facing: float, point, oy: float):
        at = (dx, 0.0, 0.0)
        w = ray.to_world(point, facing)
        o = (0.0, oy, EYE)
        return ray.unit_hit(self.units[kind]["shapes"], at, facing, o, ray.aim(o, ray.add_scaled(at, w, 1.0)))

    def test_cases(self) -> None:
        for key, (kind, dx, facing, point, want) in IN_GAME.items():
            for oy in ORIGIN_SPREAD:
                t = self.hit(kind, dx, facing, point, oy)
                self.assertEqual(t is not None and t <= 20.0, want, (key, oy, t))

    def test_flyer_body_and_under(self) -> None:
        # tps_pick_flyer: the Overseer's height is read in game; these hold
        # for any height in the range a flyer takes.
        shapes = self.units["Overseer"]["shapes"]
        # 7.0: measured, tps 20261115-213703.
        for height in (2.5, 3.0, 3.75, 4.5, 7.0):
            at = (8.0, 0.0, height)
            for oy in ORIGIN_SPREAD:
                o = (0.0, oy, EYE)
                body = ray.unit_hit(shapes, at, 0.0, o, ray.aim(o, at))
                under = ray.unit_hit(shapes, at, 0.0, o, ray.aim(o, (8.0, 0.0, height - 2.0)))
                self.assertIsNotNone(body, (height, oy))
                self.assertIsNone(under, (height, oy))

    def test_marine_before_hive(self) -> None:
        marine = self.hit("Marine", 3.0, 0.0, (0.0, 0.0, 0.6), 0.0)
        o = (0.0, 0.0, EYE)
        hive = ray.unit_hit(self.units["Hive"]["shapes"], (30.0, 0.0, 0.0), 0.0, o, ray.aim(o, (3.0, 0.0, 0.6)))
        self.assertIsNotNone(marine)
        self.assertTrue(hive is None or hive > marine + 0.3, (marine, hive))
        # Over the Marine to the Hive top: the Marine is not on that ray.
        self.assertIsNone(ray.unit_hit(self.units["Marine"]["shapes"], (3.0, 0.0, 0.0), 0.0, o, ray.aim(o, (30.0, 0.0, 28.0))))


# Engine screen-centre pitch bands on a ground Zergling (facing 180) east of
# the hero, yaw 0, hero hidden, Tosh, rest camera (pncprobe 20261115-224549).
ENGINE_BANDS = {3.0: (6.9, 19.0), 5.0: (6.0, 9.8), 8.0: (3.9, 6.0), 12.0: (3.0, 3.9)}


class EngineRayTests(unittest.TestCase):
    """The pick ray origin (hero at EYE, no side offset) gives the engine's
    bands; the old origin (shoulder 0.5 aside, 1.5 high) does not."""

    def band(self, dist: float, o) -> tuple[float, float] | None:
        shapes = galaxy.load_json()["units"]["Zergling"]["shapes"]
        hits = []
        for i in range(-300, 301):
            p = i / 10
            a = math.radians(p)
            d = (math.cos(a), 0.0, -math.sin(a))
            if ray.unit_hit(shapes, (dist, 0.0, 0.0), 180.0, o, d) is not None:
                hits.append(p)
        return (min(hits), max(hits)) if hits else None

    def test_new_origin_matches_the_engine(self) -> None:
        for dist, (lo, hi) in ENGINE_BANDS.items():
            got = self.band(dist, (0.0, 0.0, EYE))
            self.assertIsNotNone(got, dist)
            self.assertLessEqual(abs((got[0] + got[1]) / 2 - (lo + hi) / 2), 2.0, (dist, got))

    def test_old_origin_misses(self) -> None:
        for dist in ENGINE_BANDS:
            self.assertIsNone(self.band(dist, (0.0, -0.5, 1.5)), dist)


if __name__ == "__main__":
    unittest.main()
