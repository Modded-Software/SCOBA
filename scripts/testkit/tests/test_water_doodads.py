"""Host tests for scripts/mapgen/water_doodads.py (REQ-WATER-DOODADS)."""

from __future__ import annotations

import math
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from mapgen import water_doodads as wd

HEAD = '<?xml version="1.0" encoding="utf-8"?>\r\n<PlacedObjects Version="27">\r\n'
TAIL = "</PlacedObjects>\r\n"
OBJECTS = HEAD + (
    '    <ObjectDoodad Id="10" Position="100,100,8" Rotation="1" Scale="1.5,1.5,1.5" Type="Waterfall">\r\n'
    '        <Flag Index="HeightOffset" Value="1" />\r\n    </ObjectDoodad>\r\n'
    '    <ObjectDoodad Id="11" Position="104,100,10" Rotation="1" Scale="1.5,1.5,1.5" Type="Waterfall">\r\n'
    '        <Flag Index="HeightAbsolute" Value="1" />\r\n    </ObjectDoodad>\r\n'
    '    <ObjectDoodad Id="12" Variation="2" Position="50,50,9" Rotation="0" Scale="1,1,1" Type="RockWaterfall"/>\r\n'
    '    <ObjectDoodad Id="13" Position="1,240,13" Rotation="1.3" Scale="1,1,1" Type="ZerusWaterfall"/>\r\n'
    '    <ObjectDoodad Id="14" Position="20,20,5" Rotation="2" Scale="3,3,3" Type="ZerusTree"/>\r\n'
    '    <ObjectDoodad Id="15" Position="30,30,6" Scale="1,1,1" Type="RainEmitterLarge"/>\r\n'
) + TAIL


def by_type(text: str) -> dict[str, list[ET.Element]]:
    out: dict[str, list[ET.Element]] = {}
    for el in ET.fromstring(text.encode("utf-8")):
        out.setdefault(el.get("Type"), []).append(el)
    return out


def pos(el: ET.Element) -> list[float]:
    return [float(v) for v in el.get("Position").split(",")]


class WaterDoodadsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text, self.added = wd.densify_text(OBJECTS)
        self.types = by_type(self.text)
        self.new = [el for el in ET.fromstring(self.text.encode("utf-8")) if int(el.get("Id")) > 15]

    def test_doubles_every_water_type(self) -> None:  # R-WD-01
        self.assertEqual(len(self.types["Waterfall"]), 4)
        self.assertEqual(len(self.types["RockWaterfall"]), 2)
        self.assertEqual(len(self.types["ZerusWaterfall"]), 2)

    def test_other_doodads_untouched(self) -> None:  # negative case
        self.assertEqual(len(self.types["ZerusTree"]), 1)
        self.assertEqual(len(self.types["RainEmitterLarge"]), 1)
        self.assertTrue(self.text.startswith(OBJECTS[: -len(TAIL)]))  # originals byte-identical

    def test_copy_fills_gap_to_neighbour(self) -> None:  # R-WD-02
        copy = next(el for el in self.new if el.get("Type") == "Waterfall")
        x, y, z = pos(copy)
        self.assertLess(abs(x - 102), 0.3)
        self.assertLess(abs(y - 100), 0.3)
        self.assertAlmostEqual(z, 9.0, places=3)

    def test_pair_filled_once(self) -> None:  # second copy of the pair goes beside its source
        copies = [pos(el) for el in self.new if el.get("Type") == "Waterfall"]
        self.assertGreater(math.dist(copies[0][:2], copies[1][:2]), 1.0)

    def test_lone_copy_beside_source_across_facing(self) -> None:  # R-WD-02 fallback
        copy = next(el for el in self.new if el.get("Type") == "ZerusWaterfall")
        dx, dy = pos(copy)[0] - 1, pos(copy)[1] - 240
        across = abs(dx * math.cos(1.3) + dy * math.sin(1.3))  # along facing
        self.assertLess(across, 0.5)
        self.assertGreater(math.hypot(dx, dy), 1.0)

    def test_variation(self) -> None:  # R-WD-03
        rock = next(el for el in self.new if el.get("Type") == "RockWaterfall")
        self.assertNotEqual(rock.get("Variation"), "2")
        self.assertIn(int(rock.get("Variation")), range(7))
        for el in self.new:
            src_rot = {"Waterfall": 1.0, "RockWaterfall": 0.0, "ZerusWaterfall": 1.3}[el.get("Type")]
            d = abs((float(el.get("Rotation")) - src_rot + math.pi) % math.tau - math.pi)
            self.assertLessEqual(d, wd.ROTATION_JITTER + 1e-3)
        scales = {el.get("Scale") for el in self.new}
        self.assertEqual(len(scales), len(self.new))  # every copy has its own scale

    def test_flags_and_ids(self) -> None:
        copy = next(el for el in self.new if el.get("Type") == "Waterfall")
        self.assertIsNotNone(copy.find("Flag"))
        ids = [el.get("Id") for el in ET.fromstring(self.text.encode("utf-8"))]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("\n    <", self.text.replace("\r\n", ""))  # CRLF kept

    def test_deterministic(self) -> None:
        self.assertEqual(wd.densify_text(OBJECTS)[0], self.text)

    def test_apply_marker_and_preload(self) -> None:
        folder = Path(tempfile.mkdtemp())
        (folder / "Objects").write_text(OBJECTS, encoding="utf-8")
        (folder / "Preload.xml").write_text('<Preload>\n<Actor id="RockWaterfall" Variations="2"/>\n</Preload>\n', encoding="utf-8")
        wd.apply_water_doodads(folder)
        once = (folder / "Objects").read_text(encoding="utf-8")
        self.assertEqual(wd.apply_water_doodads(folder), {})  # second run skipped
        self.assertEqual((folder / "Objects").read_text(encoding="utf-8"), once)
        rock = next(el for el in by_type(once)["RockWaterfall"] if el.get("Id") != "12")
        pre = (folder / "Preload.xml").read_text(encoding="utf-8")
        self.assertIn(f'Variations="{",".join(sorted(["2", rock.get("Variation")]))}"', pre)

    def test_preload_adds_missing_entries(self) -> None:
        folder = Path(tempfile.mkdtemp())
        (folder / "Objects").write_text(OBJECTS, encoding="utf-8")
        (folder / "Preload.xml").write_bytes(b'<Preload>\r\n<Actor id="Waterfall"/>\r\n<Unit id="X"/>\r\n</Preload>\r\n')
        wd.apply_water_doodads(folder)
        pre = (folder / "Preload.xml").read_bytes().decode("utf-8")
        self.assertEqual(pre.count('<Actor id="Waterfall"/>'), 1)
        self.assertIn('<Actor id="ZerusWaterfall"/>', pre)
        self.assertRegex(pre, r'<Actor id="RockWaterfall" Variations="\d,\d"/>')
        self.assertIn('<Unit id="X"/>', pre)  # other entries kept
        self.assertNotIn("\n<", pre.replace("\r\n", ""))  # CRLF kept


if __name__ == "__main__":
    unittest.main()
