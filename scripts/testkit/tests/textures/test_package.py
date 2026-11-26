"""Packaging the bakes: the baked files, refusals with the fixing command, the record (R-HD-101 to 106, R-HD-140, R-HD-145)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

from hdtex.core import bakes, index, package, requests, skins
from hdtex.core.dataset import DatasetError
from hdtex.core.index import Index
from hdtex.core.package import PackageError
from hdtex.core.results import ACCEPTED
from hdtex.core.statewriter import StateWriter
from hdtex.core.store import ENTRY, file_sha256, read_json, write_json

from testkit.tests.textures.doubles import FLOOR, GAME, NAMES, ROCK, Case, StandIn
from testkit.tests.textures.fixtures import repeat

SAND = "textures\\sand.dds"
ROCK_ORIGIN = f"storage\\{ROCK}"
UP = "pbrify@256"
FAST = "fast@256"
ROOM = "model:room"
HALL = "model:hall"
ATTIC = "model:wing\\attic"  # a path, as a model file's id is: its backslash must reach the command as one
CELLAR = "model:cellar"


class PackageCase(Case):
    def setUp(self) -> None:
        super().setUp()
        self.target = self.root / "map"
        self.target.mkdir()

    def make(self, asset: str = ROCK, variant: str = UP) -> dict:
        found = self.dataset()
        return requests.make(
            found,
            self.runner,
            found.texture(asset),
            variant,
            wait=lambda _seconds: None,
        )

    def baked(
        self,
        owner: str = ROOM,
        textures: dict[str, str] | None = None,
        name: str = "hd",
    ) -> None:
        """A skin of the owner that names `textures`, baked."""
        found = self.dataset()
        found.change_skin(
            owner, lambda now: skins.copied(now, skins.ORIGINAL_SKIN, name)
        )
        for asset, variant in (
            textures if textures is not None else {ROCK: UP}
        ).items():
            found.set_texture(owner, name, asset, variant)
        found.bake(owner, name)

    def written(self) -> list[str]:
        return sorted(
            str(path.relative_to(self.target))
            for path in self.target.rglob("*")
            if path.is_file()
        )

    def record_file(self) -> Path:
        return self.dataset().folder / package.FILE

    def refused(self) -> str:
        """The reason a package is refused. Nothing is written and no record is kept."""
        with self.assertRaises(PackageError) as refused:
            package.package(self.dataset(), self.target)
        self.assertEqual(self.written(), [])
        self.assertFalse(self.record_file().exists())
        return str(refused.exception)


class PackageTest(PackageCase):
    def test_a_baked_file_is_packaged_and_recorded_and_an_original_is_not(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4)
        self.make()
        self.baked()
        record = package.package(self.dataset(), self.target)
        kept = self.store.game(GAME).variant_file(ROCK_ORIGIN, "pbrify", 256)
        self.assertEqual(self.written(), [f"hd/{UP}/rock.dds", NAMES])
        self.assertEqual(
            (self.target / "hd" / UP / "rock.dds").read_bytes(), kept.read_bytes()
        )
        self.assertEqual(
            record,
            {
                "format": package.FORMAT,
                "files": [
                    {
                        "asset": ROCK,
                        "variant": UP,
                        "sha256": file_sha256(kept),
                        "path": f"hd/{UP}/rock.dds",
                    }
                ],
                # The bake names the original of the texture its skin does not
                # name (R-HD-131); an original is recorded and gets no file.
                "owners": {
                    ROOM: {"skin": "hd", "textures": {ROCK: UP, SAND: "original"}}
                },
                "textures": {},
                "unused": [],
            },
        )
        self.assertEqual(json.loads(self.record_file().read_text()), record)
        self.assertEqual(package.record(self.dataset()), record)

    def test_a_dataset_that_was_never_packaged_has_no_record(self) -> None:
        self.add(ROCK)
        self.assertIsNone(package.record(self.dataset()))

    def test_without_a_bake_nothing_is_packaged_and_that_is_recorded(self) -> None:
        self.add(ROCK)
        self.make()
        record = package.package(self.dataset(), self.target)
        self.assertEqual(
            (record["files"], record["owners"], record["textures"]), ([], {}, {})
        )
        self.assertEqual(self.written(), [NAMES])

    def test_two_owners_that_bake_one_variant_share_its_file(self) -> None:
        self.add(ROCK, users=["hall", "room"])
        self.make()
        self.baked(ROOM)
        self.baked(HALL)
        record = package.package(self.dataset(), self.target)
        self.assertEqual(len(record["files"]), 1)
        self.assertEqual(sorted(record["owners"]), [HALL, ROOM])

    def test_two_variants_of_one_texture_are_two_files(self) -> None:
        self.add(ROCK, users=["hall", "room"])
        self.make()
        self.make(variant=FAST)
        self.baked(ROOM)
        self.baked(HALL, {ROCK: FAST})
        record = package.package(self.dataset(), self.target)
        self.assertEqual(
            [(one["asset"], one["variant"]) for one in record["files"]],
            [(ROCK, FAST), (ROCK, UP)],
        )
        shown = json.loads((self.target / NAMES).read_text())
        self.assertEqual(
            (shown[ROOM][ROCK], shown[HALL][ROCK]),
            (f"hd/{UP}/rock.dds", f"hd/{FAST}/rock.dds"),
        )

    def test_a_bake_that_names_the_original_packages_no_file_and_passes_it_on(
        self,
    ) -> None:
        self.add(ROCK)
        self.baked(ROOM, {ROCK: "original"})
        planned = package.plan(self.dataset())
        self.assertEqual((planned.files, planned.problems), ([], []))
        self.assertEqual(
            [bake.textures for bake in planned.owners],
            [{ROCK: "original"}],
            "the game hears that the owner shows the original",
        )
        record = package.package(self.dataset(), self.target)
        self.assertEqual(record["files"], [])
        self.assertEqual(
            json.loads((self.target / NAMES).read_text())[ROOM], {ROCK: "original"}
        )

    def test_a_texture_of_its_own_kind_is_packaged_alone(self) -> None:
        self.add(SAND, kind=FLOOR)
        self.make(SAND)
        self.dataset().bake_texture(SAND, UP)
        record = package.package(self.dataset(), self.target)
        self.assertEqual(list(record["textures"]), [SAND])
        self.assertEqual(
            json.loads((self.target / NAMES).read_text())["alone"],
            {SAND: f"hd/{UP}/sand.dds"},
        )

    def test_a_bake_nothing_uses_is_kept_and_listed_and_fails_nothing(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, users=["hall"])
        self.make()
        self.make(SAND)
        self.baked()
        self.baked(HALL, {SAND: UP})
        self.folder_game.drop("one", SAND)
        record = package.package(self.dataset(), self.target)
        self.assertEqual((list(record["owners"]), record["unused"]), ([ROOM], [HALL]))
        self.assertIn(
            HALL, self.dataset().baked.owners, "negative: the bake is not removed"
        )


class RefusalTest(PackageCase):
    def test_an_index_row_whose_original_is_gone_is_refused_not_dropped(self) -> None:
        # The original vanished after the last sync. The package is written;
        # the index is not, and the error says to run index.
        self.add(ROCK)
        self.make()
        self.baked()
        found = self.dataset()
        found.sync()
        with (
            mock.patch.object(StateWriter, "known", side_effect=OSError("gone")),
            self.assertRaises(DatasetError) as refused,
        ):
            package.package(found, self.target)
        self.assertIn(f"{ROCK}: its original cannot be read (gone)", str(refused.exception))
        self.assertIn("run index", str(refused.exception))
        with Index(self.store.root).reading() as con:
            self.assertIn(
                ROCK, index.rows(con, GAME, "one"), "negative: the row is not dropped"
            )

    def test_a_stale_variant_is_refused_with_the_texture_and_the_command(self) -> None:
        self.add(ROCK)
        self.make()
        self.baked()
        self.add(ROCK, seed=2)
        said = self.refused()
        self.assertIn(f"{ROCK}: {UP} is stale", said)
        self.assertIn(f"baked by 1 owner:\n    {ROOM}, skin hd: ", said)
        self.assertIn(
            f"run: scripts/hd_textures.py request --game {GAME} --dataset one --asset '{ROCK}' --variant {UP}",
            said,
        )

    def swap(self) -> None:
        """Put another file under the kept variant's id, past the requests: as a removal and a new make, or a hand, would."""
        game = self.store.game(GAME)
        entry = game.entry(ROCK_ORIGIN, "pbrify")
        files = {int(size): game.variant_file(ROCK_ORIGIN, "pbrify", int(size)).read_bytes() for size in entry["files"]}
        game.drop_recipe(ROCK_ORIGIN, "pbrify")
        kept = {key: value for key, value in entry.items() if key not in ("files", "format", "origin", "recipe")}
        game.write_recipe(ROCK_ORIGIN, "pbrify", kept, {size: data[:-1] + bytes([data[-1] ^ 1]) for size, data in files.items()})

    def test_a_baked_variant_whose_file_is_another_now_is_refused_naming_each_bake_that_took_the_old_one(self) -> None:
        """R-HD-160: a bake pins the file. The id alone let a changed file into the map (O-HDS-18)."""
        self.add(ROCK, users=["room", "hall"])
        self.make()
        self.baked(ROOM)
        self.baked(HALL)
        self.swap()
        # The hall is baked again: it takes the file as it is now.
        self.dataset().bake(HALL, "hd")
        said = self.refused()
        self.assertIn(f"{ROCK}: {UP} is not the file 1 bake took", said)
        self.assertIn(
            f"    {ROOM}, skin hd: scripts/hd_textures.py bake --game {GAME} --dataset one --owner '{ROOM}' --skin 'hd'",
            said,
        )
        # Negative: the bake whose pin is the file of now is not named.
        self.assertNotIn(HALL, said)
        # Baked again, the room takes it too, and the package holds the file of now.
        self.dataset().bake(ROOM, "hd")
        record = package.package(self.dataset(), self.target)
        now = self.store.game(GAME).entry(ROCK_ORIGIN, "pbrify")["files"]["256"]["sha256"]
        self.assertEqual([item["sha256"] for item in record["files"]], [now])

    def test_a_bake_without_pins_is_packaged_as_before(self) -> None:
        """Negative: a bake made before the pins is not compared (SPEC-HD-TEXTURES 4.6)."""
        self.add(ROCK)
        self.make()
        self.baked()
        path = self.dataset().folder / bakes.FILE
        value = read_json(path)
        self.assertIn("pins", value)
        write_json(path, {key: held for key, held in value.items() if key != "pins"})
        self.swap()
        record = package.package(self.dataset(), self.target)
        self.assertEqual([item["variant"] for item in record["files"]], [UP])

    def test_a_missing_variant_is_refused_with_the_command(self) -> None:
        self.add(ROCK)
        self.make()
        self.baked()
        self.store.game(GAME).drop_recipe(ROCK_ORIGIN, "pbrify")
        said = self.refused()
        self.assertIn(f"{ROCK}: {UP} is not made", said)
        self.assertIn(f"    {ROOM}, skin hd: ", said)
        self.assertIn(
            f"request --game {GAME} --dataset one --asset '{ROCK}' --variant {UP}", said
        )

    def test_a_variant_with_a_problem_is_refused_with_the_unbake_that_fixes_it(
        self,
    ) -> None:
        self.runner = StandIn(repeat)
        # It tiles: its seam counts, and the stand-in's repeated pixels miss it. (Made for one rule and read with the
        # other, it would be stale, not a problem: results.edges_off.)
        self.add(ROCK, tiles=True)
        self.make()
        # Accepted while it is baked, then no longer: the package sees the problem the bake let through.
        entry_file = self.store.game(GAME).recipe_dir(ROCK_ORIGIN, "pbrify") / ENTRY
        entry = read_json(entry_file)
        write_json(entry_file, {**entry, ACCEPTED: "for the bake"})
        self.baked()
        write_json(entry_file, entry)
        said = self.refused()
        self.assertIn(f"{ROCK}: {UP} has problems: seam", said)
        self.assertIn(
            f"    {ROOM}, skin hd: scripts/hd_textures.py unbake --game {GAME} --dataset one --owner '{ROOM}'",
            said,
        )

    def test_every_refused_texture_is_named(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4)
        self.make()
        self.make(SAND)
        self.baked(ROOM, {ROCK: UP, SAND: UP})
        self.add(ROCK, seed=2)
        self.add(SAND, seed=5)
        said = self.refused()
        self.assertIn("2 baked textures of one cannot be packaged", said)
        self.assertIn(f"{ROCK}: {UP} is stale", said)
        self.assertIn(f"{SAND}: {UP} is stale", said)

    def test_a_refused_variant_names_every_owner_that_bakes_it_and_their_number(
        self,
    ) -> None:
        # R-HD-157. The build of 2026-11-26 named Barracks alone, of 18 owners.
        users = ["wing\\attic", "cellar", "hall", "room"]
        self.add(ROCK, users=users)
        self.add(SAND, seed=4, users=["room"])
        self.make()
        self.make(variant=FAST)
        self.make(SAND)
        self.baked(ROOM, {ROCK: UP, SAND: UP})
        self.baked(HALL)
        self.baked(CELLAR)
        self.baked(ATTIC, {ROCK: FAST})
        self.add(ROCK, seed=2, users=users)  # every variant of the rock is stale now
        lines = [line.strip() for line in self.refused().split("\n")]
        unbake = "scripts/hd_textures.py unbake --game {} --dataset one --owner '{}'"
        self.assertIn("2 baked textures of one cannot be packaged", lines[0])
        up = next(n for n, line in enumerate(lines) if line.startswith(f"{ROCK}: {UP} is stale"))
        self.assertEqual(lines[up + 1], "baked by 3 owners:")
        self.assertEqual(
            lines[up + 2 : up + 5],
            [f"{owner}, skin hd: {unbake.format(GAME, owner)}" for owner in (CELLAR, HALL, ROOM)],
        )
        fast = next(n for n, line in enumerate(lines) if line.startswith(f"{ROCK}: {FAST} is stale"))
        self.assertEqual(lines[fast + 1], "baked by 1 owner:")
        self.assertEqual(lines[fast + 2], f"{ATTIC}, skin hd: {unbake.format(GAME, ATTIC)}")
        self.assertEqual(
            sum(", skin hd: " in line for line in lines),
            4,
            "negative: no owner is named twice, and none for another variant than its own",
        )
        self.assertFalse(
            any(SAND in line for line in lines),
            "negative: the sound texture of an owner that is named is not",
        )

    def test_a_refused_bake_of_a_texture_on_its_own_names_that_bake(self) -> None:
        self.add(SAND, kind=FLOOR)
        self.make(SAND)
        self.dataset().bake_texture(SAND, UP)
        self.add(SAND, seed=5, kind=FLOOR)
        lines = [line.strip() for line in self.refused().split("\n")]
        at = next(n for n, line in enumerate(lines) if line.startswith(f"{SAND}: {UP} is stale"))
        self.assertEqual(lines[at + 1], "baked by 1 owner:")
        self.assertEqual(
            lines[at + 2],
            f"its own bake: scripts/hd_textures.py unbake --game {GAME} --dataset one --asset '{SAND}'",
        )

    def test_a_kept_file_that_changed_is_refused(self) -> None:
        self.add(ROCK)
        self.make()
        self.baked()
        kept = self.store.game(GAME).variant_file(ROCK_ORIGIN, "pbrify", 256)
        kept.write_bytes(kept.read_bytes()[:-1] + b"\x00\x01")
        self.assertIn(f"{kept} is not the file its entry names", self.refused())

    def test_a_package_the_game_finds_unsound_leaves_no_record(self) -> None:
        self.add(ROCK)
        self.make()
        self.baked()
        unsound = ValueError("the package names hd/rock.dds, which is not in it")
        with (
            mock.patch.object(self.folder_game, "check", side_effect=unsound),
            self.assertRaises(ValueError),
        ):
            package.package(self.dataset(), self.target)
        self.assertFalse(self.record_file().exists())


class StoreFolderTest(PackageCase):
    def test_a_dataset_is_packaged_into_its_own_folder_and_what_was_there_goes(
        self,
    ) -> None:
        self.add(ROCK)
        self.make()
        self.baked()
        first = package.package_in_store(self.dataset())
        folder = self.dataset().folder / package.FOLDER
        self.assertEqual(first["target"], str(folder))
        self.assertTrue((folder / "hd" / UP / "rock.dds").is_file())
        self.dataset().unbake(ROOM)
        second = package.package_in_store(self.dataset())
        self.assertEqual(second["files"], [])
        self.assertFalse((folder / "hd").exists())
        self.assertNotIn(
            "target",
            json.loads(self.record_file().read_text()),
            "the record holds no path of this host",
        )
