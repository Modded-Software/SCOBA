"""Host tests for scripts/mapgen/waterfeatures (REQ-WATER-FEATURES)."""

from __future__ import annotations
import math
import unittest
from unittest import mock
import numpy as np
from flora.terrain import bilinear
from mapgen.waterfeatures import carve, compose, config, ground, models as models_mod, plan as planner, sites as site_finder
from mapgen.waterfeatures.sites import Mouth
from testkit.tests.water.water_fixtures import (
    MODELS,
    UNIT_AT,
    RECTS,
    hills,
    unit_xml,
    mouths_of,
    planned,
    cylinder,
)


class MeasureTest(unittest.TestCase):
    def test_tube_mouth_is_the_outer_end(self) -> None:
        from mapgen.waterfeatures import measure

        # From near the model origin outward and slightly down, like a drain pipe.
        found = measure.tube(cylinder((-1.0, -3.0, 1.0), (-3.0, -7.0, 0.7), 0.3))
        self.assertIsNotNone(found)
        self.assertAlmostEqual(found["mouth"][0], -3.0, delta=0.05)
        self.assertAlmostEqual(found["mouth"][1], -7.0, delta=0.05)
        self.assertAlmostEqual(found["lip_z"], 0.7 - 0.3, delta=0.06)  # lowest point of the opening
        self.assertAlmostEqual(found["top_z"], 0.7 + 0.3, delta=0.06)
        self.assertAlmostEqual(found["radius"], 0.3, delta=0.05)
        self.assertLess(found["dir"][0], 0.0)  # outward: away from the origin
        self.assertLess(found["dir"][1], 0.0)
        self.assertAlmostEqual(math.hypot(*found["dir"]), 1.0, places=3)

    def test_other_shapes_are_no_tubes(self) -> None:  # negative cases
        from mapgen.waterfeatures import measure

        self.assertIsNone(measure.tube(cylinder((0.0, 0.0, 0.0), (0.0, 0.0, 6.0), 0.3)))  # a mast: upright
        self.assertIsNone(measure.tube(cylinder((0.0, 0.0, 1.0), (2.0, 0.0, 1.0), 0.3)))  # a stub: short
        self.assertIsNone(measure.tube(cylinder((0.0, 0.0, 1.0), (6.0, 0.0, 1.0), 1.5)))  # a hull: fat

    def test_parts_split_unconnected_meshes(self) -> None:
        from mapgen.waterfeatures import measure

        a = [((0, 0, 0), (1, 0, 0), (0, 1, 0)), ((1, 0, 0), (1, 1, 0), (0, 1, 0))]  # two triangles sharing an edge
        b = [((5, 5, 5), (6, 5, 5), (5, 6, 5))]
        found = measure.parts(np.array(a + b, dtype=float))
        self.assertEqual(sorted(len(p) for p in found), [3, 4])

    def test_committed_data_has_what_the_build_needs(self) -> None:
        self.assertEqual(sorted(MODELS.falls), [config.FALL_TYPE])  # negative: no rock waterfall is measured any more
        self.assertGreater(MODELS.falls[config.FALL_TYPE][0].height, 4.0)
        # Rocks for the pools: the plain Zerus rock, every variation, about 2 wide, part of it under its origin.
        self.assertEqual(sorted(MODELS.rocks), [config.ROCK_TYPE])
        self.assertEqual(sorted(MODELS.rocks[config.ROCK_TYPE]), list(range(8)))
        for shape in MODELS.rocks[config.ROCK_TYPE].values():
            self.assertTrue(0.8 < shape.radius < 1.4)
            self.assertLess(shape.lo[2], -0.5)
            self.assertGreater(shape.hi[2], 0.8)
        for unit in config.PIPE_UNITS.values():
            self.assertGreaterEqual(len(MODELS.pipes[unit].tubes), 1)


