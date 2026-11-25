"""The state index kept in step: dropped, changed and removed rows, other schemas, origins, readers (R-HD-113, R-HD-114)."""

from __future__ import annotations

import hashlib
import sqlite3
import time
import zlib

from hdtex.core import index
from hdtex.core.index import FILE, SCHEMA, Index
from hdtex.core.queries import query

from testkit.tests.textures.doubles import FLOOR, GAME, ORIGIN, ROCK
from testkit.tests.textures.fixtures import (
    colour_rgba,
    texture_file,
)
from testkit.tests.textures.test_cli import ROOM, UP
from testkit.tests.textures.test_index import MOSS, NONE, SAND, IndexCase, inputs


def set_states(con: sqlite3.Connection, value: str) -> None:
    """Make every texture row name one state text, as a change made by hand: kept like the tooling keeps one."""
    data = value.encode()
    key = hashlib.sha256(data).digest()
    con.execute(query("checks/state_text_add"), (key, zlib.compress(data, index.COMPRESSION)))
    (found,) = con.execute(query("checks/text_id"), (key,)).fetchone()
    con.execute(query("checks/state_text_name_all"), (found,))
    con.execute(query("checks/state_set_all"), (found,))


def counted(con: sqlite3.Connection) -> list[tuple[int, int, int]]:
    """Each text whose count is not the number of fields naming it: id, count, fields. Empty: all are right."""
    return con.execute(query("checks/miscounted")).fetchall()


