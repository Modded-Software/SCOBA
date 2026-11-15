import math
import unittest

from flora import config, dirt, gates
from flora import scene as scene_mod
from flora import terrain as terrain_mod
from project_root import project_root

BUILT = project_root() / "out" / "SCOBA256.SC2Map"


class GateTableTest(unittest.TestCase):
    def test_galaxy_indexes_side_and_lane(self) -> None:
        text = gates.galaxy([gates.Gate("top", "Terran", 10.5, 20.5, 3.0), gates.Gate("center", "Zerg", 1.5, 2.5, 2.0)])
        self.assertIn("gv_gateAt[1][3] = Point(10.50, 20.50); gv_gateRadius[1][3] = 3.00;", text)
        self.assertIn("gv_gateAt[0][1] = Point(1.50, 2.50); gv_gateRadius[0][1] = 2.00;", text)

    def test_empty_table_has_no_gates(self) -> None:
        # Negative case: the src/ copy sends units straight on (radius 0 = no gate).
        self.assertNotIn("gv_gateRadius[", gates.galaxy([]).split("void gf_GateLoad")[1])


@unittest.skipUnless((BUILT / "t3TextureMasks").is_file(), "needs the built map (scripts/playtest.sh build)")
class BuiltGatesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.terrain = terrain_mod.load(BUILT)
        cls.scene = scene_mod.load(BUILT)
        cls.gates = gates.find(BUILT, cls.terrain, cls.scene)

    def test_one_gate_per_half_lane(self) -> None:
        self.assertEqual(sorted((g.lane, g.side) for g in self.gates), sorted((r.name, s) for r in config.LANE_ROUTES for s in gates.SIDES))

    def test_every_pick_is_on_dirt(self) -> None:
        self.assertEqual(gates.problems(BUILT, self.gates, self.terrain.height.shape[0]), [])

    def test_gate_lies_between_spawn_and_x(self) -> None:
        for route in config.LANE_ROUTES:
            cross = self.scene.regions[route.cross]
            for side, name in zip(gates.SIDES, (route.zerg, route.terran)):
                spawn = self.scene.regions[name]
                g = next(g for g in self.gates if g.lane == route.name and g.side == side)
                leg = math.hypot(cross.x - spawn.x, cross.y - spawn.y)
                # Negative case: not at either end, not off to the side.
                self.assertGreater(math.hypot(g.x - spawn.x, g.y - spawn.y), 0.2 * leg, f"{route.name} {side}")
                self.assertGreater(math.hypot(g.x - cross.x, g.y - cross.y), 0.2 * leg, f"{route.name} {side}")
                self.assertLess(math.hypot(g.x - spawn.x, g.y - spawn.y) + math.hypot(g.x - cross.x, g.y - cross.y), 1.6 * leg)

    def test_dirt_is_the_lane_texture(self) -> None:
        on = dirt.dirt_cells(BUILT, self.terrain.height.shape[0])
        self.assertLess(on.mean(), 0.3)  # lanes only, not the whole map
        self.assertGreater(on.mean(), 0.05)


if __name__ == "__main__":
    unittest.main()
