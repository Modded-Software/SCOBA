"""Water features: plan problems, paint and water height (split from test_water_features.py)."""

from __future__ import annotations
import unittest
import numpy as np
from flora.hazard_paint import FULL
from flora.terrain import bilinear
from mapgen.waterfeatures import compose, config, ground, paint, plan as planner
from mapgen.waterfeatures.sites import Site
from testkit.tests.water.water_fixtures import (
    WATER_BASE,
    water_heights,
    MODELS,
    planned,
)


class ProblemsTest(unittest.TestCase):
    """Negative cases: each fault is measured and reported."""

    def setUp(self) -> None:
        self.old, self.plan = planned()

    def found(self, plan: planner.Plan) -> str:
        return "\n".join(planner.problems(self.old, plan, MODELS))

    def swap(self, index: int, **changes) -> planner.Plan:
        placements = list(self.plan.placements)
        placements[index] = placements[index]._replace(**changes)
        return self.plan._replace(placements=placements)

    def test_floating_fall(self) -> None:
        self.assertIn("pipe lip", self.found(self.swap(0, scale=self.plan.placements[0].scale * 1.5)))
        self.assertIn("water at", self.found(self.swap(0, z=self.plan.placements[0].z + 1.0)))
        # Operator 2026-11-20: the fall is FALL_RAISE up. One left on the water is reported.
        self.assertIn("water at", self.found(self.swap(0, z=self.plan.placements[0].z - config.FALL_RAISE)))

    def test_fall_from_the_top_of_the_pipe(self) -> None:  # operator 2026-11-20: "not from the bottom but the top"
        p = self.plan.placements[0]
        mouth = self.plan.sites[p.site].mouths[p.mouth]
        fall = MODELS.falls[p.kind][0]
        level = self.plan.levels["Albion"]
        high = (mouth.lip_z + 0.6 * 2 * mouth.radius - level) / fall.height  # the old rule: 0.6 up the opening
        self.assertIn("top at", self.found(self.swap(0, scale=high, z=level - fall.base_z * high + config.FALL_RAISE)))

    def test_fall_past_the_side_of_its_pipe(self) -> None:  # operator 2026-11-20: "clips outside of the small pipe"
        p = self.plan.placements[0]
        self.assertIn("to the side", self.found(self.swap(0, wide=p.wide * 2.5)))

    def test_small_pipe_with_the_bigger_fall(self) -> None:  # operator 2026-11-20
        site = self.plan.sites[0]
        small = min(range(len(site.mouths)), key=lambda k: site.mouths[k].radius)
        placements = [p._replace(wide=p.wide * 2.0) if p.site == 0 and p.mouth == small else p for p in self.plan.placements]
        self.assertIn("is bigger than", self.found(self.plan._replace(placements=placements)))

    def test_thin_stream_and_copies(self) -> None:  # operator 2026-11-20
        mine = [i for i, p in enumerate(self.plan.placements) if p.site == 0 and p.mouth == 0]
        self.assertGreaterEqual(len(mine), 2)
        one = [p for i, p in enumerate(self.plan.placements) if i not in mine[1:]]
        self.assertIn("thin stream", self.found(self.plan._replace(placements=one)))
        first = self.plan.placements[mine[0]]
        same = self.swap(mine[1], scale=first.scale, wide=first.wide, z=first.z)
        self.assertIn("two falls of one size", self.found(same))

    def test_fall_on_dry_ground(self) -> None:
        q = compose.landing(MODELS, self.plan.placements[0])
        raised = self.plan.ground.copy()
        raised[int(q[1]) - 1 : int(q[1]) + 3, int(q[0]) - 1 : int(q[0]) + 3] = self.plan.levels["Albion"] + 1.0
        self.assertIn("dry ground", self.found(self.plan._replace(ground=raised)))

    def test_fall_outside_the_pool(self) -> None:
        p = self.plan.placements[0]
        self.assertIn("outside the pool", self.found(self.swap(0, x=p.x + 12.0)))

    def test_mouth_without_fall(self) -> None:
        kept = [p for p in self.plan.placements if not (p.site == 0 and p.mouth == 0)]
        self.assertIn("pipe mouth 0 has no fall", self.found(self.plan._replace(placements=kept)))

    def test_ground_in_a_pipe_mouth(self) -> None:
        mouth = self.plan.sites[0].mouths[0]
        raised = self.plan.ground.copy()
        raised[int(round(mouth.y)), int(round(mouth.x))] = mouth.lip_z + 1.0
        self.assertIn("ground reaches pipe mouth", self.found(self.plan._replace(ground=raised)))

    def test_stacked_falls(self) -> None:
        mine = [i for i, p in enumerate(self.plan.placements) if p.site == 0 and p.mouth == 0]
        other = self.plan.placements[mine[0]]
        self.assertIn("overlap", self.found(self.swap(mine[1], x=other.x, y=other.y, rotation=other.rotation)))

    def rock(self, index: int, **changes) -> planner.Plan:
        rocks = list(self.plan.rocks)
        rocks[index] = rocks[index]._replace(**changes)
        return self.plan._replace(rocks=tuple(rocks))

    def test_rock_faults(self) -> None:  # operator 2026-11-20: rocks inside the pools
        r = self.plan.rocks[0]
        shape = MODELS.rocks[r.kind][r.variation]
        self.assertIn("no rock in the pool", self.found(self.plan._replace(rocks=tuple(k for k in self.plan.rocks if k.site != 0))))
        self.assertIn("outside the pool", self.found(self.rock(0, x=r.x + 30.0)))
        self.assertIn("buried or floating", self.found(self.rock(0, z=r.z + 3.0)))
        self.assertIn("buried or floating", self.found(self.rock(0, z=r.z - 1.0)))
        self.assertGreater(shape.hi[2], 0.0)
        self.assertIn("under the water", self.found(self.rock(0, scale=0.05, z=bilinear(self.plan.ground, r.x, r.y))))  # a drowned pebble
        self.assertIn("scale", self.found(self.rock(0, scale=config.ROCK_SCALE[1] * 2)))
        q = compose.landing(MODELS, next(p for p in self.plan.placements if p.site == r.site))
        self.assertIn("from where a fall lands", self.found(self.rock(0, x=q[0], y=q[1])))
        mine = [k for k, other in enumerate(self.plan.rocks) if other.site == r.site]
        if len(mine) > 1:
            other = self.plan.rocks[mine[1]]
            self.assertIn("from the rock at", self.found(self.rock(0, x=other.x + 0.5, y=other.y)))
            self.assertIn("same variation", self.found(self.rock(0, variation=other.variation)))

    def test_water_at_the_rectangle_edge(self) -> None:
        x0, y0, _x1, _y1 = (int(v) for v in self.plan.sites[0].rect)
        low = self.plan.ground.copy()
        low[y0, x0 + 3] = self.plan.levels["Albion"] - 1.0
        self.assertIn("below the rim", self.found(self.plan._replace(ground=low)))

    def test_too_much_ground_moved(self) -> None:
        deep = self.plan.ground.copy()
        deep[5, 5] -= config.MAX_CHANGE + 1.0
        self.assertIn("ground moved", self.found(self.plan._replace(ground=deep)))


