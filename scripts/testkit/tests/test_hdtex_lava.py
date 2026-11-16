from __future__ import annotations

import unittest

import numpy as np

from hd_textures import lowest_correlation
from hdtex.pipeline import merge_entries, select
from hdtex.roles import RoleError, match_layout, normal_layout, split_normal
from hdtex.sources import Override, TextureRef

RNG = np.random.default_rng(7)


def swizzled(fill: str) -> np.ndarray:
    rgba = np.zeros((8, 8, 4), dtype=np.uint8)
    rgba[:, :, 1] = RNG.integers(64, 192, (8, 8))
    rgba[:, :, 3] = RNG.integers(64, 192, (8, 8))
    if fill == "fixed":
        rgba[:, :, 0], rgba[:, :, 2] = 255, 0
    else:
        rgba[:, :, 0] = rgba[:, :, 1]
        rgba[:, :, 2] = rgba[:, :, 1]
    return rgba


class NormalLayoutTest(unittest.TestCase):
    def test_both_fillers_recognised(self):
        self.assertEqual(normal_layout(swizzled("fixed")), "fixed")
        self.assertEqual(normal_layout(swizzled("copy")), "copy")

    def test_split_ignores_filler(self):
        a, b = swizzled("fixed"), swizzled("copy")
        b[:, :, 1], b[:, :, 3] = a[:, :, 1], a[:, :, 3]
        b[:, :, 0] = b[:, :, 2] = a[:, :, 1]
        self.assertTrue(np.array_equal(split_normal(a)["normal"], split_normal(b)["normal"]))

    def test_unknown_layout_rejected(self):
        rgba = swizzled("fixed")
        rgba[:, :, 0] = RNG.integers(0, 255, (8, 8))  # red is neither 255 nor a copy of green
        with self.assertRaises(RoleError):
            normal_layout(rgba)

    def test_copy_layout_written_back(self):
        out = match_layout([swizzled("fixed")], "copy")[0]
        self.assertTrue(np.array_equal(out[:, :, 0], out[:, :, 1]))
        self.assertTrue(np.array_equal(out[:, :, 2], out[:, :, 1]))

    def test_fixed_layout_untouched(self):
        level = swizzled("fixed")
        self.assertIs(match_layout([level], "fixed")[0], level)


def ref(entry: str, path: str) -> TextureRef:
    return TextureRef(path, "diffuse", path, path, (Override("TerrainTexData.xml", "CTerrainTex", entry, "Texture"),))


class SelectTest(unittest.TestCase):
    def test_select_by_entry(self):
        refs = [ref("Zerus1", "a"), ref("CharLavaCracks", "b")]
        self.assertEqual([r.asset for r in select(refs, ("charlavacracks",))], ["b"])

    def test_select_all_when_empty(self):
        refs = [ref("Zerus1", "a")]
        self.assertEqual(select(refs, ()), refs)

    def test_unknown_entry_rejected(self):
        with self.assertRaises(RoleError):
            select([ref("Zerus1", "a")], ("Nope",))

    def test_merge_replaces_by_map_path(self):
        old = [{"map_path": "a", "v": 1}, {"map_path": "b", "v": 1}]
        merged = merge_entries(old, [{"map_path": "b", "v": 2}])
        self.assertEqual(sorted((e["map_path"], e["v"]) for e in merged), [("a", 1), ("b", 2)])


class CorrelationRuleTest(unittest.TestCase):
    def test_flat_channel_proven_by_psnr(self):
        tex = {"file": "x", "fidelity_corr": [0.99, 0.09, 0.25, 0.99], "fidelity_psnr": [45.0, 53.7, 53.9, 48.0]}
        self.assertEqual(lowest_correlation(tex), 0.99)

    def test_low_psnr_channel_still_judged(self):
        tex = {"file": "x", "fidelity_corr": [0.99, 0.09, 0.99, 0.99], "fidelity_psnr": [45.0, 30.0, 45.0, 45.0]}
        self.assertEqual(lowest_correlation(tex), 0.09)


if __name__ == "__main__":
    unittest.main()
