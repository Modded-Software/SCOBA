"""SC2 owners and their bakes: model files, actors, units; copies that change one owner only (R-HD-130, R-HD-141 to 144).

These are host tests of what the package writes. Whether the game shows a
made entry as it shows the stock one (E-1, E-2) needs a game run.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from hdtex.core import package, requests, skins
from hdtex.sc2.packaged import HD_DIR, HD_MODEL_DIR
from hdtex.sc2.storage import GAP_ACTORS

from testkit.tests.textures.sc2_fixtures import (
    GAMEDATA,
    PLACED,
    TEXTURES,
    PackCase,
    model_layers,
    objects,
)

ROCK_MODEL = "model:assets\\doodads\\rock\\rock.m3"
TREE_MODEL = "model:assets\\doodads\\tree\\tree.m3"
SPEC = TEXTURES + "rock_spec.dds"
NORMAL = TEXTURES + "rock_normal.dds"
FAST = "fast@256"
UNITS = '<Catalog><CUnit id="Guard"/></Catalog>'


class OwnerCase(PackCase):
    def setUp(self) -> None:
        super().setUp()
        self.casc.files[GAMEDATA + "unitdata.xml"] = UNITS.encode()
        (self.map_dir / "Objects").write_text(objects(PLACED, ("Guard",)))

    def made(self, *assets: str) -> None:
        found = self.dataset()
        for asset in assets:
            requests.make(
                found,
                self.runner,
                found.texture(asset),
                FAST,
                wait=lambda _seconds: None,
            )

    def bake(self, owner: str, textures: dict[str, str]) -> None:
        found = self.dataset()
        found.change_skin(
            owner, lambda now: skins.copied(now, skins.ORIGINAL_SKIN, "hd")
        )
        for asset, variant in textures.items():
            found.set_texture(owner, "hd", asset, variant)
        found.bake(owner, "hd")

    def node(self, catalog: str, element: str, entry: str) -> ET.Element | None:
        path = self.map_dir / "Base.SC2Data" / "GameData" / catalog
        if not path.is_file():
            return None
        return next(
            (
                item
                for item in ET.parse(path).getroot().iter(element)
                if item.get("id") == entry
            ),
            None,
        )

    def paths(self, copy: str) -> list[str]:
        return [item["path"] for item in model_layers(self.map_file(copy).read_bytes())]


class ListTest(OwnerCase):
    def test_models_actors_and_units_are_owners_each_with_the_layers_below(
        self,
    ) -> None:
        owners = self.dataset().owners
        self.assertEqual(owners["actor:Rock"].below, (ROCK_MODEL,))
        self.assertEqual(owners["actor:Tree"].below, (TREE_MODEL,))
        self.assertEqual(
            owners["unit:Guard"].below,
            ("actor:Guard", ROCK_MODEL),
            "a unit shows its actor, then the actor's model",
        )
        self.assertLessEqual({SPEC, NORMAL}, set(owners[ROCK_MODEL].textures))
        self.assertEqual(owners["actor:Rock"].textures, owners[ROCK_MODEL].textures)
        self.assertEqual(owners["unit:Guard"].textures, owners[ROCK_MODEL].textures)
        self.assertNotIn(
            SPEC,
            owners["actor:Tree"].textures,
            "negative: another model's textures are not the actor's",
        )
        self.assertEqual([owner.layer for owner in owners.values()].count("unit"), 1)

    def test_a_unit_and_a_doodad_the_map_does_not_place_are_owners(self) -> None:
        # The viewer lists every unit and doodad of the dataset; each can get a
        # skin, placed or not (operator 2026-11-25).
        (self.map_dir / "Objects").write_text(objects(("Tree",)))
        owners = self.dataset().owners
        self.assertEqual(
            owners["unit:Guard"].below, ("actor:Guard", ROCK_MODEL), "unplaced unit"
        )
        self.assertEqual(owners["actor:Rock"].below, (ROCK_MODEL,), "unplaced doodad")

    def test_an_id_in_no_catalog_or_without_a_model_file_is_no_owner(self) -> None:
        own = self.map_dir / "Base.SC2Data" / "GameData" / "ActorData.xml"
        own.parent.mkdir(parents=True, exist_ok=True)
        own.write_text(
            '<Catalog><CActorDoodad id="Bare"><Model value="NoSuchModel"/></CActorDoodad></Catalog>'
        )
        owners = self.dataset().owners
        self.assertNotIn("unit:Nobody", owners, "negative: in no catalog")
        self.assertNotIn("actor:Bare", owners, "negative: its model has no entry")
        self.assertIn("actor:Mist", owners, "an unplaced doodad with a model file")
        self.assertEqual(
            sorted(name for name in owners if name.startswith("unit:")),
            ["unit:Guard"],
            "negative: the units are those of the catalog, no other",
        )

    def test_an_actor_whose_model_cannot_be_read_is_listed_as_a_gap(self) -> None:
        # Stock data has two actors whose parent is in no catalog. They own
        # nothing, and the gaps name each with the reason.
        own = self.map_dir / "Base.SC2Data" / "GameData" / "ActorData.xml"
        own.parent.mkdir(parents=True, exist_ok=True)
        own.write_text(
            '<Catalog><CActorUnit id="Orphan" parent="NoSuchParent"/></Catalog>'
        )
        found = self.dataset()
        self.assertNotIn("actor:Orphan", found.owners, "negative: it owns nothing")
        gaps = found.adapter.gaps(found.name)
        self.assertEqual(
            gaps[GAP_ACTORS],
            ["Orphan: parent NoSuchParent is not in the catalog"],
        )
        self.assertIn("actor:Rock", found.owners, "negative: the others stay owners")

    def test_a_model_bake_reaches_the_map_only_where_the_map_shows_the_model(
        self,
    ) -> None:
        # R-HD-54: the package copies the models the map shows, no other.
        self.made(SPEC)
        self.bake(ROCK_MODEL, {SPEC: FAST})
        (self.map_dir / "Objects").write_text(objects(("Tree",)))
        package.package(self.dataset(), self.map_dir)
        # The shown case: ActorBakeTest.test_a_model_bake_reaches_every_actor_and_unit_that_shows_the_model.
        self.assertFalse(
            self.map_file(f"{HD_MODEL_DIR}\\Rock.m3").exists(),
            "negative: Rock is not shown, so no copy",
        )

    def test_an_unplaced_owner_without_a_bake_adds_nothing_to_the_map(self) -> None:
        (self.map_dir / "Objects").write_text(objects(("Tree",)))
        package.package(self.dataset(), self.map_dir)
        self.assertIsNone(self.node("ActorData.xml", "CActorUnit", "Guard"))
        self.assertIsNone(self.node("ActorData.xml", "CActorDoodad", "Rock"))
        self.assertIsNone(self.node("ModelData.xml", "CModel", "Rock_hd_Guard"))
        self.assertFalse(self.map_file(f"{HD_MODEL_DIR}\\Guard\\Rock.m3").exists())


class ActorBakeTest(OwnerCase):
    def test_an_actor_bake_makes_a_model_entry_of_its_own_and_changes_that_actor_only(
        self,
    ) -> None:
        self.made(SPEC)
        self.bake("actor:Rock", {SPEC: FAST})
        package.package(self.dataset(), self.map_dir)
        copy = f"{HD_MODEL_DIR}\\Rock\\Rock.m3"
        entry = self.node("ModelData.xml", "CModel", "Rock_hd_Rock")
        self.assertIsNotNone(entry)
        self.assertEqual(
            (entry.get("parent"), entry.find("Model").get("value")), ("Rock", copy)
        )
        self.assertEqual(
            self.value("ActorData.xml", "CActorDoodad", "Rock", "Model"), "Rock_hd_Rock"
        )
        layers = self.paths(copy)
        self.assertTrue(
            layers[0].startswith(HD_DIR + "\\") and "rock_spec" in layers[0], layers
        )
        self.assertEqual(
            layers[1],
            "Assets\\Textures\\rock_normal.dds",
            "a texture the bake does not name stays",
        )
        self.assertIsNone(
            self.value("ModelData.xml", "CModel", "Rock", "Model"),
            "negative: the model entry itself is unchanged",
        )
        self.assertIsNone(
            self.value("ActorData.xml", "CActorUnit", "Guard", "Model"),
            "negative: another actor of the same model is unchanged",
        )
        self.assertFalse(
            self.map_file(f"{HD_MODEL_DIR}\\Rock.m3").exists(),
            "negative: no model-level copy",
        )

    def test_an_actor_bake_that_shows_what_its_model_shows_makes_nothing(self) -> None:
        self.made(SPEC)
        self.bake(ROCK_MODEL, {SPEC: FAST})
        self.bake("actor:Rock", {SPEC: FAST})
        package.package(self.dataset(), self.map_dir)
        self.assertIsNone(self.node("ModelData.xml", "CModel", "Rock_hd_Rock"))
        self.assertIsNone(self.node("ActorData.xml", "CActorDoodad", "Rock"))
        self.assertFalse(self.map_file(f"{HD_MODEL_DIR}\\Rock\\Rock.m3").exists())
        self.assertTrue(
            self.map_file(f"{HD_MODEL_DIR}\\Rock.m3").is_file(),
            "the model's own bake is there",
        )

    def test_a_model_bake_reaches_every_actor_and_unit_that_shows_the_model(
        self,
    ) -> None:
        self.made(SPEC)
        self.bake(ROCK_MODEL, {SPEC: FAST})
        package.package(self.dataset(), self.map_dir)
        self.assertEqual(
            self.value("ModelData.xml", "CModel", "Rock", "Model"),
            f"{HD_MODEL_DIR}\\Rock.m3",
        )
        self.assertIsNone(
            self.node("ActorData.xml", "CActorDoodad", "Rock"),
            "the actor names the entry as before",
        )


class UnitBakeTest(OwnerCase):
    def test_a_unit_bake_copies_its_actors_model_and_changes_that_unit_only(
        self,
    ) -> None:
        self.made(NORMAL)
        self.bake("unit:Guard", {NORMAL: FAST})
        package.package(self.dataset(), self.map_dir)
        copy = f"{HD_MODEL_DIR}\\Guard\\Rock.m3"
        entry = self.node("ModelData.xml", "CModel", "Rock_hd_Guard")
        self.assertEqual(
            (entry.get("parent"), entry.find("Model").get("value")), ("Rock", copy)
        )
        self.assertEqual(
            self.value("ActorData.xml", "CActorUnit", "Guard", "Model"), "Rock_hd_Guard"
        )
        self.assertIn("rock_normal", self.paths(copy)[1])
        self.assertIsNone(
            self.value("ActorData.xml", "CActorDoodad", "Rock", "Model"),
            "negative: the doodad of the same model is unchanged",
        )

    def test_a_unit_bake_goes_over_its_actors_bake(self) -> None:
        # Operator 2026-11-25: a texture a skin does not name shows its
        # original, baked too. The unit's skin names one original; the bake
        # names the original for the rest, over the actor's variants.
        self.made(SPEC, NORMAL)
        self.bake("actor:Guard", {SPEC: FAST, NORMAL: FAST})
        self.dataset().change_skin(
            "unit:Guard", lambda now: skins.copied(now, skins.ORIGINAL_SKIN, "hd")
        )
        self.dataset().set_texture("unit:Guard", "hd", NORMAL, "original")
        baked = self.dataset().bake("unit:Guard", "hd")
        self.assertEqual(baked.textures[SPEC], "original", baked.textures)
        package.package(self.dataset(), self.map_dir)
        self.assertFalse(
            self.map_file(f"{HD_MODEL_DIR}\\Guard\\Rock.m3").exists(),
            "every texture is its original: no copy",
        )
        self.assertFalse(
            self.map_file("Base.SC2Data\\GameData\\ActorData.xml").exists(),
            "the unit's actor keeps the stock model: no actor data is written",
        )

    def test_a_unit_bake_of_originals_over_a_model_bake_makes_a_copy(self) -> None:
        # Found in game run hdbake 2026-11-25: such a bake was taken for one
        # that changes nothing, and the unit kept the model's variant.
        self.made(SPEC)
        self.bake(ROCK_MODEL, {SPEC: FAST})
        self.bake("unit:Guard", {SPEC: "original"})
        package.package(self.dataset(), self.map_dir)
        copy = f"{HD_MODEL_DIR}\\Guard\\Rock.m3"
        self.assertEqual(
            self.value("ActorData.xml", "CActorUnit", "Guard", "Model"), "Rock_hd_Guard"
        )
        self.assertEqual(
            self.paths(copy)[0],
            "Assets\\Textures\\rock_spec.dds",
            "the unit shows the original, not the model's variant",
        )
        self.assertTrue(
            self.paths(f"{HD_MODEL_DIR}\\Rock.m3")[0].startswith(HD_DIR + "\\"),
            "negative: the model's own copy still shows its variant",
        )

    def test_a_unit_bake_of_originals_over_no_bake_makes_nothing(self) -> None:
        self.made(SPEC)
        self.bake("unit:Guard", {SPEC: "original"})
        package.package(self.dataset(), self.map_dir)
        self.assertIsNone(self.node("ModelData.xml", "CModel", "Rock_hd_Guard"))
        self.assertFalse(self.map_file(f"{HD_MODEL_DIR}\\Guard\\Rock.m3").exists())
