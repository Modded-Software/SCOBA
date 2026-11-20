"""Host tests for scripts/hdtex/classic_skins.py: which model entries a skin swaps, and how the map takes them."""

from __future__ import annotations

import re
import unittest

from hdtex import classic_skins as C

SKINS = """<Catalog>
<CSkin default="1" id="Base">
    <?token id="unit" type="CUnitLink"?>
    <?token id="collection" value="Bogus"?>
    <ReplacementArray Catalog="Model" From="##unit##" To="##unit##_##collection##"/>
    <ReplacementArray Catalog="Model" From="##unit##Death" To="##unit##_##collection##_Death"/>
    <ReplacementArray Catalog="Sound" From="##unit##_Yes" To="##unit##_##collection##_Yes"/>
</CSkin>
<CSkin default="1" id="BugBase" parent="Base">
    <?token id="unit" type="CUnitLink" value="Bug"?>
    <ReplacementArray Catalog="Model" From="BugNest" To="##unit##_##collection##"/>
</CSkin>
<CSkin id="BugOld" parent="BugBase" collection="Old">
    <ReplacementArray Catalog="Model" From="BugDeath" To="Bug_Old_Splat"/>
</CSkin>
<CSkin id="TankOld" parent="Base" collection="Old" unit="Tank"/>
</Catalog>"""

MODELS = """<Catalog>
<CModel default="1" id="Unit"><Model value="Assets\\Units\\##id##\\##id##.m3"/><Lighting value="##id##"/></CModel>
<CModel default="1" id="BugBase" parent="Unit"><Radius value="0.5"/></CModel>
<CModel default="1" id="BugAnimated" parent="BugBase"><RequiredAnims value="Assets\\Units\\Bug\\Bug.m3a"/></CModel>
<CModel id="Bug" parent="BugAnimated"/>
<CModel id="Bug_Old" parent="BugBase"><EditorCategories value="Skin"/></CModel>
<CModel id="BugNest" parent="BugBase"><Model value="Assets\\Units\\Bug\\Nest.m3"/></CModel>
<CModel id="BugDeath" parent="Unit"/>
<CModel id="Bug_Old_Splat" parent="Unit"><Radius value="2"/><Lighting value="SplatLight"/></CModel>
<CModel id="Tank" parent="Unit"/>
</Catalog>"""

MAP = """<?xml version="1.0" encoding="us-ascii"?>
<Catalog>
    <CModel id="BugNest">
        <ScaleMax value="3"/>
    </CModel>
    <CModel id="Other">
        <Radius value="1"/>
    </CModel>
</Catalog>
"""


def found() -> list[C.Swap]:
    swaps, _left = C.swaps([SKINS], [MODELS], ("BugOld",), frozenset({"SplatLight"}))
    return swaps


class SwapTest(unittest.TestCase):
    def test_a_skin_gives_the_pairs_of_itself_and_its_parents(self) -> None:
        self.assertEqual({swap.entry: swap.shows for swap in found()}, {"Bug": "Bug_Old", "BugDeath": "Bug_Old_Splat", "BugNest": "Bug_Old"})

    def test_the_line_of_the_skin_beats_that_of_its_parent(self) -> None:
        death = next(swap for swap in found() if swap.entry == "BugDeath")
        self.assertEqual(death.shows, "Bug_Old_Splat")

    def test_an_entry_takes_the_model_file_and_the_other_fields_that_differ(self) -> None:
        death = next(swap for swap in found() if swap.entry == "BugDeath")
        self.assertEqual(dict(death.fields), {"Lighting": "SplatLight", "Model": "Assets\\Units\\Bug_Old_Splat\\Bug_Old_Splat.m3", "Radius": "2"})

    def test_a_light_the_game_does_not_have_is_not_named(self) -> None:
        bug = next(swap for swap in found() if swap.entry == "Bug")
        self.assertEqual(dict(bug.fields), {"Model": "Assets\\Units\\Bug_Old\\Bug_Old.m3"})

    def test_animations_of_the_other_skeleton_are_removed(self) -> None:
        bug = next(swap for swap in found() if swap.entry == "Bug")
        self.assertEqual(bug.removed, ("RequiredAnims",))
        self.assertEqual(next(swap for swap in found() if swap.entry == "BugNest").removed, ())

    def test_replacements_of_other_catalogs_are_not_followed(self) -> None:
        self.assertNotIn("Bug_Yes", [swap.entry for swap in found()])

    def test_a_pair_the_game_data_lacks_is_left_out_and_reported(self) -> None:
        swaps, left = C.swaps([SKINS], [MODELS], ("TankOld",))
        self.assertEqual(swaps, [])
        self.assertEqual(left, ["TankOld: Tank -> Tank_Old", "TankOld: TankDeath -> Tank_Old_Death"])

    def test_an_unknown_skin_is_an_error(self) -> None:
        with self.assertRaises(C.SkinError):
            C.swaps([SKINS], [MODELS], ("Ghost",))

    def test_only_the_entries_of_one_class_are_read(self) -> None:
        mixed = '<Catalog><CUnit id="Bug"/><CModel id="Bug"><Radius value="1"/></CModel></Catalog>'
        (text,) = C.class_text([mixed], "CModel")
        self.assertIn("CModel", text)
        self.assertNotIn("CUnit", text)


