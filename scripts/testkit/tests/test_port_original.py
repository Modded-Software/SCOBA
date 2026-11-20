"""Host tests for scripts/mapgen/port_original_objects.py and port_original_terrain.py."""

from __future__ import annotations

import struct
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from mapgen import port_original_objects as objs
from mapgen import port_original_terrain as terr

HEAD = '<?xml version="1.0" encoding="utf-8"?>\r\n<PlacedObjects Version="27">\r\n'
TAIL = "</PlacedObjects>\r\n"
UNIT_A = '    <ObjectUnit Id="1" Position="1,1,0" UnitType="SporeCannon" Player="8"/>\r\n'
TREE_B = '    <ObjectDoodad Id="2" Position="2,2,5" Type="ZerusTree"/>\r\n'
RAIN_C = '    <ObjectDoodad Id="3" Position="3,3,7" Type="RainEmitterLarge"/>\r\n'
NEW_D = '    <ObjectDoodad Id="4" Position="4,4,1" Type="Waterfall">\r\n        <Flag Index="HeightOffset" Value="1" />\r\n    </ObjectDoodad>\r\n'
GROUP_E = '    <Group Type="ObjectDoodad" Name="G" Id="5">\r\n        <GroupObject Id="4" />\r\n    </Group>\r\n'
SRC_ONLY = '    <ObjectDoodad Id="9" Position="9,9,0" Type="Waterfall"/>\r\n'


def write_map(folder: Path, objects: str) -> Path:
    folder.mkdir(parents=True)
    (folder / "Objects").write_bytes(objects.encode("utf-8"))
    return folder


def ids(path: Path) -> dict[str, ET.Element]:
    return {el.get("Id"): el for el in ET.parse(path).getroot()}


class PortObjectsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.base = write_map(self.tmp / "base", HEAD + UNIT_A + TREE_B + RAIN_C + TAIL)
        self.src = self.tmp / "src_Objects"
        self.src.write_bytes((HEAD + UNIT_A + TREE_B + RAIN_C + SRC_ONLY + TAIL).encode("utf-8"))

    def run_port(self, edited: str, *extra: str) -> int:
        edited_dir = write_map(self.tmp / "edited", edited)
        argv = ["port", "--base", str(self.base), "--edited", str(edited_dir), *extra]
        with mock.patch.object(objs, "SRC_OBJECTS", self.src), mock.patch.object(sys, "argv", argv):
            return objs.main()

    def test_remove_move_add_and_skip(self) -> None:
        edited = HEAD + TREE_B.replace("2,2,5", "2,2,6") + RAIN_C.replace("3,3,7", "3,3,8") + NEW_D + GROUP_E + TAIL
        self.assertEqual(self.run_port(edited, "--skip", "3"), 0)
        result = ids(self.src)
        self.assertNotIn("1", result)  # removed
        self.assertEqual(result["2"].get("Position"), "2,2,6")  # moved
        self.assertEqual(result["3"].get("Position"), "3,3,7")  # skipped: not moved
        self.assertIn("9", result)  # src-only object kept
        self.assertEqual(result["4"].find("Flag").get("Index"), "HeightOffset")  # added with children
        self.assertEqual(result["5"].tag, "Group")
        self.assertNotIn(b"\n    <", self.src.read_bytes().replace(b"\r\n", b""))  # CRLF kept

    def test_flag_change_replaces_element(self) -> None:
        flagged = TREE_B.replace('5" Type="ZerusTree"/>', '7" Type="ZerusTree">\r\n        <Flag Index="HeightAbsolute" Value="1"/>\r\n    </ObjectDoodad>')
        self.assertEqual(self.run_port(HEAD + UNIT_A + flagged + RAIN_C + TAIL), 0)
        tree = ids(self.src)["2"]
        self.assertEqual(tree.get("Position"), "2,2,7")
        self.assertEqual([c.get("Index") for c in tree], ["HeightAbsolute"])
        self.assertIn("9", ids(self.src))

    def test_refuses_non_flag_child_change(self) -> None:
        before = self.src.read_bytes()
        odd = TREE_B.replace('Type="ZerusTree"/>', 'Type="ZerusTree"><Other/></ObjectDoodad>')
        with self.assertRaises(SystemExit):
            self.run_port(HEAD + UNIT_A + odd + RAIN_C + TAIL)
        self.assertEqual(self.src.read_bytes(), before)

    def test_check_writes_nothing(self) -> None:
        before = self.src.read_bytes()
        self.assertEqual(self.run_port(HEAD + TREE_B + RAIN_C + TAIL, "--check"), 0)
        self.assertEqual(self.src.read_bytes(), before)

    def test_refuses_when_src_differs_from_base(self) -> None:
        self.src.write_bytes(self.src.read_bytes().replace(b"2,2,5", b"2,2,99"))
        before = self.src.read_bytes()
        with self.assertRaises(SystemExit):
            self.run_port(HEAD + UNIT_A + TREE_B.replace("2,2,5", "2,2,6") + RAIN_C + TAIL)
        self.assertEqual(self.src.read_bytes(), before)

    def test_refuses_other_attribute_change(self) -> None:
        before = self.src.read_bytes()
        with self.assertRaises(SystemExit):
            self.run_port(HEAD + UNIT_A.replace('Player="8"', 'Player="7"') + TREE_B + RAIN_C + TAIL)
        self.assertEqual(self.src.read_bytes(), before)

    def test_refuses_added_id_already_in_src(self) -> None:
        before = self.src.read_bytes()
        with self.assertRaises(SystemExit):
            self.run_port(HEAD + UNIT_A + TREE_B + RAIN_C + SRC_ONLY.replace("9,9,0", "8,8,0") + TAIL)
        self.assertEqual(self.src.read_bytes(), before)


