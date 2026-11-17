"""Large trees are lowered by their final scale (flora.lift.sink_trees)."""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

import numpy as np

from flora import terrain
from flora.lift import SINK_MARKER, sink_text, sink_trees, tree_sink
from project_root import project_root

ABS = '        <Flag Index="HeightAbsolute" Value="1"/>\n'


def tree(ident: int, scale: float, z: float = 10.0, kind: str = "ZerusTreeFpabc", absolute: bool = True) -> str:
    flags = ABS if absolute else ""
    return (
        f'    <ObjectDoodad Id="{ident}" Position="5,5,{z:.4f}" Rotation="0" Scale="{scale:g},{scale:g},{scale:g}" Type="{kind}">\n'
        f"{flags}    </ObjectDoodad>\n"
    )


def z_of(text: str, ident: int) -> float:
    return float(re.search(rf'Id="{ident}" Position="[^,]+,[^,]+,([^"]+)"', text).group(1))


class TreeSinkTest(unittest.TestCase):
    def test_steps(self) -> None:
        self.assertEqual(tree_sink(4.0), 0.0)
        self.assertEqual(tree_sink(4.01), 1.0)
        self.assertEqual(tree_sink(6.0), 1.0)
        self.assertEqual(tree_sink(6.01), 2.0)
        self.assertEqual(tree_sink(8.0), 2.0)  # not cumulative: -2, not -3

    def test_text(self) -> None:
        text = "".join(
            (
                tree(1, 3.9),
                tree(2, 5.0),
                tree(3, 8.0),
                tree(4, 8.0, kind="ZerusTreeScobaBorder"),
                tree(5, 8.0, absolute=False),  # engine places it: left alone
                tree(6, 8.0, kind="ZerusBrambles"),  # not a tree
            )
        )
        out, count = sink_text(text)
        self.assertEqual(count, 3)
        self.assertEqual([z_of(out, i) for i in range(1, 7)], [10.0, 9.0, 8.0, 8.0, 10.0, 10.0])

    def test_once(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Objects").write_text(f"<PlacedObjects>\n{tree(1, 7.0)}</PlacedObjects>\n", encoding="utf-8")
            self.assertEqual(sink_trees(root), 1)
            self.assertEqual(sink_trees(root), 0)
            self.assertTrue((root / SINK_MARKER).exists())
            self.assertEqual(z_of((root / "Objects").read_text(encoding="utf-8"), 1), 8.0)

    def test_calibration_ignores_the_sink(self) -> None:
        raw = np.zeros((20, 20))
        before = tree(1, 3.0, 10.0) + tree(2, 5.0, 10.0) + tree(3, 7.0, 10.0)
        after, _ = sink_text(before)
        self.assertEqual(terrain._offset(raw, 1.0, before), 10.0)
        self.assertEqual(terrain._offset(raw, 1.0, after, sunk=True), 10.0)
        # Negative: without the correction the calibration moves.
        self.assertEqual(terrain._offset(raw, 1.0, after), 9.0)


class BuiltMapTest(unittest.TestCase):
    BUILT = project_root() / "out" / "SCOBA256.SC2Map"

    def setUp(self) -> None:
        if not (self.BUILT / SINK_MARKER).exists():
            self.skipTest("built map has no sunk trees; run scripts/playtest.sh build")

    def test_built_trees_are_sunk(self) -> None:
        built = (self.BUILT / "Objects").read_text(encoding="utf-8")
        marker = (self.BUILT / SINK_MARKER).read_text(encoding="utf-8")
        sunk = int(re.search(r"sunk=(\d+)", marker).group(1))
        big = 0
        for m in re.finditer(r'<ObjectDoodad\b[^>]*>.*?</ObjectDoodad>', built, re.S):
            block = m.group(0)
            if 'Type="ZerusTree' in block and 'Index="HeightAbsolute" Value="1"' in block:
                if tree_sink(float(re.search(r'\bScale="([^",]+)', block).group(1))) > 0:
                    big += 1
        self.assertGreater(big, 0)
        self.assertEqual(sunk, big)


if __name__ == "__main__":
    unittest.main()
