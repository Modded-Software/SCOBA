"""Host tests of the hit-volume data pipeline: stock unit list, actor and
model resolution, the stale check (fresh.py), and the m3 worker pool."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hdtex.sc2.packaged import HD_MODEL_DIR, name_files
from hitvolumes import fresh, galaxy, measure
from hitvolumes.resolve import STACK, Catalog, GameData
from hitvolumes.units import concrete

ROOT = Path(__file__).resolve().parents[4]
TOSH = ROOT / "src" / "SCOBA.SC2Map" / "Assets" / "Units" / "Terran" / "Tosh" / "ToshSCOBA.m3"

STOCK_UNITS = """<Catalog>
    <CUnit default="1" id="MISSILE"><FlagArray index="Missile" value="1"/></CUnit>
    <CUnit default="1" id="Base"/>
    <CUnit id="Bolt" parent="MISSILE"/>
    <CUnit id="Marine" parent="Base"/>
    <CUnit id="Shell" parent="MISSILE"><FlagArray index="Missile" value="0"/></CUnit>
</Catalog>"""

STOCK_ACTORS = """<Catalog>
    <CActorUnit id="Marine"><Model value="Marine"/></CActorUnit>
    <CActorUnit id="Archive"><On Terms="UnitBirth.ArchiveSealed" Send="Create"/></CActorUnit>
    <CActorMissile id="Dehaka"><Model value="Marine"/></CActorMissile>
    <CActorUnit id="Egg"><Model value="Egg"/></CActorUnit>
    <CActorUnit id="Baneling"><On Terms="AbilMorph.*.Finish; MorphTo BanelingBurrowed" Send="AnimClear"/></CActorUnit>
</Catalog>"""

STOCK_MODELS = """<Catalog>
    <CModel id="Marine"><Model value="Assets\\Units\\Marine\\Marine.m3"/></CModel>
    <CModel id="Archive"><Model value="Assets\\Archive.m3"/></CModel>
    <CModel id="Egg"><Model value="Assets\\Egg\\Egg.m3"/><VariationCount value="3"/></CModel>
</Catalog>"""

MAP_ACTORS = """<Catalog>
    <!-- a comment -->
    <CActorUnit id="Marine"><Scale value="1.25"/></CActorUnit>
</Catalog>"""

MAP_MODELS = """<Catalog>
    <CModel id="Marine"><Model value="Assets\\Models\\hd\\Marine.m3"/></CModel>
</Catalog>"""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def stock_tree(root: Path) -> Path:
    data = root / "stock" / Path(*STACK[1].split("/")) / "base.sc2data" / "gamedata"
    write(data / "unitdata.xml", STOCK_UNITS)
    write(data / "actordata.xml", STOCK_ACTORS)
    write(data / "modeldata.xml", STOCK_MODELS)
    return root / "stock"


def map_tree(root: Path, actors: str = MAP_ACTORS, units: str = "<Catalog/>") -> Path:
    m = root / "map"
    write(m / "Base.SC2Data" / "GameData" / "ActorData.xml", actors)
    write(m / "Base.SC2Data" / "GameData" / "ModelData.xml", MAP_MODELS)
    write(m / "Base.SC2Data" / "GameData" / "UnitData.xml", units)
    write(m / "Objects", "<PlacedObjects/>")
    write(m / "scripts" / "app" / "x.galaxy", 'UnitCreate(1, "Marine", 0, 1, p, 0.0);\n')
    write(m / "Assets" / "Models" / "hd" / "Marine.m3", "model bytes v1")
    return m


def packaged_map(map_dir: Path) -> None:
    """What the HD texture step leaves in a map: copies of the models of Marine and Egg, the lines that name them,
    and its note of what the lines replaced."""
    for name in ("Marine.m3", "Egg.m3", "Egg_00.m3"):
        write(map_dir.joinpath(*HD_MODEL_DIR.split("\\")) / name, "the copy")
    name_files(map_dir, {("ModelData.xml", "CModel"): {("Marine", "Model"): f"{HD_MODEL_DIR}\\Marine.m3", ("Egg", "Model"): f"{HD_MODEL_DIR}\\Egg.m3"}})


def actor_baked_map(map_dir: Path) -> None:
    """What a unit bake of Marine leaves: a copy for its actor, a made entry, and the actor's Model naming it."""
    write(map_dir.joinpath(*HD_MODEL_DIR.split("\\")) / "Marine" / "Marine.m3", "the copy")
    name_files(
        map_dir,
        {
            ("ModelData.xml", "CModel"): {("Marine_hd_Marine", "Model"): f"{HD_MODEL_DIR}\\Marine\\Marine.m3"},
            ("ActorData.xml", "CActorUnit"): {("Marine", "Model"): "Marine_hd_Marine"},
        },
        {("ModelData.xml", "CModel"): {"Marine_hd_Marine": "Marine"}},
    )


