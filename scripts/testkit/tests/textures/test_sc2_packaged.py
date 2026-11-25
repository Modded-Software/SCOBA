"""A map folder without what the pack step wrote into it (R-HD-54, R-HD-108)."""

from __future__ import annotations

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from hdtex.sc2.packaged import (
    GAMEDATA,
    HD_MODEL_DIR,
    PRIOR,
    PackagedError,
    is_packaged,
    name_files,
    own_catalog,
    require_unpackaged,
)
from hdtex.sc2.sources import HD_DIR

MODELS = "ModelData.xml"
TERRAIN = "TerrainTexData.xml"
COPY = f"{HD_MODEL_DIR}\\Own.m3"
GRASS = f"{HD_DIR}\\grass_scoba_hd.dds"


def entries(text: str | None) -> list[str]:
    """The entries of a catalog text, without its layout."""
    found = []
    for node in ET.fromstring(text or "<Catalog/>"):
        for part in node.iter():
            part.text = (part.text or "").strip() or None
            part.tail = None
        found.append(ET.tostring(node, encoding="unicode"))
    return found


class PackagedCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.map_dir = Path(self.temp.name)

    def write(self, body: str, name: str = MODELS) -> str:
        (self.map_dir / GAMEDATA).mkdir(parents=True, exist_ok=True)
        text = f"<Catalog>\n{body}\n</Catalog>\n"
        (self.map_dir / GAMEDATA / name).write_text(text)
        return text

    def models(self, values: dict[tuple[str, str], str]) -> None:
        name_files(self.map_dir, {(MODELS, "CModel"): values})

    def model(self, entry: str) -> str | None:
        root = ET.fromstring(own_catalog(self.map_dir, MODELS) or "<Catalog/>")
        node = next(
            (item for item in root.iter("CModel") if item.get("id") == entry), None
        )
        return (
            None
            if node is None or node.find("Model") is None
            else node.find("Model").get("value")
        )


class FolderTest(PackagedCase):
    def test_only_the_two_folders_of_the_pack_step_are_packaged(self) -> None:
        self.assertTrue(is_packaged(f"{HD_MODEL_DIR}\\Own.m3"))
        self.assertTrue(is_packaged(GRASS.replace("\\", "/")))
        self.assertFalse(is_packaged("Assets\\Models\\Own.m3"))
        self.assertFalse(is_packaged("Assets\\Textures\\grass_scoba_hd.dds"))

    def test_a_map_without_the_catalog_has_none(self) -> None:
        self.assertIsNone(own_catalog(self.map_dir, MODELS))

    def test_a_catalog_of_a_map_that_is_not_packaged_is_given_as_it_is(self) -> None:
        text = self.write(
            '    <!-- kept -->\n    <CModel id="Own">\n        <Model value="Assets\\Skins\\Own.m3" />\n    </CModel>'
        )
        self.assertEqual(own_catalog(self.map_dir, MODELS), text)


class SpellingTest(PackagedCase):
    def test_a_written_catalog_spells_empty_lines_as_the_map_does(self) -> None:
        # The build's checks read catalogs by text (`<Scale value=".."/>`).
        # Found by the hdbake run 2026-11-25: ElementTree's `" />` hid the
        # Command Center's Scale from the hall footprint check.
        self.write(
            '    <CModel id="Own">\n        <Radius value="2"/>\n        <Model value="Assets\\Skins\\Own.m3"/>\n    </CModel>'
        )
        self.models({("Own", "Model"): COPY})
        text = (self.map_dir / GAMEDATA / MODELS).read_text()
        self.assertIn('<Radius value="2"/>', text)
        self.assertIn(f'<Model value="{COPY}"/>', text)
        self.assertNotIn(" />", text, "negative: no line in ElementTree's own spelling")