class MergeTest(unittest.TestCase):
    def test_an_entry_of_the_map_takes_the_lines_and_keeps_its_own(self) -> None:
        text = C.merged(MAP, found())
        self.assertEqual(len(re.findall(r'<CModel id="BugNest">', text)), 1)
        body = re.search(r'<CModel id="BugNest">(.*?)</CModel>', text, re.DOTALL).group(1)
        self.assertIn('<Model value="Assets\\Units\\Bug_Old\\Bug_Old.m3"/>', body)
        self.assertIn('<ScaleMax value="3"/>', body)

    def test_the_other_entries_go_into_the_marked_block(self) -> None:
        text = C.merged(MAP, found())
        block = text[text.index(C.BEGIN) : text.index(C.END)]
        self.assertIn('<CModel id="Bug">', block)
        self.assertIn('<RequiredAnims index="0" removed="1"/>', block)
        self.assertNotIn("BugNest", block)
        self.assertTrue(text.rstrip().endswith("</Catalog>"))

    def test_a_second_run_changes_nothing_and_no_swaps_gives_the_map_back(self) -> None:
        once = C.merged(MAP, found())
        self.assertEqual(C.merged(once, found()), once)
        self.assertEqual(C.stripped(once), MAP)
        self.assertNotIn("Bug_Old", C.merged(once, []))

    def test_a_field_the_map_sets_itself_is_a_clash(self) -> None:
        own = MAP.replace('<ScaleMax value="3"/>', '<Model value="Assets\\Mine.m3"/>')
        self.assertEqual(C.clashes(own, found()), ["BugNest: the map sets Model itself"])
        self.assertEqual(C.clashes(C.merged(MAP, found()), found()), [])


class MapDataTest(unittest.TestCase):
    """The lines in the map's own ModelData.xml."""

    def setUp(self) -> None:
        self.text = (C.MAP / C.MODEL_DATA).read_text(encoding="utf-8-sig")

    def models(self) -> dict[str, str]:
        written = self.text[self.text.index(C.BEGIN) : self.text.index(C.END)]
        written += "".join(re.findall(r'<CModel id="[^"]+">\n(?:[^\n]*' + re.escape(C.LINE_MARK) + r"\n)+", self.text))
        return dict(re.findall(r'<CModel id="([^"]+)">.*?<Model value="([^"]+)"/>', written, re.DOTALL))

    def test_the_units_show_their_classic_models(self) -> None:
        models = self.models()
        for unit in ("Marine", "SCV", "Battlecruiser", "Hydralisk", "Ultralisk", "Drone", "Hatchery", "Lair", "Hive", "CommandCenter"):
            self.assertIn("_Remastered", models[unit], unit)

    def test_the_command_center_shows_its_classic_model(self) -> None:
        models = self.models()
        self.assertIn("CommandCenter_Remastered", models["CommandCenter"])
        for entry in ("OrbitalCommandDeath", "OrbitalCommandFlyDeath", "PlanetaryFortressDeath"):
            self.assertIn("_Remastered", models[entry], entry)

    def test_no_entry_stands_twice(self) -> None:
        ids = re.findall(r'<CModel id="([^"]+)"', self.text)
        self.assertEqual(sorted(ids), sorted(set(ids)))