class StockUnitTests(unittest.TestCase):
    def test_templates_and_missiles_are_left_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stock = stock_tree(Path(tmp))
            path = stock / Path(*STACK[1].split("/")) / "base.sc2data" / "gamedata" / "unitdata.xml"
            got = concrete(Catalog([path], ("CUnit",)))
        # Shell turns its inherited missile flag off: it is a unit.
        self.assertEqual(got, ["Marine", "Shell"])
        # Negative: the template and the missile are not listed.
        self.assertNotIn("Base", got)
        self.assertNotIn("Bolt", got)


class ResolveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.data = GameData(stock_tree(root), map_tree(root))

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_map_wins_and_chains_are_kept(self) -> None:
        res = self.data.resolve("Marine")
        self.assertEqual(res.m3, "Assets\\Models\\hd\\Marine.m3")
        self.assertEqual(res.actor_scale, (1.25, 1.25, 1.25))
        self.assertEqual(res.actors, ("Marine",))
        self.assertEqual(res.models, ("Marine",))

    def test_a_packaged_copy_resolves_to_the_model_it_was_made_from(self) -> None:
        root = Path(self.tmp.name) / "packaged"
        packaged_map(map_tree(root))
        data = GameData(stock_tree(root), root / "map")
        self.assertEqual(data.resolve("Marine").m3, "Assets\\Models\\hd\\Marine.m3", "the map's own model, not its copy")
        self.assertEqual(data.resolve("Egg").files(), ["Assets\\Egg\\Egg.m3", "Assets\\Egg\\Egg_00.m3"], "the stock model")
        self.assertEqual(data.resolve("Egg").models, ("Egg",))

    def test_a_unit_bake_resolves_to_the_model_the_actor_showed_before(self) -> None:
        root = Path(self.tmp.name) / "baked"
        actor_baked_map(map_tree(root))
        data = GameData(stock_tree(root), root / "map")
        res = data.resolve("Marine")
        self.assertEqual(res.m3, "Assets\\Models\\hd\\Marine.m3", "the map's own model, not the actor's copy")
        self.assertEqual(res.models, ("Marine",), "negative: not the made entry")
        self.assertEqual(res.actor_scale, (1.25, 1.25, 1.25), "the map's own actor line stays")

    def test_birth_create_and_missile_actor(self) -> None:
        self.assertEqual(self.data.actor_for("ArchiveSealed"), "Archive")
        self.assertEqual(self.data.actor_for("Dehaka"), "Dehaka")
        # Negative: a morph state has no actor; only the reason knows its source.
        self.assertIsNone(self.data.actor_for("BanelingBurrowed"))
        self.assertEqual(self.data.by_morph["BanelingBurrowed"], "Baneling")

    def test_variation_files(self) -> None:
        res = self.data.resolve("Egg")
        self.assertEqual(res.files(), ["Assets\\Egg\\Egg.m3", "Assets\\Egg\\Egg_00.m3"])
        # Negative: a model without variations has one file.
        self.assertEqual(self.data.resolve("Marine").files(), ["Assets\\Models\\hd\\Marine.m3"])