TERRAIN_XML = '<terrain>\n        <vertData quantizeBias="{b}" quantizeScale="1" standardHeight="8" name="t3HeightMap"/>\n        <texture i="7" name="{t}"/>\n</terrain>\n'


def water(rects: list[tuple[float, float, float, float]], junk: int = 0) -> bytes:
    """A t3Water file; `junk` fills the pointer bytes the editor rewrites."""
    out = bytearray(b"WATR" + struct.pack("<II", 110, len(rects)) + bytes(20))
    for r in rects:
        out += b"BelShir\0" + struct.pack("<I", 100) + bytes([junk]) * 28 + struct.pack("<4f", *r)
    return bytes(out)


def write_terrain(folder: Path, height: bytes, bias: str, texture: str = "Zerus5", rects=((0, 0, 8, 8),), junk: int = 0, xil: bool = False) -> Path:
    folder.mkdir(parents=True)
    for name in terr.HEIGHT_FILES:
        (folder / name).write_bytes(height + name.encode())
    (folder / "t3Water").write_bytes(water(list(rects), junk))
    game = folder / "Base.SC2Data" / "GameData"
    game.mkdir(parents=True)
    (game / "WaterData.xml").write_text('<Catalog>\n' + ('    <CWater id="Xil"/>\n' if xil else "") + "</Catalog>\n", encoding="utf-8")
    (folder / "t3Terrain.xml").write_text(TERRAIN_XML.format(b=bias, t=texture), encoding="utf-8")
    return folder


class PortTerrainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.base = write_terrain(self.tmp / "base", b"old", "1.0")
        self.edited = write_terrain(self.tmp / "edited", b"new", "2.0", rects=((1, 1, 4, 4), (4, 4, 8, 8)), junk=7, xil=True)
        # src keeps the pointer bytes of an older editor save: same water.
        self.src = write_terrain(self.tmp / "src", b"old", "1.0", texture="CharLavaCracks", junk=3)

    def run_port(self, *extra: str) -> int:
        argv = ["port", "--base", str(self.base), "--edited", str(self.edited), *extra]
        with mock.patch.object(terr, "SRC", self.src), mock.patch.object(sys, "argv", argv):
            return terr.main()

    def test_copies_heights_pathing_and_vertdata_only(self) -> None:
        self.assertEqual(self.run_port(), 0)
        for name in terr.HEIGHT_FILES:
            self.assertEqual((self.src / name).read_bytes(), b"new" + name.encode())
        xml = (self.src / "t3Terrain.xml").read_text(encoding="utf-8")
        self.assertIn('quantizeBias="2.0"', xml)
        self.assertIn('name="CharLavaCracks"', xml)  # src-only texture change kept
        self.assertIn("CellAttribute_Pnp", terr.HEIGHT_FILES)

    def test_copies_water(self) -> None:
        self.assertEqual(self.run_port(), 0)
        self.assertEqual((self.src / "t3Water").read_bytes(), (self.edited / "t3Water").read_bytes())
        self.assertIn('<CWater id="Xil"/>', (self.src / "Base.SC2Data" / "GameData" / "WaterData.xml").read_text(encoding="utf-8"))

    def test_refuses_when_src_water_rects_differ(self) -> None:
        # Negative case: a real water change in src/ (not pointer bytes) is not overwritten.
        (self.src / "t3Water").write_bytes(water([(0, 0, 9, 9)]))
        with self.assertRaises(SystemExit):
            self.run_port()
        self.assertEqual((self.src / "t3HeightMap").read_bytes(), b"oldt3HeightMap")

    def test_rerun_is_accepted(self) -> None:
        self.assertEqual(self.run_port(), 0)
        self.assertEqual(self.run_port(), 0)

    def test_check_writes_nothing(self) -> None:
        self.assertEqual(self.run_port("--check"), 0)
        self.assertEqual((self.src / "t3HeightMap").read_bytes(), b"oldt3HeightMap")

    def test_refuses_when_src_heights_differ(self) -> None:
        (self.src / "t3HeightMap").write_bytes(b"other")
        with self.assertRaises(SystemExit):
            self.run_port()
        self.assertEqual((self.src / "t3SyncHeightMap").read_bytes(), b"oldt3SyncHeightMap")


if __name__ == "__main__":
    unittest.main()
