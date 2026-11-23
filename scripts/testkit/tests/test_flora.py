from __future__ import annotations

import math
import random
import unittest
from unittest import mock

import numpy as np

from flora import config
from flora.build import balance_problems, family_problems, objects_xml, Plan
from flora.grid import disk_cells, distance_to, shortest_path, value_noise
from flora.lanes import Placed, detours, find_lanes, place_hazards, settle
from flora.rules import RULES, context
from flora.scatter import Plant, scatter
from flora.scene import FINE, Region, Scene, Tree, Unit, tree_grid
from flora.terrain import Terrain

N = 96


def world(river: bool = True) -> tuple[Terrain, Scene]:
    """Flat ground, a steep wall along y 80-84, a pond, a river across x + y = N."""
    height = np.full((N, N), 10.0)
    for y in range(80, 85):
        height[y, :] = 10.0 + (y - 79) * 1.2  # slope 1.2 > WALL_SLOPE
    height[85:, :] = 16.0
    ys, xs = np.mgrid[0:N, 0:N]
    level = 9.0
    pond = np.hypot(xs - 70, ys - 20) < 6
    height[pond] = 8.0  # depth 1.0
    if river:
        band = np.abs(xs + ys - N) < 4
        height[band & (height < 12)] = 8.7  # depth 0.3, still pathable
    gy, gx = np.gradient(height)
    slope = np.hypot(gx, gy)
    relief = np.where(slope > 0.8, 6.0, 0.0)
    depth = np.where(height < level, level - height, -np.inf)
    terrain = Terrain(height, slope, np.arctan2(-gy, -gx), relief, np.ones((N, N), bool), depth, level)
    trees = [Tree(str(i), x, y, s, ((x - 1, y - 1), (x - 1, y + 1), (x + 1, y + 1), (x + 1, y - 1)))
             for i, (x, y, s) in enumerate([(20, 40, 6.0), (26, 42, 3.0), (22, 48, 4.5), (60, 60, 6.0)])]
    units = [
        Unit("100", "GreaterNydusWorm", "8", 12.0, 12.0),
        Unit("101", "HybridUltraliskShackled", "7", 72.0, 72.0),
        Unit("102", "SporeCrawler", "8", 30.0, 15.0),
        Unit("103", "Marine", "7", 50.0, 30.0),
    ]
    keepout = np.zeros((N, N), bool)
    keepout[25:35, 45:55] = True  # around the Marine
    regions = {r.name: r for r in (
        Region("Kerrigan Spawn", 15, 15, 4), Region("X Center", 48, 48, 4), Region("Tosh Spawn", 75, 75, 4),
        Region("Dehaka Spawn", 10, 35, 4), Region("X Top", 30, 66, 4), Region("Raynor Spawn", 55, 76, 4),
        Region("Stukov Spawn", 35, 10, 4), Region("X Bottom", 66, 30, 4), Region("Nova Spawn", 85, 55, 4),
    )}
    return terrain, Scene(trees, units, keepout, tree_grid(trees, N), 1000, regions)


class GridTests(unittest.TestCase):
    def test_distance(self) -> None:
        mask = np.zeros((5, 5), bool)
        mask[2, 2] = True
        d = distance_to(mask)
        self.assertEqual(d[2, 2], 0.0)
        self.assertAlmostEqual(d[2, 4], 2.0)
        self.assertAlmostEqual(d[0, 0], 2 * math.sqrt(2))

    def test_path_avoids_blocked_and_fails_when_cut(self) -> None:
        cost = np.ones((10, 10))
        cost[:9, 5] = np.inf
        path = shortest_path(cost, (0, 0), (9, 0))
        self.assertTrue(path)
        self.assertTrue(all(not (x == 5 and y < 9) for x, y in path))
        cost[9, 5] = np.inf
        self.assertEqual(shortest_path(cost, (0, 0), (9, 0)), [])

    def test_noise_is_seeded(self) -> None:
        a = value_noise((32, 32), 8, random.Random(1))
        b = value_noise((32, 32), 8, random.Random(1))
        self.assertTrue((a == b).all())
        self.assertTrue(((a >= 0) & (a < 1)).all())


class RuleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.terrain, self.scene = world()
        self.ctx = context(self.terrain, self.scene, random.Random(3))

    def cells_of(self, kind: str) -> list[tuple[int, int]]:
        return [(int(c.x), int(c.y)) for c in RULES[kind](self.ctx, random.Random(4))]

    def test_wall_vines_only_on_walls(self) -> None:
        for kind in ("ZerusCliffVines", "ZerusCurtain"):
            got = self.cells_of(kind)
            self.assertTrue(got, kind)
            self.assertTrue(all(self.terrain.slope[y, x] > config.WALL_SLOPE for x, y in got), kind)

    def test_water_plants_only_in_water(self) -> None:
        got = self.cells_of("ZerusWaterPlant")
        self.assertTrue(got)
        for x, y in got:
            self.assertGreater(self.terrain.depth[y, x], config.WATER_PLANT_MIN)

    def test_swamp_near_water(self) -> None:
        dist = distance_to(self.terrain.wet)
        got = self.cells_of("ZerusSwampPlants")
        self.assertTrue(got)
        self.assertTrue(all(dist[y, x] <= config.SHORE_BAND for x, y in got))

    def test_ground_rules_stay_dry_flat_and_out_of_keepouts(self) -> None:
        for kind in ("ZerusBrambles", "ZerusGroundVines", "ZerusPlant", "ZerusPlantlife",
                     "ZerusPlantClusterSmall", "ZerusPlantClusterMedium", "ZerusPlantClusterLarge", "ZerusDeadlyPlant"):
            for x, y in self.cells_of(kind):
                self.assertFalse(self.terrain.wet[y, x], kind)
                self.assertLess(self.terrain.slope[y, x], config.FLAT_SLOPE, kind)
                self.assertFalse(self.scene.keepout[y, x], kind)

    def test_tall_grass_fills_water_and_keeps_out(self) -> None:
        cells = self.cells_of("ZerusTallGrassCluster")
        self.assertTrue(any(self.terrain.wet[y, x] for x, y in cells))  # river grass exists
        for x, y in cells:
            self.assertFalse(self.scene.keepout[y, x])
            # Negative case: no grass on a lane route.
            self.assertGreater(self.ctx.to_lane[y, x], config.GRASS_LANE_CLEAR)

    def test_cluster_size_follows_tree_scale(self) -> None:
        def ring_scales(kind: str) -> set[float]:
            """Scales of the trees whose ring each candidate lies on."""
            ring_add = config.TREE_MARGIN + config.FAMILIES[kind].spacing / 2
            out = set()
            for c in RULES[kind](self.ctx, random.Random(4)):
                on = {t.scale for t in self.scene.trees if abs(math.hypot(t.x - c.x, t.y - c.y) - (t.radius + ring_add)) < 1e-6}
                self.assertTrue(on, (kind, c))
                out |= on
            return out

        self.assertEqual(ring_scales("ZerusPlantClusterLarge"), {6.0})
        self.assertEqual(ring_scales("ZerusPlantClusterMedium"), {4.5})
        # Negative case: the scale-3 tree gets small clusters only.
        self.assertEqual(ring_scales("ZerusPlantClusterSmall"), {3.0})

    def test_deadly_only_near_zerg(self) -> None:
        got = self.cells_of("ZerusDeadlyPlant")
        self.assertTrue(got)
        self.assertTrue(all(math.hypot(x - 30, y - 15) <= config.ZERG_ACCENT_RADIUS + 1.5 or math.hypot(x - 12, y - 12) <= config.ZERG_ACCENT_RADIUS + 1.5 for x, y in got))


class ScatterTests(unittest.TestCase):
    def test_spacing_caps_trees_and_determinism(self) -> None:
        terrain, scene = world()
        ctx = context(terrain, scene, random.Random(3))
        hazards = np.zeros((N, N), bool)
        hazards[50:54, 10:14] = True
        plants = scatter(ctx, hazards, 7)
        self.assertEqual(plants, scatter(context(terrain, scene, random.Random(3)), hazards, 7))
        by_kind: dict[str, list] = {}
        for p in plants:
            by_kind.setdefault(p.kind, []).append(p)
            self.assertFalse(scene.tree_block[int(p.y * FINE), int(p.x * FINE)], p)
            self.assertFalse(hazards[int(p.y), int(p.x)], p)
            self.assertFalse(scene.keepout[int(p.y), int(p.x)], p)
        for kind, items in by_kind.items():
            self.assertLessEqual(len(items), config.FAMILIES[kind].cap)
            spacing = config.FAMILIES[kind].spacing
            for i, a in enumerate(items):
                for b in items[i + 1 :]:
                    self.assertGreaterEqual(math.hypot(a.x - b.x, a.y - b.y), spacing - 1e-6, kind)

    def test_cap_is_enforced(self) -> None:
        terrain, scene = world()
        families = dict(config.FAMILIES)
        families["ZerusTallGrassCluster"] = families["ZerusTallGrassCluster"]._replace(cap=2)
        with mock.patch.object(config, "FAMILIES", families):
            plants = scatter(context(terrain, scene, random.Random(3)), np.zeros((N, N), bool), 7)
        self.assertLessEqual(sum(p.kind == "ZerusTallGrassCluster" for p in plants), 2)


class LaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.terrain, self.scene = world()
        self.lanes = find_lanes(self.terrain, self.scene)
        placed, self.notes = place_hazards(self.lanes, self.terrain, self.scene)
        self.hazards, self.detour, _ = settle(self.lanes, placed, self.terrain, self.scene)

    def test_lanes_follow_their_regions(self) -> None:
        self.assertEqual(len(self.lanes), len(config.LANE_ROUTES))
        regions = self.scene.regions
        for lane, route in zip(self.lanes, config.LANE_ROUTES):
            for point, name in ((lane.points[0], route.zerg), (lane.points[lane.split], route.cross), (lane.points[-1], route.terran)):
                r = regions[name]
                self.assertLess(math.hypot(point[0] - r.x, point[1] - r.y), 1.5, (route.name, name))

    def test_missing_region_fails(self) -> None:
        # Negative case: a lane whose X region is missing must not be invented.
        regions = dict(self.scene.regions)
        del regions["X Top"]
        with self.assertRaises(ValueError):
            find_lanes(self.terrain, self.scene._replace(regions=regions))

    def test_hazards_balanced_per_lane(self) -> None:
        self.assertTrue(self.hazards)
        self.assertEqual(balance_problems(self.hazards, len(self.lanes)), [])
        for lane in self.lanes:
            for pair in {h.pair for h in self.hazards if h.lane == lane.index}:
                a, b = [h for h in self.hazards if h.lane == lane.index and h.pair == pair]
                self.assertEqual(a.kind, b.kind)
                self.assertNotEqual(a.side, b.side)
                self.assertEqual(a.along, b.along)

    def test_unbalanced_pair_is_caught(self) -> None:
        # Negative case: shift one side of one pair; the balance check must flag it.
        h = self.hazards[0]
        bad = [h._replace(along=h.along + 3.0)] + self.hazards[1:]
        self.assertTrue(balance_problems(bad, len(self.lanes)))

    def test_lanes_stay_open(self) -> None:
        self.assertEqual(self.detour, detours(self.lanes, self.hazards, self.terrain, self.scene))
        for d in self.detour:
            self.assertLessEqual(d, config.LANE_DETOUR_MAX)

    def test_settle_drops_pairs_that_cut_a_lane(self) -> None:
        # Negative case: a wall of extra hazards across lane 0 must be removed, both sides.
        lane = self.lanes[0]
        mid = lane.points[lane.split]
        wall = [Placed("ZerusTarPit", mid[0] + dx, mid[1] - dx, 0.0, 0, side, 99, 0.0)
                for dx in range(-12, 13, 3) for side in config.FACTION_SIDES]
        kept, detour, notes = settle(self.lanes, self.hazards + wall, self.terrain, self.scene)
        self.assertTrue(all(d <= config.LANE_DETOUR_MAX for d in detour))
        self.assertEqual(balance_problems(kept, len(self.lanes)), [])
        self.assertTrue(notes)

    def test_blocked_spot_drops_the_pair_on_both_sides(self) -> None:
        # Negative case: keep out every spot on the Terran side; no hazard may remain on either side.
        keepout = self.scene.keepout.copy()
        ys, xs = np.mgrid[0:N, 0:N]
        keepout[xs + ys > N + 2] = True
        scene = self.scene._replace(keepout=keepout)
        hazards, notes = place_hazards(self.lanes, self.terrain, scene)
        self.assertEqual(hazards, [])
        self.assertTrue(notes)