class PaintTest(unittest.TestCase):
    """Rock texture on the sloped walls of the pools (operator 2026-11-20)."""

    SITE = Site((10.0, 10.0, 26.0, 26.0), "Albion", ())

    def ground(self) -> np.ndarray:
        vz = np.full((65, 65), 10.0)
        vz[14:23, 14:23] = 4.0  # a pit with upright walls inside the rectangle
        vz[50:60, 50:60] = 4.0  # the same pit far from any pool
        return vz

    def test_walls_are_painted_and_flat_ground_is_not(self) -> None:
        w = paint.vertex_weights(self.ground(), [self.SITE])
        self.assertEqual(w[18, 14], 1.0)  # the wall
        self.assertEqual(w[18, 18], 0.0)  # negative: the flat pool floor
        self.assertEqual(w[12, 12], 0.0)  # negative: the flat shore
        self.assertEqual(w[55, 50], 0.0)  # negative: a wall that is not at a pool

    def test_weight_follows_the_slope(self) -> None:
        low, high = config.WALL_SLOPE
        xs = np.arange(65, dtype=float)
        for rise, want in ((low, 0.0), ((low + high) / 2, 0.5), (high, 1.0), (high * 3, 1.0)):
            vz = np.tile(xs * rise, (65, 1))
            self.assertAlmostEqual(float(paint.vertex_weights(vz, [self.SITE])[18, 18]), want, places=6)

    def test_mask_weights_keep_place_and_range(self) -> None:
        vertex = np.zeros((65, 65))
        vertex[20:25, 40:45] = 1.0  # rows are y, columns are x
        mask = paint.mask_weights(vertex, 256)
        self.assertEqual(mask.shape, (256, 256))
        self.assertEqual(int(mask.max()), FULL)
        self.assertEqual(int(mask[88, 168]), FULL)  # map cell (42, 22), 4 mask cells per map cell
        self.assertEqual(int(mask[168, 88]), 0)  # negative: not mirrored
        self.assertEqual(int(mask[8, 8]), 0)


class WaterHeightTest(unittest.TestCase):
    BASE = WATER_BASE

    def heights(self, text: str) -> dict[str, float]:
        return water_heights(text)

    def test_absent_type_is_added(self) -> None:
        text = ground.set_water_height(self.BASE.format(more=""), "Albion", 8.05)
        self.assertEqual(self.heights(text), {"BelShir": 7.15, "Albion": 8.05})  # BelShir untouched
        self.assertNotIn("\n", text.replace("\r\n", ""))  # CRLF kept

    def test_empty_type_gets_a_state(self) -> None:
        text = ground.set_water_height(self.BASE.format(more='    <CWater id="Albion"/>\r\n'), "Albion", 8.05)
        self.assertEqual(self.heights(text), {"BelShir": 7.15, "Albion": 8.05})

    def test_both_editor_forms_are_replaced(self) -> None:
        text = ground.set_water_height(self.BASE.format(more=""), "BelShir", 6.0)
        self.assertEqual(self.heights(text), {"BelShir": 6.0})
        self.assertIn('Specularity="56.5"', text)
        child = '<Catalog>\n    <CWater id="Albion">\n        <State index="0">\n            <Height value="5.000000"/>\n        </State>\n    </CWater>\n</Catalog>\n'
        self.assertEqual(self.heights(ground.set_water_height(child, "Albion", 8.05)), {"Albion": 8.05})


if __name__ == "__main__":
    unittest.main()
