"""The store migration from layout 2 to 3: an entry without `tiles` gets true, the layout file last (SPEC-HD-TEXTURES 4.1)."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hdtex.core import progress, storemigrate
from hdtex.core.results import TILES
from hdtex.core.store import ENTRY, FORMAT, FORMAT_FILE, Store, StoreError


class MigrateCase(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / FORMAT_FILE).write_text("2\n")

    def entry(self, recipe: str, value: dict) -> Path:
        path = self.root / "sc2" / "variants" / "rock-0123" / recipe / ENTRY
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(value))
        return path

    def read(self, path: Path) -> dict:
        return json.loads(path.read_text())


class MigrateTest(MigrateCase):
    def test_each_entry_of_layout_2_gets_tiles_true_then_the_layout_is_3(self) -> None:
        one = self.entry("pbrify", {"format": 2, "origin": "o", "recipe": "pbrify"})
        two = self.entry("fast", {"format": 2, "origin": "o", "recipe": "fast", "edit": {"changed": ["color"]}})
        with self.assertRaisesRegex(StoreError, "make texture-store-migrate"):
            Store(self.root)
        found = storemigrate.migrate(self.root, dry_run=False)
        self.assertEqual((found["layout"], found["entries"], found["changed"]), ("2", 2, 2))
        self.assertEqual(self.read(one), {"format": FORMAT, "origin": "o", "recipe": "pbrify", TILES: True})
        self.assertEqual(self.read(two)[TILES], True)
        self.assertEqual((self.root / FORMAT_FILE).read_text(), f"{FORMAT}\n")
        Store(self.root)
        # Negative: a second run changes nothing.
        self.assertEqual(storemigrate.migrate(self.root, dry_run=False)["changed"], 0)

    def test_an_entry_of_layout_2_that_names_its_edge_rule_keeps_it(self) -> None:
        off = self.entry("fast", {"format": 2, "origin": "o", TILES: False})
        on = self.entry("pbrify", {"format": 2, "origin": "o", TILES: True})
        self.assertEqual(storemigrate.migrate(self.root, dry_run=False)["changed"], 2)
        self.assertEqual(self.read(off), {"format": FORMAT, "origin": "o", TILES: False})
        self.assertEqual(self.read(on), {"format": FORMAT, "origin": "o", TILES: True})

    def test_a_dry_run_writes_nothing(self) -> None:
        one = self.entry("pbrify", {"format": 2, "origin": "o"})
        before = one.read_text()
        self.assertEqual(storemigrate.migrate(self.root, dry_run=True)["changed"], 1)
        self.assertEqual((one.read_text(), (self.root / FORMAT_FILE).read_text()), (before, "2\n"))

    def test_a_run_stopped_halfway_is_finished_by_the_next(self) -> None:
        self.entry("pbrify", {"format": 3, "origin": "o", TILES: True})
        late = self.entry("fast", {"format": 2, "origin": "o"})
        self.assertEqual(storemigrate.migrate(self.root, dry_run=False)["changed"], 1)
        self.assertIs(self.read(late)[TILES], True)

    def test_an_open_request_another_layout_or_a_wrong_entry_is_refused_and_writes_nothing(self) -> None:
        one = self.entry("pbrify", {"format": 2, "origin": "o"})
        (one.parent / progress.FILE).write_text("{}")
        with self.assertRaisesRegex(StoreError, "1 request"):
            storemigrate.migrate(self.root, dry_run=False)
        (one.parent / progress.FILE).unlink()
        # A wrong entry that sorts last: the right one before it is not written either.
        early = self.entry("fast", {"format": 2, "origin": "o"})
        before = early.read_text()
        one.write_text(json.dumps({"format": 2, "origin": "o", TILES: "yes"}))
        self.assertLess(early, one)
        with self.assertRaisesRegex(StoreError, "is not true or false"):
            storemigrate.migrate(self.root, dry_run=False)
        self.assertEqual(early.read_text(), before, "negative: no entry was written")
        self.assertEqual((self.root / FORMAT_FILE).read_text(), "2\n", "negative: the layout stays")
        (self.root / FORMAT_FILE).write_text("1\n")
        with self.assertRaisesRegex(StoreError, "layout '1'"):
            storemigrate.migrate(self.root, dry_run=False)
