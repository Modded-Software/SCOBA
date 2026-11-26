"""The skin files and the bake file: names, round trips, refusals with the place of the fault (R-HD-130 to 136, R-HD-140)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hdtex import core
from hdtex.core import bakes, skins
from hdtex.core.bakes import Bake, BakeError, Bakes
from hdtex.core.skins import Skin, SkinError
from hdtex.core.store import StoreError

ROCK = "assets\\textures\\rock.dds"
OWNER = "model:Assets\\Models\\Rock\\Rock.m3"


class FolderCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)


class SkinFileTest(FolderCase):
    def test_a_skin_file_is_named_by_the_owner_readably_and_by_its_hash(self) -> None:
        path = skins.file_of(self.folder, OWNER)
        self.assertEqual(path.parent, self.folder / skins.FOLDER)
        self.assertRegex(path.name, r"^model-rock\.m3-[0-9a-f]{16}\.json$")
        self.assertNotEqual(
            path, skins.file_of(self.folder, "model:Assets\\Other\\Rock.m3")
        )

    def test_skins_come_back_as_they_were_saved_and_none_leave_no_file(self) -> None:
        found = {
            "hd": Skin("hd", {ROCK: "pbrify@2048"}),
            "seed": Skin("seed", {ROCK: "pbrify@2048+seedvr2@4096"}),
        }
        skins.save(self.folder, OWNER, found)
        self.assertEqual(skins.load(self.folder, OWNER), found)
        self.assertEqual(skins.owners(self.folder), [OWNER])
        skins.save(self.folder, OWNER, {})
        self.assertFalse(skins.file_of(self.folder, OWNER).exists())
        self.assertEqual(skins.load(self.folder, OWNER), {})

    def test_a_faulty_skin_file_is_refused_with_the_place_of_the_fault(self) -> None:
        good = {
            "format": skins.FORMAT,
            "owner": OWNER,
            "skins": {"hd": {"textures": {ROCK: "pbrify@2048"}}},
        }
        path = skins.file_of(self.folder, OWNER)
        path.parent.mkdir(parents=True)
        for word, value in (
            ("not a skin file", {**good, "owner": "model:other"}),
            ("not a skin file", {**good, "format": 2}),
            ("extra: unknown key", {**good, "extra": 1}),
            (
                "skins.hd.size: unknown key",
                {**good, "skins": {"hd": {"textures": {}, "size": 1}}},
            ),
            (
                f"skins.hd.textures.{ROCK}",
                {**good, "skins": {"hd": {"textures": {ROCK: "upscale"}}}},
            ),
            ("names nothing", {**good, "skins": {"original": {"textures": {}}}}),
            # Negative: a skin names no other skin.
            ("skins.hd.from: unknown key", {**good, "skins": {"hd": {"from": "original", "textures": {}}}}),
            ("skins.hd.textures: missing", {**good, "skins": {"hd": {}}}),
            ("skins: missing", {"format": skins.FORMAT, "owner": OWNER}),
        ):
            path.write_text(json.dumps(value))
            with self.assertRaises(SkinError, msg=word) as refused:
                skins.load(self.folder, OWNER)
            self.assertIn(word, str(refused.exception))
            self.assertIn(str(path), str(refused.exception))

    def test_a_skin_file_with_a_name_twice_is_refused(self) -> None:
        path = skins.file_of(self.folder, OWNER)
        path.parent.mkdir(parents=True)
        head = f'{{"format": {skins.FORMAT}, "owner": {json.dumps(OWNER)}, "skins": '
        for word, text in (
            ("the key 'hd' is given twice", head + '{"hd": {"textures": {}}, "hd": {"textures": {}}}}'),
            ("there is a skin 'hd' already", head + '{"hd": {"textures": {}}, "HD": {"textures": {}}}}'),
        ):
            path.write_text(text)
            with self.assertRaises((SkinError, StoreError), msg=word) as refused:
                skins.load(self.folder, OWNER)
            self.assertIn(word, str(refused.exception))
            self.assertIn(str(path), str(refused.exception))

    def test_an_owner_and_a_name_are_checked(self) -> None:
        for owner in ("rock", "doodad:x", "model:", ""):
            with self.assertRaises(SkinError, msg=owner):
                skins.check_owner(owner)
        # The names table of hdtex.core; the viewer's check is tested against it too.
        table = json.loads(Path(core.__file__).with_name("skin_names.json").read_text(encoding="utf-8"))["names"]
        self.assertTrue(any(row["ok"] for row in table) and any(not row["ok"] for row in table))
        for row in table:
            if row["ok"]:
                self.assertEqual(skins.check_name(row["name"]), row["name"])
            else:
                with self.assertRaises(SkinError, msg=row["name"]):
                    skins.check_name(row["name"])

    def test_a_stored_skin_named_new_is_read_as_it_is(self) -> None:
        # Data from before New Skin N: a skin called "new" is an ordinary skin; nothing renames it.
        path = skins.file_of(self.folder, OWNER)
        path.parent.mkdir(parents=True)
        value = {"format": skins.FORMAT, "owner": OWNER, "skins": {"new": {"textures": {ROCK: "pbrify@2048"}}, "New Skin 2": {"textures": {}}}}
        path.write_text(json.dumps(value))
        before = path.read_bytes()
        self.assertEqual(
            skins.load(self.folder, OWNER),
            {"new": Skin("new", {ROCK: "pbrify@2048"}), "New Skin 2": Skin("New Skin 2", {})},
        )
        # Negative: reading writes nothing.
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(skins.next_new(skins.load(self.folder, OWNER)), "New Skin 3")

    def test_a_skin_folder_file_that_names_no_owner_is_refused(self) -> None:
        folder = self.folder / skins.FOLDER
        folder.mkdir()
        (folder / "stray.json").write_text(json.dumps({"format": skins.FORMAT}))
        with self.assertRaises(SkinError) as refused:
            skins.owners(self.folder)
        self.assertIn("stray.json", str(refused.exception))


def named(*names: str) -> dict[str, Skin]:
    """Empty skins of these names."""
    return {name: Skin(name, {}) for name in names}


class NextNewTest(unittest.TestCase):
    """The name of a skin made without one (R-HD-137): New Skin N, one above the highest N in use."""

    def test_the_numbers_count_up_from_the_highest_in_use(self) -> None:
        one = named  # short, so each case reads on one line
        self.assertEqual(
            [
                skins.next_new({}),
                skins.next_new(one("hd")),
                skins.next_new(one("New Skin 1")),
                skins.next_new(one("New Skin 1", "New Skin 2")),
                # A deleted number below the highest is not taken again.
                skins.next_new(one("New Skin 3")),
                skins.next_new(one("new skin 7", "New Skin 2")),
            ],
            ["New Skin 1", "New Skin 1", "New Skin 2", "New Skin 3", "New Skin 4", "New Skin 8"],
        )
        # Negative: a name that only starts so is no New Skin N.
        self.assertEqual(skins.next_new(one("New Skin 2b", "New Skin")), "New Skin 1")


class SkinChangeTest(unittest.TestCase):
    def test_a_copy_takes_what_its_source_names_and_original_names_nothing(
        self,
    ) -> None:
        found = skins.copied({}, skins.ORIGINAL_SKIN, "hd")
        self.assertEqual(found, {"hd": Skin("hd", {})})
        found = {"hd": Skin("hd", {ROCK: "pbrify@2048"})}
        self.assertEqual(
            skins.copied(found, "hd", "two")["two"],
            Skin("two", {ROCK: "pbrify@2048"}),
        )

    def test_a_rename_changes_one_skin_and_leaves_the_others(self) -> None:
        found = {
            "hd": Skin("hd", {ROCK: "pbrify@2048"}),
            "two": Skin("two", {}),
        }
        self.assertEqual(
            skins.renamed(found, "hd", "sharp"),
            {
                "sharp": Skin("sharp", {ROCK: "pbrify@2048"}),
                "two": Skin("two", {}),
            },
        )

    def test_skin_names_are_unique_ignoring_case(self) -> None:
        found = {"hd": Skin("hd", {})}
        for change in (
            lambda: skins.copied(found, skins.ORIGINAL_SKIN, "HD"),
            lambda: skins.made(found, "Hd", {}),
            lambda: skins.renamed({**found, "two": Skin("two", {})}, "two", "hD"),
        ):
            with self.assertRaises(SkinError) as refused:
                change()
            self.assertIn("there is a skin 'hd' already", str(refused.exception))
        # Negative: a case change of the same skin is no clash.
        self.assertEqual(skins.renamed(found, "hd", "HD"), {"HD": Skin("HD", {})})
        for reserved in ("Original", "ORIGINAL"):
            with self.assertRaises(SkinError, msg=reserved):
                skins.check_name(reserved)

    def test_a_change_of_a_skin_that_is_not_there_or_of_another_texture_is_refused(
        self,
    ) -> None:
        with self.assertRaises(SkinError):
            skins.deleted({}, "hd")
        with self.assertRaises(SkinError):
            skins.renamed(
                {"hd": Skin("hd", {}), "two": Skin("two", {})},
                "hd",
                "two",
            )
        with self.assertRaises(SkinError):
            skins.with_texture(
                {"hd": Skin("hd", {})},
                "hd",
                "other.dds",
                "fast@1024",
                {ROCK},
                lambda *_: "",
            )
        with self.assertRaises(SkinError) as refused:
            skins.with_texture(
                {"hd": Skin("hd", {})},
                "hd",
                ROCK,
                "pbrify@1024",
                {ROCK},
                lambda *_: "no colour",
            )
        self.assertIn("no colour", str(refused.exception))


class BakeFileTest(FolderCase):
    def test_bakes_come_back_as_they_were_saved_and_none_leave_no_file(self) -> None:
        found = Bakes(
            {OWNER: Bake("hd", {ROCK: "pbrify@2048"})},
            {"assets\\textures\\ground.dds": "pbrify@4096"},
        )
        bakes.save(self.folder, found)
        self.assertEqual(bakes.load(self.folder), found)
        bakes.save(self.folder, Bakes({}, {}))
        self.assertFalse((self.folder / bakes.FILE).exists())
        self.assertEqual(bakes.load(self.folder), Bakes({}, {}))

    def test_a_faulty_bake_file_is_refused_with_the_place_of_the_fault(self) -> None:
        good = {
            "format": bakes.FORMAT,
            "owners": {OWNER: {"skin": "hd", "textures": {ROCK: "pbrify@2048"}}},
            "textures": {},
        }
        for word, value in (
            ("format", {**good, "format": 9}),
            ("picks: unknown key", {**good, "picks": {}}),
            (
                "owners.rock",
                {**good, "owners": {"rock": {"skin": "hd", "textures": {}}}},
            ),
            (
                f"owners.{OWNER}: a bake holds skin and textures",
                {**good, "owners": {OWNER: {"skin": "hd"}}},
            ),
            (
                f"owners.{OWNER}.textures.{ROCK}",
                {
                    **good,
                    "owners": {OWNER: {"skin": "hd", "textures": {ROCK: "upscale"}}},
                },
            ),
            ("textures.x", {**good, "textures": {"x": "pbrify"}}),
        ):
            (self.folder / bakes.FILE).write_text(json.dumps(value))
            with self.assertRaises(BakeError, msg=word) as refused:
                bakes.load(self.folder)
            self.assertIn(word, str(refused.exception))

    def test_a_bake_file_without_owners_or_textures_is_refused(self) -> None:
        for missing in ("owners", "textures"):
            value = {"format": bakes.FORMAT, "owners": {}, "textures": {}}
            del value[missing]
            (self.folder / bakes.FILE).write_text(json.dumps(value))
            with self.assertRaises(BakeError) as refused:
                bakes.load(self.folder)
            self.assertIn(f"{missing}: missing", str(refused.exception))

    def test_a_texture_bake_of_its_original_is_removed(self) -> None:
        found = bakes.with_texture(Bakes({}, {"x": "pbrify@1024"}), "x", "original")
        self.assertEqual(found.textures, {})
        with self.assertRaises(BakeError):
            bakes.with_texture(Bakes({}, {}), "x", "pbrify")
