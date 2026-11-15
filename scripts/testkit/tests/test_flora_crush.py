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


if __name__ == "__main__":
    unittest.main()