class WaterLevelTests(unittest.TestCase):
    def test_both_editor_forms(self) -> None:
        import tempfile
        from pathlib import Path

        from flora.terrain import water_levels

        root = Path(tempfile.mkdtemp())
        game = root / "Base.SC2Data" / "GameData"
        game.mkdir(parents=True)
        (game / "WaterData.xml").write_text(
            '<Catalog>\n'
            '    <CWater id="Old">\n        <State index="0">\n            <Height value="6.5"/>\n        </State>\n    </CWater>\n'
            '    <CWater id="BelShir">\n        <State index="0" Height="7.150000" Specularity="56.5"/>\n    </CWater>\n'
            '    <CWater id="Xil"/>\n'
            '</Catalog>\n',
            encoding="utf-8",
        )
        levels = water_levels(root)
        self.assertEqual(levels, {"Old": 6.5, "BelShir": 7.15})  # Xil has no override: not listed


class DiskCellsTests(unittest.TestCase):
    def test_disk_off_the_map_is_empty(self) -> None:
        # Wide hazard wiggle rings reach past the map edge.
        for x, y in ((-20.0, 5.0), (5.0, -20.0), (300.0, 5.0), (5.0, 300.0)):
            rows, cols = disk_cells(x, y, 2.0, (64, 64))
            self.assertEqual(len(rows), 0)
            self.assertEqual(len(cols), 0)

    def test_disk_inside_the_map_has_cells(self) -> None:
        rows, _ = disk_cells(10.0, 10.0, 2.0, (64, 64))
        self.assertGreater(len(rows), 0)


class BuildTests(unittest.TestCase):
    def test_balance_problem_is_reported(self) -> None:
        hazards = [Placed("ZerusTarPit", 1, 1, 0, 0, "Zerg", 0, 18.0)]
        self.assertTrue(balance_problems(hazards, 1))

    def test_missing_family_is_reported(self) -> None:
        plan = Plan([], [], [], [], [])
        self.assertEqual(len(family_problems(plan)), len(config.FAMILIES))

    def test_objects_sit_on_the_ground_with_fresh_ids(self) -> None:
        terrain, _ = world()
        plan = Plan([], [Placed("ZerusTarPit", 1.5, 2.5, 0.0, 0, "Zerg", 0, 18.0)], [], [], [])
        xml = objects_xml(plan, 500, terrain)
        self.assertIn('Id="500"', xml)
        self.assertIn('Position="1.5,2.5,12.7000"', xml)  # flat ground 10 + GROUND_LIFT 2.6 + HAZARD_LIFT 0.1
        self.assertIn('<Flag Index="HeightAbsolute" Value="1"/>', xml)
        # Negative case: z 0 buried props off low ground (operator probe).
        self.assertNotIn(',0" Rotation', xml)

    def test_small_flora_sits_higher(self) -> None:
        # Operator probe 2026-11-23: under scale 2.0 at ground +3.0 (row C).
        terrain, _ = world()
        plants = [Plant("ZerusPlant", 1.5, 2.5, 0.0, 1.99, 0), Plant("ZerusBrambles", 3.5, 2.5, 0.0, 2.0, 0), Plant("ZerusPlant", 5.5, 2.5, 0.0, 0.6, 0)]
        xml = objects_xml(Plan([], [Placed("ZerusTarPit", 7.5, 2.5, 0.0, 0, "Zerg", 0, 18.0)], plants, [], []), 500, terrain)
        self.assertIn('Position="1.5,2.5,13.0000"', xml)
        self.assertIn('Position="5.5,2.5,13.0000"', xml)
        # Negative cases: scale 2.0 keeps GROUND_LIFT; a hazard keeps its lift.
        self.assertIn('Position="3.5,2.5,12.6000"', xml)
        self.assertIn('Position="7.5,2.5,12.7000"', xml)

    def test_hazard_sits_on_the_lowest_footprint_ground(self) -> None:
        # Operator 2026-11-16: the centre height left an edge floating.
        terrain, _ = world()
        height = terrain.height.copy()
        height[5, 5] = 9.0  # one low cell under the tar pit (half 2.0)
        terrain = terrain._replace(height=height)
        plan = Plan([], [Placed("ZerusTarPit", 5.5, 5.5, 0.0, 0, "Zerg", 0, 18.0)], [], [], [])
        xml = objects_xml(plan, 500, terrain)
        self.assertIn('Position="5.5,5.5,11.7000"', xml)  # lowest ground 9 + 2.6 + 0.1
        self.assertNotIn('Position="5.5,5.5,12.7000"', xml)


if __name__ == "__main__":
    unittest.main()
