import re
import unittest

from flora import config
from flora.crush import BUCKET, CRUSH_KINDS, GRID, SIZE_REF, bucket, effect_size, galaxy, table


class CrushTableTest(unittest.TestCase):
    PLANTS = [
        ("ZerusTallGrassCluster", 100.5, 20.25, 3.5, 1.0),
        ("ZerusRocks", 10.0, 10.0, 3.0, 1.0),  # not generated flora
        ("ZerusPlant", 3.0, 4.0, 3.25, 0.5),
        ("ZerusBrambles", 7.9, 1.0, 4.0, 2.0),
    ]

    def test_only_crush_kinds_in_bucket_order(self) -> None:
        rows = table(self.PLANTS)
        self.assertEqual(len(rows), 3)
        self.assertEqual([r[0] for r in rows], sorted(r[0] for r in rows))
        self.assertEqual(sorted(CRUSH_KINDS[r[1]] for r in rows), ["ZerusBrambles", "ZerusPlant", "ZerusTallGrassCluster"])
        self.assertEqual(sorted(r[4] for r in rows), [3.25, 3.5, 4.0])

    def test_bucket_index(self) -> None:
        self.assertEqual(bucket(0.0, 0.0), 0)
        self.assertEqual(bucket(BUCKET + 0.1, 0.0), 1)
        self.assertEqual(bucket(0.0, BUCKET + 0.1), GRID)
        self.assertEqual(bucket(999.0, 999.0), GRID * GRID - 1)  # clamped

    def test_galaxy_buckets_cover_every_row(self) -> None:
        text = galaxy(self.PLANTS)
        self.assertIn("const int c_CRUSH_COUNT = 3;", text)
        spans = [(int(s), int(n)) for s, n in re.findall(r"gv_crushStart\[\d+\] = (\d+); gv_crushLen\[\d+\] = (\d+);", text)]
        covered = sorted(i for s, n in spans for i in range(s, s + n))
        self.assertEqual(covered, [0, 1, 2])
        # Negative case: the non-crushable plant is not in the table.
        self.assertNotIn("10.000", text)
        self.assertIn("gv_crushZ", text)
        self.assertIn("= 3.250;", text)

    def test_effect_size_follows_scale_and_kind(self) -> None:
        grass = config.FAMILIES["ZerusTallGrassCluster"].spacing
        self.assertAlmostEqual(effect_size("ZerusTallGrassCluster", 0.5), round(0.5 * grass / SIZE_REF, 3))
        # Negative case: a bigger doodad of the same kind never gets a smaller cloud.
        self.assertGreater(effect_size("ZerusTallGrassCluster", 1.0), effect_size("ZerusTallGrassCluster", 0.5))
        self.assertIn("gv_crushS", galaxy(self.PLANTS))

    def test_empty_stub_compiles_shape(self) -> None:
        text = galaxy([])
        self.assertIn("const int c_CRUSH_COUNT = 0;", text)
        self.assertIn("fixed[1] gv_crushX;", text)
        self.assertIn("void gf_CrushLoad () {", text)


class WaterSpanTest(unittest.TestCase):
    def terrain(self):
        import numpy as np
        from types import SimpleNamespace

        n = 8
        height = np.full((n, n), 5.0)
        lift = config.GROUND_LIFT
        surface = 5.0 + lift + 1.0  # 1.0 above the visible ground
        depth = np.full((n, n), -np.inf)
        depth[2, 1:6] = surface - height[2, 1:6]  # water rect over row 2, x 1..5
        height[2, 4] = 5.0 + 0.95  # shore: surface only 0.05 above the visible ground
        depth[2, 4] = surface - height[2, 4]
        return SimpleNamespace(height=height, depth=depth), surface

    def test_spans_hold_wet_cells_only(self) -> None:
        from flora.crush import water_spans

        terrain, surface = self.terrain()
        spans = water_spans(terrain)
        self.assertEqual([(y, x0, x1) for y, x0, x1, _z, _d in spans], [(2, 1, 4), (2, 5, 6)])
        self.assertTrue(all(abs(z - surface) < 1e-3 for *_r, z, _d in spans))
        # Visible depth: surface over the visible ground (1.0 by construction).
        self.assertTrue(all(abs(d - 1.0) < 1e-3 for *_r, d in spans))
        # Negative cases: the shallow shore cell and cells outside the rect are dry.
        self.assertFalse(any(x0 <= 4 < x1 for _y, x0, x1, _z, _d in spans))
        self.assertFalse(any(y != 2 for y, *_r in spans))

    def test_galaxy_rows_index_their_spans(self) -> None:
        from flora.crush import water_spans

        terrain, _ = self.terrain()
        text = galaxy([], water_spans(terrain))
        self.assertIn("const int c_WATER_SPANS = 2;", text)
        self.assertIn("gv_waterRowFirst[2] = 0; gv_waterRowCount[2] = 2;", text)
        self.assertNotIn("gv_waterRowCount[3]", text)
        self.assertIn("gv_waterD[0] = 1.000;", text)


if __name__ == "__main__":
    unittest.main()
