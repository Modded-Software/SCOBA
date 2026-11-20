"""Pool gardens (flora/pools.py): plants in a ring round every carved pool.

Operator 2026-11-20: "the pools need vegetation around".
"""

from __future__ import annotations

import math
import random
import unittest

import numpy as np

from flora import config, pools
from flora.grid import distance_to
from flora.rules import context
from flora.scatter import scatter
from flora.scene import FINE, Unit
from mapgen.waterfeatures import config as water_config

from testkit.tests.test_flora import N, world


def pooled():
    """The test world with its pond as a carved pool."""
    terrain, scene = world()
    ys, xs = np.mgrid[0:N, 0:N]
    return terrain._replace(pool=np.hypot(xs - 70, ys - 20) < 6), scene


class PoolGardenTest(unittest.TestCase):
    def setUp(self) -> None:
        self.terrain, self.scene = pooled()
        self.ctx = context(self.terrain, self.scene, random.Random(3))
        self.hazards = np.zeros((N, N), bool)
        self.hazards[14:18, 76:80] = True  # beside the pool
        self.plants = pools.garden(self.ctx, self.hazards, 7)

    def test_pool_water_is_the_site_water_of_the_water_features(self) -> None:
        self.assertEqual(config.POOL_WATER, water_config.SITE_WATER)
        self.assertTrue(set(config.POOL_GARDEN) <= set(config.FAMILIES))  # flora families: checks and crush cover them

    def test_plants_stand_in_a_ring_round_the_pool(self) -> None:
        dist = distance_to(self.terrain.pool)
        self.assertGreater(len(self.plants), 30)
        self.assertEqual({p.kind for p in self.plants}, set(config.POOL_GARDEN))  # every family of the garden
        for p in self.plants:
            x, y = int(p.x), int(p.y)
            self.assertLessEqual(dist[y, x], config.POOL_GARDEN_BAND)
            self.assertFalse(self.terrain.pool[y, x], p)  # negative: none in the water
            self.assertLess(self.terrain.slope[y, x], config.POOL_GARDEN_SLOPE)  # negative: none on a wall
            self.assertFalse(self.hazards[y, x], p)
            self.assertFalse(self.scene.tree_block[int(p.y * FINE), int(p.x * FINE)], p)
            family = config.FAMILIES[p.kind]
            self.assertTrue(family.scale[0] <= p.scale <= family.scale[1])
            self.assertLess(p.variation, family.variations)

    def test_ring_is_all_round_the_pool(self) -> None:
        quarters = {(p.x > 70, p.y > 20) for p in self.plants}
        self.assertEqual(len(quarters), 4)

    def test_spacing(self) -> None:
        for i, a in enumerate(self.plants):
            for b in self.plants[i + 1 :]:
                gap = math.hypot(a.x - b.x, a.y - b.y)
                if a.kind == b.kind:
                    self.assertGreaterEqual(gap, config.POOL_GARDEN[a.kind] - 1e-6)
                else:
                    self.assertGreaterEqual(gap, config.MIX_SPACING * (config.POOL_GARDEN[a.kind] + config.POOL_GARDEN[b.kind]) / 2 - 1e-6)

    def test_same_input_same_garden(self) -> None:
        self.assertEqual(self.plants, pools.garden(context(self.terrain, self.scene, random.Random(3)), self.hazards, 7))

    def test_no_pool_no_garden(self) -> None:  # negative case
        terrain, scene = world()
        ctx = context(terrain, scene, random.Random(3))
        self.assertEqual(pools.garden(ctx, self.hazards, 7), [])
        empty = context(terrain._replace(pool=np.zeros((N, N), bool)), scene, random.Random(3))
        self.assertEqual(pools.garden(empty, self.hazards, 7), [])

    def test_base_region_does_not_stop_the_garden_but_units_do(self) -> None:
        # The decimator pools lie in the Terran base region: its keep-out is not the garden's.
        everywhere = self.scene._replace(keepout=np.ones((N, N), bool))
        self.assertEqual(pools.garden(context(self.terrain, everywhere, random.Random(3)), self.hazards, 7), self.plants)
        # Negative: no plant within a unit's keep radius.
        turret = Unit("200", "AutoTurret", "7", 77.0, 20.0)  # on the pool's edge
        self.assertEqual(config.KEEP_STRUCTURE, 6.0)
        guarded = self.scene._replace(units=[*self.scene.units, turret])
        plants = pools.garden(context(self.terrain, guarded, random.Random(3)), self.hazards, 7)
        self.assertTrue(plants)
        self.assertLess(len(plants), len(self.plants))
        for p in plants:
            self.assertGreater(math.hypot(p.x - 77.0, p.y - 20.0), config.KEEP_STRUCTURE - 1.5)
        self.assertTrue(any(math.hypot(p.x - 77.0, p.y - 20.0) < config.KEEP_STRUCTURE - 1.5 for p in self.plants))

    def test_scatter_plants_the_garden_first_and_keeps_clear_of_it(self) -> None:
        plants = scatter(self.ctx, self.hazards, 7)
        self.assertEqual(plants[: len(self.plants)], self.plants)
        rest = plants[len(self.plants) :]
        self.assertTrue(rest)
        for p in rest:
            for g in self.plants:
                if g.kind == p.kind:
                    # A plant of the general rules keeps its family's spacing from the garden's.
                    self.assertGreaterEqual(math.hypot(p.x - g.x, p.y - g.y), config.FAMILIES[p.kind].spacing - 1e-6)
        # Without the pool the same world has no garden: the ring is thinner there.
        terrain, scene = world()
        bare = scatter(context(terrain, scene, random.Random(3)), self.hazards, 7)
        dist = distance_to(self.terrain.pool)

        def near(items: list) -> int:
            return sum(1 for p in items if 0 < dist[int(p.y), int(p.x)] <= config.POOL_GARDEN_BAND)

        self.assertGreater(near(plants), near(bare))


if __name__ == "__main__":
    unittest.main()
