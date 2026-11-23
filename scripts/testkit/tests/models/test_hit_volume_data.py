"""Host tests of the hit-volume data pipeline: stock unit list, actor and
model resolution, the stale check (fresh.py), and the m3 worker pool."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

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