class FreshTests(unittest.TestCase):
    """A measured record stays fresh until the map changes one of its inputs."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.harness = self.root / "harness"
        self.harness.mkdir()
        self.map = map_tree(self.root)
        rec = {"source": "fuzzy", "m3": "Assets\\Models\\hd\\Marine.m3", "files": ["Assets\\Models\\hd\\Marine.m3"],
               "actors": ["Marine"], "models": ["Marine"]}
        rec["inputs"] = fresh.MapInputs(self.map).key("Marine", rec)
        self.data = {"units": {"Marine": rec}}

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def problems(self) -> list[str]:
        return fresh.problems(self.map, self.data, self.harness)

    def test_unchanged_map_is_fresh(self) -> None:
        self.assertEqual(self.problems(), [])

    def test_comment_edit_stays_fresh(self) -> None:
        write(self.map / "Base.SC2Data" / "GameData" / "ActorData.xml", MAP_ACTORS.replace("a comment", "another"))
        self.assertEqual(self.problems(), [])

    def test_changed_model_path_is_stale(self) -> None:
        write(self.map / "Base.SC2Data" / "GameData" / "ModelData.xml", MAP_MODELS.replace("hd", "sd"))
        self.assertIn("Marine changed in the map", "\n".join(self.problems()))

    def test_changed_scale_is_stale(self) -> None:
        write(self.map / "Base.SC2Data" / "GameData" / "ActorData.xml", MAP_ACTORS.replace("1.25", "2.0"))
        self.assertIn("Marine changed in the map", "\n".join(self.problems()))

    def test_changed_m3_bytes_are_stale(self) -> None:
        write(self.map / "Assets" / "Models" / "hd" / "Marine.m3", "model bytes v2")
        self.assertIn("Marine changed in the map", "\n".join(self.problems()))

    def test_new_claiming_actor_is_stale(self) -> None:
        extra = MAP_ACTORS.replace("</Catalog>", '<CActorUnit id="Other" unitName="Marine"/></Catalog>')
        write(self.map / "Base.SC2Data" / "GameData" / "ActorData.xml", extra)
        self.assertIn("Marine changed in the map", "\n".join(self.problems()))

    def test_what_the_texture_step_packages_stays_fresh(self) -> None:
        packaged_map(self.map)
        self.assertEqual(self.problems(), [])
        # The copy is not an input: the game shows it, but its shapes are those of the original.
        write(self.map / "Assets" / "Models" / "scoba_hd" / "Marine.m3", "another copy")
        self.assertEqual(self.problems(), [])

    def test_a_copy_for_an_entry_of_the_map_that_named_no_model_stays_fresh(self) -> None:
        # The map build writes a model of its own at the game's path. The map's entry names no model.
        entry = '<CModel id="Egg"><Occlusion value="None"/></CModel>'
        write(self.map / "Base.SC2Data" / "GameData" / "ModelData.xml", MAP_MODELS.replace("</Catalog>", f"{entry}</Catalog>"))
        write(self.map / "Assets" / "Egg" / "Egg.m3", "the map's egg")
        rec = {"source": "fuzzy", "m3": "Assets\\Egg\\Egg.m3", "files": ["Assets\\Egg\\Egg.m3"], "actors": ["Egg"], "models": ["Egg"]}
        rec["inputs"] = fresh.MapInputs(self.map).key("Egg", rec)
        self.data["units"]["Egg"] = rec
        packaged_map(self.map)
        self.assertEqual(self.problems(), [])
        # Negative: the map's own model is still an input.
        write(self.map / "Assets" / "Egg" / "Egg.m3", "another egg")
        self.assertIn("Egg changed in the map", "\n".join(self.problems()))

    def test_a_unit_bake_of_the_texture_step_stays_fresh(self) -> None:
        # Found by the hdbake run 2026-11-25: the actor's Model line and the
        # made entry of a unit bake (hdtex.sc2.owned) made Marauder stale.
        actor_baked_map(self.map)
        self.assertIn("Marine_hd_Marine", (self.map / "Base.SC2Data" / "GameData" / "ActorData.xml").read_text())
        self.assertEqual(self.problems(), [])
        # Negative: an edit of the map's own actor line is still seen.
        path = self.map / "Base.SC2Data" / "GameData" / "ActorData.xml"
        path.write_text(path.read_text().replace('"1.25"', '"2.0"'))
        self.assertIn("Marine changed in the map", "\n".join(self.problems()))

    def test_a_changed_original_is_stale_with_a_copy_in_the_map(self) -> None:
        packaged_map(self.map)
        write(self.map / "Assets" / "Models" / "hd" / "Marine.m3", "model bytes v2")
        self.assertIn("Marine changed in the map", "\n".join(self.problems()))

    def test_another_layout_of_the_catalog_stays_fresh(self) -> None:
        write(self.map / "Base.SC2Data" / "GameData" / "ModelData.xml", MAP_MODELS.replace("><", ">\n\t\t<"))
        self.assertEqual(self.problems(), [])

    def test_unmeasured_map_type_fails(self) -> None:
        write(self.map / "Base.SC2Data" / "GameData" / "UnitData.xml", '<Catalog><CUnit id="SCOBANew"/></Catalog>')
        self.assertIn("unit type SCOBANew is not measured", "\n".join(self.problems()))

    def test_record_without_key_fails(self) -> None:
        del self.data["units"]["Marine"]["inputs"]
        self.assertIn("Marine has no input key", "\n".join(self.problems()))


class MeasureTests(unittest.TestCase):
    def test_suffix_index(self) -> None:
        index = measure.suffix_index(["mods\\b.sc2mod\\base.sc2assets\\Assets\\X\\X.m3", "mods\\a.sc2mod\\base.sc2assets\\assets\\x\\x.m3"])
        # Two stored copies: the first in sort order wins.
        self.assertEqual(index["assets\\x\\x.m3"], "mods\\a.sc2mod\\base.sc2assets\\assets\\x\\x.m3")
        # Negative: a suffix that does not start after a backslash is absent.
        self.assertNotIn("ssets\\x\\x.m3", index)

    def test_pool_equals_serial(self) -> None:
        files = {str(TOSH): [(1.0, 1.0, 1.0), (2.0, 2.0, 2.0)]}
        serial = measure.shapes_by_file(files, 1)
        pooled = measure.shapes_by_file(files, 2)
        self.assertEqual(json.dumps(serial[(str(TOSH), (2.0, 2.0, 2.0))]), json.dumps(pooled[(str(TOSH), (2.0, 2.0, 2.0))]))
        self.assertNotEqual(serial[(str(TOSH), (1.0, 1.0, 1.0))], serial[(str(TOSH), (2.0, 2.0, 2.0))])

    def test_unreadable_file_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.m3"
            bad.write_bytes(b"not an m3")
            got = measure.shapes_by_file({str(bad): [(1.0, 1.0, 1.0)]}, 1)[(str(bad), (1.0, 1.0, 1.0))]
        self.assertIsInstance(got, measure.Unreadable)


class CommittedDataTests(unittest.TestCase):
    def test_classic_and_ai_types_have_volumes(self) -> None:
        units = galaxy.load_json()["units"]
        for name in ("SCV", "Marine", "Drone", "Larva", "Egg", "MULE", "SpawningPool", "Dehaka", "ArchiveSealed"):
            self.assertTrue(units[name].get("shapes"), name)
        self.assertIn("_Remastered", units["SCV"]["m3"])
        # Negative: a morph state carries a reason, not a guessed volume.
        self.assertEqual(units["BanelingBurrowed"]["source"], "none")
        self.assertIn("morph state", units["BanelingBurrowed"]["reason"])

    def test_every_record_has_an_input_key(self) -> None:
        missing = [n for n, rec in galaxy.load_json()["units"].items() if "inputs" not in rec]
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