class TakenBackTest(PackagedCase):
    def test_a_field_that_named_a_file_names_it_again(self) -> None:
        before = self.write(
            '    <CModel id="Own">\n        <Model value="Assets\\Skins\\Own.m3" />\n        <Radius value="2" />\n    </CModel>'
        )
        self.models({("Own", "Model"): COPY})
        self.assertIn(COPY, (self.map_dir / GAMEDATA / MODELS).read_text())
        self.assertEqual(entries(own_catalog(self.map_dir, MODELS)), entries(before))

    def test_a_field_the_entry_did_not_have_goes_and_the_entry_stays(self) -> None:
        before = self.write(
            '    <CModel id="Queen">\n        <Occlusion value="None" />\n    </CModel>'
        )
        self.models({("Queen", "Model"): f"{HD_MODEL_DIR}\\Queen.m3"})
        self.assertEqual(entries(own_catalog(self.map_dir, MODELS)), entries(before))

    def test_a_file_of_the_map_with_the_name_of_the_copy_is_not_taken_for_what_stood_there(
        self,
    ) -> None:
        # The map build writes a model of its own at the game's path. The entry named nothing.
        own = self.map_dir / "Assets" / "Units" / "Zerg" / "Queen" / "Queen.m3"
        own.parent.mkdir(parents=True)
        own.write_text("")
        self.write(
            '    <CModel id="Queen">\n        <Occlusion value="None" />\n    </CModel>'
        )
        self.models({("Queen", "Model"): f"{HD_MODEL_DIR}\\Queen.m3"})
        self.assertIsNone(self.model("Queen"))

    def test_an_entry_the_pack_step_made_goes_and_an_empty_entry_of_the_map_stays(
        self,
    ) -> None:
        before = self.write('    <CModel id="Empty">\n    </CModel>')
        self.models(
            {
                ("Empty", "Model"): f"{HD_MODEL_DIR}\\Empty.m3",
                ("Made", "Model"): f"{HD_MODEL_DIR}\\Made.m3",
            }
        )
        self.assertEqual(entries(own_catalog(self.map_dir, MODELS)), entries(before))

    def test_two_entries_that_show_one_copy_get_each_its_own_back(self) -> None:
        before = self.write(
            '    <CModel id="A">\n        <Model value="Assets\\Skins\\Own.m3" />\n    </CModel>\n'
            '    <CModel id="B">\n        <Model value="Assets\\Deaths\\Own.m3" />\n    </CModel>\n'
            '    <CModel id="C">\n        <Radius value="1" />\n    </CModel>'
        )
        self.models({("A", "Model"): COPY, ("B", "Model"): COPY, ("C", "Model"): COPY})
        self.assertEqual(entries(own_catalog(self.map_dir, MODELS)), entries(before))

    def test_a_catalog_file_the_pack_step_made_is_none_again(self) -> None:
        name_files(
            self.map_dir,
            {
                (TERRAIN, "CTerrainTex"): {
                    ("Grass", "Texture"): GRASS,
                    ("Grass", "Normalmap"): GRASS,
                }
            },
        )
        self.assertTrue((self.map_dir / GAMEDATA / TERRAIN).is_file())
        self.assertIsNone(own_catalog(self.map_dir, TERRAIN))

    def test_a_catalog_the_pack_step_did_not_touch_is_given_as_it_is(self) -> None:
        text = self.write('    <CModel id="Own">\n    </CModel>')
        name_files(
            self.map_dir, {(TERRAIN, "CTerrainTex"): {("Grass", "Texture"): GRASS}}
        )
        self.assertEqual(own_catalog(self.map_dir, MODELS), text)


class RefusalTest(PackagedCase):
    def test_a_folder_is_packaged_once(self) -> None:
        self.write('    <CModel id="Own">\n    </CModel>')
        self.models({("Own", "Model"): COPY})
        with self.assertRaisesRegex(PackagedError, "packaged already"):
            self.models({("Own", "Model"): COPY})
        with self.assertRaisesRegex(PackagedError, "packaged already"):
            require_unpackaged(self.map_dir)

    def test_a_field_is_only_set_to_a_packaged_file(self) -> None:
        with self.assertRaisesRegex(PackagedError, "no packaged file"):
            self.models({("Own", "Model"): "Assets\\Skins\\Own.m3"})
        self.assertFalse((self.map_dir / PRIOR).exists())

    def test_a_packaged_line_without_a_note_is_refused(self) -> None:
        self.write(
            f'    <CModel id="Own">\n        <Model value="{COPY}" />\n    </CModel>'
        )
        with self.assertRaisesRegex(PackagedError, "does not say what stood there"):
            own_catalog(self.map_dir, MODELS)

    def test_a_packaged_line_the_note_does_not_list_is_refused(self) -> None:
        self.write('    <CModel id="Own" />\n    <CModel id="Other" />')
        self.models({("Own", "Model"): COPY})
        path = self.map_dir / GAMEDATA / MODELS
        path.write_text(
            path.read_text().replace(
                '<CModel id="Other"/>',
                f'<CModel id="Other"><Model value="{COPY}" /></CModel>',
            )
        )
        self.assertIn('id="Other"><Model', path.read_text())
        with self.assertRaisesRegex(PackagedError, "does not say what stood there"):
            own_catalog(self.map_dir, MODELS)

    def test_a_noted_entry_that_is_gone_is_refused(self) -> None:
        self.write('    <CModel id="Own">\n    </CModel>')
        self.models({("Own", "Model"): COPY})
        (self.map_dir / GAMEDATA / MODELS).write_text("<Catalog/>")
        with self.assertRaisesRegex(PackagedError, "no CModel Own"):
            own_catalog(self.map_dir, MODELS)

    def test_a_note_of_another_format_is_refused(self) -> None:
        self.write('    <CModel id="Own">\n    </CModel>')
        (self.map_dir / PRIOR).write_text(
            json.dumps({"own.m3": "Assets\\Skins\\Own.m3"})
        )
        with self.assertRaisesRegex(PackagedError, "format"):
            own_catalog(self.map_dir, MODELS)


if __name__ == "__main__":
    unittest.main()