class SyncTest(IndexCase):
    def test_each_text_is_kept_once_and_counted_and_goes_with_its_last_field(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4)
        self.add(SAND, seed=4, dataset="two")
        self.ok("index")
        self.run_in("two", "index")
        with Index(self.store.root).reading() as con:
            self.assertEqual(counted(con), [])
            shared = con.execute(query("checks/descriptions_of"), (SAND,)).fetchone()[0]
            texts = con.execute(query("checks/texts")).fetchone()[0]
        self.assertEqual(shared, 1, "one description of SAND, for both datasets")
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.folder_game.drop("one", SAND)
        self.ok("index")
        with Index(self.store.root).reading() as con:
            self.assertEqual(counted(con), [], "after a change and a removal")
            orphans = con.execute(query("checks/unnamed_texts")).fetchone()[0]
            after = con.execute(query("checks/texts")).fetchone()[0]
        self.assertEqual(orphans, 0, "negative: no text that no field names stays")
        self.assertLessEqual(after, texts + 1, "ROCK's old state went when its new one came")

    def test_a_texture_the_dataset_dropped_leaves_its_rows_only(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4)
        self.add(SAND, seed=4, dataset="two")
        self.ok("index")
        self.run_in("two", "index")
        self.folder_game.drop("one", SAND)
        self.assertEqual(self.ok("index")["removed"], 1)
        self.assertEqual(self.read(ROCK, SAND)["unknown"], [SAND])
        self.assertEqual(
            self.read(SAND, dataset="two")["unknown"],
            [],
            "negative: another dataset keeps its row",
        )

    def test_a_changed_original_shows_its_variant_as_stale(self) -> None:
        self.add(SAND, kind=FLOOR)
        self.ok("request", "--asset", SAND, "--variant", UP)
        self.ok("bake", "--asset", SAND, "--variant", UP)
        self.assertEqual(
            (self.state(SAND)["variants"][0]["stale"], self.state(SAND)["bakeProblem"]),
            (False, ""),
        )
        self.rewrite(SAND, 2)
        self.assertEqual(
            self.state(SAND)["variants"][0]["stale"],
            False,
            "negative: nobody told the index yet",
        )
        self.ok("index")
        sand = self.state(SAND)
        self.assertEqual(sand["variants"][0]["stale"], True)
        self.assertIn("stale", sand["bakeProblem"])
        self.assertEqual(
            inputs(sand), ["original"], "negative: a stale variant is no input"
        )

    def test_an_index_that_was_removed_comes_back_whole(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, kind=FLOOR)
        for asset in (ROCK, SAND):
            self.ok("request", "--asset", asset, "--variant", UP)
        self.hd()
        self.ok("bake", "--owner", ROOM, "--skin", "hd")
        self.ok("bake", "--asset", SAND, "--variant", UP)
        self.ok("package")
        self.ok("index", "--asset", ROCK, "--asset", SAND)
        before, owner = self.read(ROCK, SAND), self.owner()
        self.assertEqual(
            before["textures"][SAND]["packaged"], {"variant": UP, "held": True}
        )
        for path in self.store.root.glob(FILE + "*"):
            path.unlink()
        with Index(self.store.root).reading() as con:
            self.assertIsNone(con, "negative: there is no index now")
        self.ok("index", "--asset", ROCK, "--asset", SAND)
        self.assertEqual((self.read(ROCK, SAND), self.owner()), (before, owner))

    def test_a_row_that_holds_something_else_is_written_again(self) -> None:
        self.add(ROCK)
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.ok("index")
        before = self.state()
        with Index(self.store.root).writing() as con:
            set_states(con, "{}")
        self.assertEqual(self.state(), {})
        self.assertEqual(self.ok("index")["written"], 1)
        self.assertEqual(self.state(), before, "the files hold")

    def test_a_file_of_another_schema_is_emptied_by_the_tooling_and_refused_by_a_reader(
        self,
    ) -> None:
        self.add(ROCK)
        other = sqlite3.connect(self.store.root / FILE)
        other.executescript(query("checks/other_schema"))
        other.execute(f"PRAGMA user_version = {SCHEMA + 1}")
        other.close()
        with Index(self.store.root).reading() as con:
            self.assertIsNone(con, "a reader takes no file of another schema")
        self.ok("index")
        self.assertEqual(self.state()["asset"], ROCK)
        with Index(self.store.root).reading() as con:
            tables = {
                name
                for (name,) in con.execute(query("checks/table_names"))
            }
        self.assertEqual(tables, {"dataset", "text", "texture", "original", "origin", "owner"})

    def test_the_origin_of_every_texture_file_is_kept_listed_or_not(self) -> None:
        self.add(ROCK)
        self.add(MOSS, dataset="two")  # in the storage; dataset one does not list it
        self.folder_game.add(
            "one", SAND, texture_file("diffuse", colour_rgba(4, 64, 64)), own=True
        )
        self.assertEqual(self.ok("index")["origins"], 3)
        with Index(self.store.root).reading() as con:
            found = [
                index.origin(con, GAME, "one", asset)
                for asset in (ROCK, MOSS, SAND, NONE)
            ]
        self.assertEqual(
            found,
            [ORIGIN + ROCK, ORIGIN + MOSS, f"dataset\\one\\{SAND}", None],
            "a file of the dataset's own wins; an unknown asset has none",
        )
        with Index(self.store.root).writing() as con:
            same = self.folder_game.origins("one")
            self.assertFalse(
                index.put_origins(con, GAME, "one", same),
                "negative: origins that are as before are not written again",
            )
            self.assertTrue(
                index.put_origins(con, GAME, "one", same | {NONE: ORIGIN + NONE})
            )

    def test_the_textures_of_one_kind_are_listed_with_their_entries(self) -> None:
        self.add(ROCK)
        self.add(SAND, seed=4, kind="floor", entries=["Hall"])
        self.ok("index")
        with Index(self.store.root).reading() as con:
            floor = index.rows_of_kind(con, GAME, "one", "floor")
            roof = index.rows_of_kind(con, GAME, "one", "roof")
        self.assertEqual(
            [
                (row.texture.asset, row.texture.entries, row.texture.role)
                for row in floor
            ],
            [(SAND, ("Hall",), "diffuse")],
        )
        self.assertEqual(roof, [])

    def test_a_reader_does_not_wait_for_a_writer(self) -> None:
        self.add(ROCK)
        self.ok("index")
        before = self.state()
        with Index(self.store.root).writing() as con:
            set_states(con, '{"new": 1}')
            start = time.monotonic()
            during = self.state()
            waited = time.monotonic() - start
        self.assertEqual(during, before, "a change shows whole or not at all")
        self.assertLess(
            waited,
            index.BUSY_SECONDS / 10,
            "the reader did not wait for the write lock",
        )
        self.assertEqual(self.state(), {"new": 1})
