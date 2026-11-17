import unittest
from types import SimpleNamespace

import numpy as np

from flora import border, config

OBJECTS = (
    '<ObjectDoodad Id="1" Variation="3" Position="10,10,5" Scale="2,2,2" Type="ZerusTreeFpabc">\n'
    '<ObjectDoodad Id="2" Variation="1" Position="20,20,5" Scale="3,3,3" Type="ZerusTreeFpdef">\n'
    '<ObjectUnit Id="3" Position="21,9,0" Scale="1,1,1" UnitType="SCOBAOvermind" Player="8">\n'
    '<ObjectUnit Id="4" Position="240,248,0" Scale="2,2,2" UnitType="PsiDecimator" Player="7">\n'
)


def bowl() -> SimpleNamespace:
    n = config.MAP_CELLS
    y, x = np.mgrid[0:n, 0:n]
    r = np.hypot(x - n / 2, y - n / 2)
    return SimpleNamespace(height=4.0 + 0.1 * r)  # rises toward the rim


class BorderTest(unittest.TestCase):
    def test_rows_band_and_scale(self) -> None:
        plants = border.plan(bowl(), OBJECTS)
        trees = [p for p in plants if p[0] == border.BORDER_TREE]
        brambles = [p for p in plants if p[0] == border.BRAMBLE]
        self.assertGreater(len(trees), 0)
        self.assertGreater(len(brambles), 0)
        n = config.MAP_CELLS
        for kind, _v, x, y, _z, _r, s in plants:
            inset = min(x, y, n - x, n - y)
            lo, hi = border.BRAMBLE_BAND if kind == border.BRAMBLE else (-1.3, 1.3)
            self.assertTrue(lo - 1e-6 <= inset <= hi + 1e-6, (kind, x, y))
        # Trees copy placed scales times BORDER_SCALE (2 or 3 -> 3 or 4.5).
        self.assertEqual({round(p[6], 3) for p in trees}, {3.0, 4.5})
        low, high = config.FAMILIES[border.BRAMBLE].scale
        for p in brambles:
            self.assertTrue(low * border.BORDER_SCALE <= p[6] <= high * border.BORDER_SCALE)

    def test_heights_follow_the_bowl(self) -> None:
        t = bowl()
        for kind, _v, x, y, z, _r, _s in border.plan(t, OBJECTS):
            want = border.ground(t, x, y) + (config.GROUND_LIFT if kind == border.BRAMBLE else 0.0)
            self.assertAlmostEqual(z, want, places=6)
            # Negative case: never at the bowl floor (z 4) on the rim.
            self.assertGreater(z, 10.0)

    def test_nothing_near_hive_and_psi_decimator(self) -> None:
        import math

        plants = border.plan(bowl(), OBJECTS)
        for ux, uy, r in ((21.0, 9.0, border.KEEPOUT_UNITS["SCOBAOvermind"]), (240.0, 248.0, border.KEEPOUT_UNITS["PsiDecimator"])):
            near = [p for p in plants if math.hypot(p[2] - ux, p[3] - uy) <= r]
            self.assertEqual(near, [])
        # Negative case: missing keep-out units fail loudly.
        with self.assertRaises(ValueError):
            border.plan(bowl(), OBJECTS.split("<ObjectUnit")[0])

    def test_deterministic_and_skips_border_trees(self) -> None:
        t = bowl()
        first = border.plan(t, OBJECTS)
        again = OBJECTS + f'<ObjectDoodad Id="9" Position="1,1,1" Scale="9,9,9" Type="{border.BORDER_TREE}">\n'
        self.assertEqual(first, border.plan(t, again))


if __name__ == "__main__":
    unittest.main()