class SitesTest(unittest.TestCase):
    def test_mouths_scaled_and_placed(self) -> None:
        vz = hills()
        found = mouths_of(vz)
        self.assertEqual(len(found), 4)  # two tubes per side of the model
        tube = MODELS.pipes["PsiDecimator"].tubes[0]
        scale = MODELS.pipes["PsiDecimator"].model_scale * 2.0
        self.assertAlmostEqual(found[0].x, UNIT_AT[0] + tube.mouth[0] * scale, places=3)
        self.assertAlmostEqual(found[0].y, UNIT_AT[1] + tube.mouth[1] * scale, places=3)
        self.assertAlmostEqual(found[0].lip_z, bilinear(vz, *UNIT_AT) + tube.lip_z * scale, places=3)
        self.assertAlmostEqual(found[0].radius, tube.radius * scale, places=3)
        self.assertAlmostEqual(math.hypot(found[0].dx, found[0].dy), 1.0, places=3)

    def test_pending_scale_and_rotation(self) -> None:
        vz = hills()
        done = mouths_of(vz, unit_xml(scale="2,2,2"), pending={})  # already scaled: same mouths
        self.assertAlmostEqual(done[0].x, mouths_of(vz)[0].x, places=3)
        turned = mouths_of(vz, unit_xml(rotation=f' Rotation="{math.pi:.6f}"'))
        self.assertAlmostEqual(turned[0].x - UNIT_AT[0], -(mouths_of(vz)[0].x - UNIT_AT[0]), places=2)
        self.assertAlmostEqual(turned[0].dx, -mouths_of(vz)[0].dx, places=3)

    def test_other_units_have_no_pipes(self) -> None:  # negative case
        self.assertEqual(mouths_of(hills(), unit_xml(kind="SensorTower")), [])

    def test_sites_need_site_water_and_a_mouth(self) -> None:
        found = site_finder.find(RECTS, mouths_of(hills()))
        self.assertEqual([s.rect for s in found], [RECTS[0][1], RECTS[1][1]])
        for site in found:
            self.assertEqual(len(site.mouths), 2)
        # Negative cases: other water under a mouth, and site water far from every mouth.
        moved = [("BelShir", RECTS[0][1]), RECTS[3]]
        self.assertEqual(site_finder.find(moved, mouths_of(hills())), [])

    def test_level_is_drop_below_lowest_lip(self) -> None:
        found = site_finder.find(RECTS, mouths_of(hills()))
        low = min(m.lip_z for s in found for m in s.mouths)
        self.assertEqual(site_finder.levels(found), {"Albion": low - config.DROP})


