import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import doodad_occlusion as occ
from project_root import project_root

MAP_MODELS = """<?xml version="1.0" encoding="utf-8"?>
<Catalog>
    <CModel id="SCOBAThing" parent="Unit"/>
    <CModel id="SCOBAHidden" parent="Unit">
        <Occlusion value="Hide"/>
    </CModel>
</Catalog>
"""


class ResolveTest(unittest.TestCase):
    def test_show_and_unset_resolve_through_parents(self) -> None:
        entries = [
            ("Base", None, "Show"),
            ("Child", "Base", None),
            ("Plain", "Unit", None),
            ("Hidden", "Base", "Hide"),
            ("Off", None, "None"),
        ]
        got = occ.resolve_show(entries)
        self.assertIn("Child", got)
        self.assertIn("Plain", got)
        # Negative: explicit Hide and None are kept.
        self.assertNotIn("Hidden", got)
        self.assertNotIn("Off", got)

    def test_later_entry_overrides(self) -> None:
        got = occ.resolve_show([("A", None, "Show"), ("A", None, "Hide")])
        self.assertNotIn("A", got)


class BuiltMapTest(unittest.TestCase):
    def test_step_sets_none_on_stock_and_map_models(self) -> None:
        stock = json.loads((project_root() / occ.SILHOUETTE_JSON).read_text(encoding="utf-8"))["models"]
        for name in ("Marine", "Kerrigan", "Tosh"):
            self.assertIn(name, stock)
        with tempfile.TemporaryDirectory() as tmp:
            game = Path(tmp) / "Base.SC2Data" / "GameData"
            game.mkdir(parents=True)
            (game / "ModelData.xml").write_text(MAP_MODELS, encoding="utf-8")
            occ.disable_unit_silhouettes(Path(tmp))
            root = ET.parse(game / "ModelData.xml").getroot()
            value = {e.get("id"): e.find("Occlusion").get("value") for e in root.findall("CModel")}
        self.assertEqual(value["SCOBAThing"], "None")
        self.assertEqual(value["Marine"], "None")
        # Negative: a map model that hides stays Hide.
        self.assertEqual(value["SCOBAHidden"], "Hide")


if __name__ == "__main__":
    unittest.main()