class CarveTest(unittest.TestCase):
    RECT = (10.0, 10.0, 30.0, 26.0)

    def test_basin_only_lowers_and_stays_inside(self) -> None:
        vz = np.full((40, 40), 10.0)
        vz[15, 15] = 2.0  # already deeper: kept
        out = carve.basin(vz, self.RECT, [(15.0, 15.0), (29.5, 18.0)], 8.0)
        self.assertTrue((out <= vz).all())
        self.assertEqual(out[15, 15], 2.0)
        self.assertAlmostEqual(out[15, 16], 8.0 - config.BASIN_DEPTH * (1 - (1 / config.BASIN_RADIUS) ** 2))
        self.assertEqual(out[18, 30], 10.0)  # negative: the rectangle's edge is not dug
        self.assertEqual(out[18, 31], 10.0)  # nor the ground outside
        self.assertLess(out[18, 29], 8.0)

    def test_pool_is_connected_inside_and_near(self) -> None:
        vz = np.full((40, 40), 10.0)
        vz[14:19, 14:19] = 5.0  # the pool
        vz[14:19, 22:25] = 5.0  # a puddle: wet, not connected
        vz[10, 14:19] = 5.0  # wet on the rectangle's edge
        wet = carve.pool(vz, self.RECT, [(16.0, 16.0)], 8.0)
        self.assertEqual(int(wet.sum()), 25)
        self.assertTrue(wet[14:19, 14:19].all())
        self.assertFalse(wet[14:19, 22:25].any())  # negative: the puddle is no pool
        self.assertFalse(wet[10].any())  # negative: nothing on the edge
        out = carve.rim(vz, self.RECT, wet, 8.0)
        self.assertTrue((out[14:19, 22:25] == 8.0 + config.RIM).all())  # the puddle is filled
        self.assertTrue((out[10, 14:19] == 8.0 + config.RIM).all())
        self.assertTrue((out[14:19, 14:19] == 5.0).all())  # the pool is kept
        self.assertEqual(out[35, 35], 10.0)

    def test_rim_fills_low_ground_close_outside(self) -> None:
        vz = np.full((40, 40), 10.0)
        vz[27:29, 12:20] = 3.0  # a dry pit just outside the rectangle
        vz[36, 12:20] = 3.0  # far outside: not this step's ground
        out = carve.rim(vz, self.RECT, np.zeros(vz.shape, dtype=bool), 8.0)
        self.assertTrue((out[27:29, 12:20] == 8.0 + config.RIM).all())
        self.assertTrue((out[36, 12:20] == 3.0).all())  # negative case

    def test_mouth_is_freed(self) -> None:
        vz = np.full((40, 40), 12.0)
        mouth = Mouth(20.0, 20.0, 9.0, 13.0, 1.0, 0.0, 2.0, 12.0)
        out = carve.free_mouths(vz, (mouth,))
        self.assertAlmostEqual(out[20, 20], 9.0 - config.PIPE_CLEAR)
        self.assertAlmostEqual(out[21, 19], 9.0 - config.PIPE_CLEAR)
        self.assertEqual(out[20, 10], 12.0)  # negative: far back along the pipe the hill stays
        self.assertEqual(out[30, 20], 12.0)

    def test_feather_fades_and_keeps(self) -> None:
        old = np.full((40, 40), 10.0)
        new = old.copy()
        new[20, 20] = 6.0  # a cut
        new[20, 30] = 13.0  # a raise
        keep = np.zeros(old.shape, dtype=bool)
        keep[20, 21] = True
        out = carve.feather(old, new, keep)
        self.assertEqual(out[20, 20], 6.0)
        self.assertEqual(out[20, 21], 10.0)  # kept vertex untouched
        self.assertAlmostEqual(out[20, 19], 10.0 - 4.0 * config.BLEND_KEEP_CUT)
        self.assertAlmostEqual(out[20, 18], 10.0 - 4.0 * config.BLEND_KEEP_CUT**2)
        self.assertAlmostEqual(out[20, 31], 10.0 + 3.0 * config.BLEND_KEEP)
        self.assertEqual(out[5, 5], 10.0)  # negative: far ground does not move
        self.assertEqual(out[20, 20 - config.BLEND_PASSES - 1], 10.0)


class PlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.old, cls.plan = planned()

    def test_no_problems(self) -> None:
        self.assertEqual(planner.problems(self.old, self.plan, MODELS), [])
        self.assertEqual(len(self.plan.sites), 2)

    def test_deterministic(self) -> None:  # same input, same plan
        _old, again = planned()
        self.assertEqual(again.placements, self.plan.placements)
        self.assertEqual(again.rocks, self.plan.rocks)
        self.assertTrue(np.array_equal(again.ground, self.plan.ground))

    def test_rocks_stand_in_the_pools(self) -> None:  # operator 2026-11-20: "some rocks inside"
        for i, site in enumerate(self.plan.sites):
            level = self.plan.levels[site.water]
            rocks = [r for r in self.plan.rocks if r.site == i]
            self.assertGreaterEqual(len(rocks), 1)
            self.assertLessEqual(len(rocks), config.ROCK_COUNT)
            self.assertEqual(len({r.variation for r in rocks}), len(rocks))  # no two alike in a pool
            landings = [compose.landing(MODELS, p) for p in self.plan.placements if p.site == i]
            for k, r in enumerate(rocks):
                self.assertEqual(r.kind, config.ROCK_TYPE)
                shape = MODELS.rocks[r.kind][r.variation]
                self.assertTrue(self.plan.pools[i][int(round(r.y)), int(round(r.x))])  # in the pool
                floor = bilinear(self.plan.ground, r.x, r.y)
                self.assertGreaterEqual(level - floor, config.ROCK_MIN_DEPTH)  # in water
                self.assertGreaterEqual(r.z, floor - 1e-9)
                self.assertLess(r.z + shape.lo[2] * r.scale, floor)  # negative: it does not float, its underside is in the floor
                self.assertGreaterEqual(r.z + shape.hi[2] * r.scale, level + config.ROCK_ABOVE[0] - 1e-9)  # negative: not drowned
                self.assertTrue(config.ROCK_SCALE[0] <= r.scale <= config.ROCK_SCALE[1])
                for q in landings:
                    self.assertGreaterEqual(math.dist((r.x, r.y), q), config.ROCK_FALL_CLEAR)  # negative: not under a fall
                for other in rocks[k + 1 :]:
                    self.assertGreaterEqual(math.dist((r.x, r.y), (other.x, other.y)), config.ROCK_SPACING)

    def test_rocks_do_not_change_the_falls(self) -> None:  # negative: the rocks have their own chance
        bare = planner.make(self.old, self.plan.sites, MODELS._replace(rocks={}))
        self.assertEqual(bare.placements, self.plan.placements)
        self.assertEqual(bare.rocks, ())
        self.assertEqual(planner.problems(self.old, bare, MODELS._replace(rocks={})), [])

    def test_falls_hang_from_the_lip_onto_the_water(self) -> None:
        falls = self.plan.placements
        self.assertGreaterEqual(len(falls), 4)  # every mouth has one
        for p in falls:
            self.assertEqual(p.kind, config.FALL_TYPE)  # negative: no rock waterfall is placed (operator 2026-11-20)
            site = self.plan.sites[p.site]
            level = self.plan.levels[site.water]
            mouth = site.mouths[p.mouth]
            # The top is just over the lip: not under it, not in the upper half of the opening
            # (operator 2026-11-20: "does not flow from the bottom of the pipe but the top").
            top = compose.top_z(MODELS, p)
            self.assertGreater(top, mouth.lip_z)
            self.assertLess(top, mouth.lip_z + mouth.radius)
            # No fall reaches past the side of its pipe.
            self.assertLessEqual(compose.side_reach(MODELS, p, site), mouth.radius + config.SIDE_TOLERANCE)
            # The whole fall is FALL_RAISE up (operator 2026-11-20): its water line is over the pool, not on it.
            self.assertAlmostEqual(compose.surface_z(MODELS, p), level + config.FALL_RAISE, places=6)
            q = compose.landing(MODELS, p)
            self.assertGreaterEqual(level - bilinear(self.plan.ground, *q), config.WET_MIN)
            # Just outside the mouth, along the pipe: not behind it, not far away.
            # Measured from where the water leaves: the mouth, moved by the site's shift.
            leaves = (mouth.x + site.shift[0], mouth.y + site.shift[1])
            ahead = (q[0] - leaves[0]) * mouth.dx + (q[1] - leaves[1]) * mouth.dy
            self.assertGreater(ahead, 0.0)
            self.assertLess(math.dist(q, leaves), mouth.radius + 2.0)
            self.assertGreaterEqual(p.scale, config.FALL_SCALE[0])
            self.assertLessEqual(p.scale, config.FALL_SCALE[1])
        mouths_fed = {(p.site, p.mouth) for p in falls}
        self.assertEqual(len(mouths_fed), sum(len(s.mouths) for s in self.plan.sites))

    def test_feature_is_shifted_toward_the_bigger_pipe(self) -> None:  # operator 2026-11-20
        for i, site in enumerate(self.plan.sites):
            small = min(site.mouths, key=lambda m: m.radius)
            big = max(site.mouths, key=lambda m: m.radius)
            self.assertAlmostEqual(math.hypot(*site.shift), config.SITE_SHIFT)
            along = (big.x - small.x) * site.shift[0] + (big.y - small.y) * site.shift[1]
            self.assertGreater(along, 0.0)  # toward the big pipe, not away from it
            # The falls of each mouth are centred on the shifted point, not on the measured mouth.
            for m_index, mouth in enumerate(site.mouths):
                points = [compose.landing(MODELS, p) for p in self.plan.placements if p.site == i and p.mouth == m_index]
                mid = (sum(q[0] for q in points) / len(points), sum(q[1] for q in points) / len(points))
                moved = (mouth.x + site.shift[0], mouth.y + site.shift[1])
                self.assertLess(math.dist(mid, moved), math.dist(mid, mouth.at))

    def test_falls_face_the_mean_direction_of_the_pipes(self) -> None:  # operator 2026-11-20: "need a southwest facing"
        common = compose.common_facing(self.plan.sites)
        want = models_mod.rotation_facing(common)
        own = []
        for p in self.plan.placements:
            off = (p.rotation - want + math.pi) % math.tau - math.pi
            self.assertLessEqual(abs(off), config.FALL_TURN_JITTER + 1e-9)  # every group faces the same way
            mouth = self.plan.sites[p.site].mouths[p.mouth]
            pipe = (p.rotation - models_mod.rotation_facing(mouth.out) + math.pi) % math.tau - math.pi
            own.append(abs(pipe))
        self.assertGreater(max(own), config.FALL_TURN_JITTER)  # negative: not along their own pipes any more
        # The model's front (-y) points along the common direction.
        front = models_mod.turned((0.0, -1.0), want)
        self.assertAlmostEqual(front[0], common[0], places=6)
        self.assertAlmostEqual(front[1], common[1], places=6)
        # The turn moves no water: the falls land where they did when they faced their pipes.
        with mock.patch.object(config, "FALL_FACE_COMMON", 0.0):
            _old, along = planned()
        self.assertEqual(len(along.placements), len(self.plan.placements))
        for a, b in zip(along.placements, self.plan.placements):
            qa, qb = compose.landing(MODELS, a), compose.landing(MODELS, b)
            self.assertLess(math.dist(qa, qb), 1e-6)
            mouth = along.sites[a.site].mouths[a.mouth]
            pipe = (a.rotation - models_mod.rotation_facing(mouth.out) + math.pi) % math.tau - math.pi
            self.assertLessEqual(abs(pipe), config.FALL_TURN_JITTER + 1e-9)  # negative: share 0 keeps the pipe's direction

    def test_fall_facing_turns_by_the_share(self) -> None:
        mouth = self.plan.sites[0].mouths[0]
        self.assertEqual(compose.fall_facing(mouth, None), mouth.out)
        common = compose.common_facing(self.plan.sites)
        full = compose.fall_facing(mouth, common)
        self.assertAlmostEqual(full[0], common[0], places=6)
        self.assertAlmostEqual(full[1], common[1], places=6)
        with mock.patch.object(config, "FALL_FACE_COMMON", 0.5):
            half = compose.fall_facing(mouth, common)
        between = math.atan2(half[1], half[0])
        ends = sorted((math.atan2(mouth.dy, mouth.dx), math.atan2(common[1], common[0])))
        self.assertTrue(ends[0] < between < ends[1])

    def test_dense_and_varied(self) -> None:  # operator 2026-11-20: density, then "more variation in their scale"
        for i, site in enumerate(self.plan.sites):
            mine = [p for p in self.plan.placements if p.site == i]
            for m_index, mouth in enumerate(site.mouths):
                falls = [p for p in mine if p.mouth == m_index]
                self.assertGreaterEqual(len(falls), 2)
                self.assertEqual(len({(round(p.scale, 3), round(p.flat, 3)) for p in falls}), len(falls))  # no two copies
                # Together they are as wide as the opening: not a thin thread.
                self.assertGreaterEqual(sum(MODELS.falls[p.kind][0].width * p.flat for p in falls), 2 * mouth.radius)
                # Width and height scales stay inside their jitter.
                for p in falls:
                    share = MODELS.falls[p.kind][0].width * p.flat / (2 * mouth.radius)
                    self.assertLessEqual(abs(share - config.FALL_WIDTH), config.FALL_WIDTH * config.FALL_WIDTH_JITTER + 1e-9)
        # Over the map the widths differ by more than the first jitter of 8 % allowed.
        shares = [MODELS.falls[p.kind][0].width * p.flat / (2 * self.plan.sites[p.site].mouths[p.mouth].radius) for p in self.plan.placements]
        self.assertGreater((max(shares) - min(shares)) / config.FALL_WIDTH, 0.16)

    def test_bigger_pipe_has_the_bigger_fall(self) -> None:  # operator 2026-11-20
        for i, site in enumerate(self.plan.sites):
            small = min(range(len(site.mouths)), key=lambda k: site.mouths[k].radius)
            big = max(range(len(site.mouths)), key=lambda k: site.mouths[k].radius)
            width = {k: [p.flat for p in self.plan.placements if p.site == i and p.mouth == k] for k in (small, big)}
            self.assertGreater(min(width[big]), max(width[small]))

    def test_no_overlap(self) -> None:
        for i in range(len(self.plan.sites)):
            mine = [p for p in self.plan.placements if p.site == i]
            for a_index, a in enumerate(mine):
                for b in mine[a_index + 1 :]:
                    share = models_mod.overlap_share(compose.outline(MODELS, a), compose.outline(MODELS, b))
                    self.assertLessEqual(share, config.FALL_OVERLAP_LIMIT)

    def test_water_ends_on_a_shore(self) -> None:
        vz = self.plan.ground
        for i, site in enumerate(self.plan.sites):
            level = self.plan.levels[site.water]
            x0, y0, x1, y1 = (int(v) for v in site.rect)
            edge = np.concatenate([vz[y0, x0 : x1 + 1], vz[y1, x0 : x1 + 1], vz[y0 : y1 + 1, x0], vz[y0 : y1 + 1, x1]])
            self.assertGreaterEqual(edge.min(), level + config.RIM - 1e-9)  # no water at the rectangle's edge
            wet = vz[y0 : y1 + 1, x0 : x1 + 1] < level
            self.assertTrue((wet == self.plan.pools[i][y0 : y1 + 1, x0 : x1 + 1]).all())  # all water is the pool
            self.assertGreater(int(self.plan.pools[i].sum()), 20)

    def test_ground_clear_of_pipe_mouths(self) -> None:
        for site in self.plan.sites:
            for mouth in site.mouths:
                under = self.plan.ground[carve.mouth_mask(self.plan.ground.shape, mouth)]
                self.assertLessEqual(under.max(), mouth.lip_z - config.PIPE_CLEAR + 1e-9)

    def test_change_is_local_and_bounded(self) -> None:
        delta = np.abs(self.plan.ground - self.old)
        self.assertLessEqual(delta.max(), config.MAX_CHANGE)
        self.assertGreater(delta.max(), 1.0)  # the ground was shaped
        far = np.ones(delta.shape, dtype=bool)
        for site in self.plan.sites:
            far &= ~carve.inside(delta.shape, site.rect, config.SHORE_MARGIN + config.BLEND_PASSES + 2)
        self.assertEqual(delta[far].max(), 0.0)  # negative: the rest of the map is untouched


if __name__ == "__main__":
    unittest.main()
