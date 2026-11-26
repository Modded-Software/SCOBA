"""Host tests for scripts/mapgen/loading_screen.py (REQ-LOADING-SCREEN)."""

from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

import workpaths
from mapgen import loading_screen as ls
from project_root import project_root
from testkit.map_builder import patch_mapinfo

from .built_map import needs_built

SRC = project_root() / "src" / "SCOBA.SC2Map"


def source_strings() -> dict[str, dict[str, str]]:
    return {locale: ls.read_strings(SRC, locale) for locale in ls.LOCALES}


class TextTest(unittest.TestCase):
    def setUp(self) -> None:
        self.strings = source_strings()
        self.tip = self.strings["enUS"][ls.TIP]
        self.script = ls.script_text(SRC)
        self.buttons = (SRC / "Base.SC2Data" / "GameData" / "ButtonData.xml").read_text(encoding="utf-8")

    def test_source_text(self) -> None:
        self.assertEqual(ls.check_text(self.strings), [])

    def test_source_bindings(self) -> None:
        self.assertEqual(ls.check_bindings(self.tip, self.script, self.buttons), [])

    def test_name_and_author(self) -> None:
        for locale in ls.LOCALES:
            self.assertEqual(self.strings[locale]["DocInfo/Name"], "SCOBA: StarCraft Online Battle Arena", locale)
            self.assertEqual(self.strings[locale]["DocInfo/Author"], "SCOBA", locale)

    def test_every_locale_is_set(self) -> None:
        self.assertEqual(len(ls.LOCALES), 13)
        for locale in ls.LOCALES:
            self.assertEqual(self.strings[locale]["DocInfo/Name"], ls.NAME, locale)
            self.assertEqual(self.strings[locale]["DocInfo/Author"], ls.AUTHOR, locale)

    def test_other_locales_are_translated(self) -> None:
        en = self.strings["enUS"]
        for locale in ls.LOCALES:
            if locale.startswith("en"):
                continue
            for field in ("DocInfo/DescShort", "DocInfo/DescLong", ls.TIP):
                self.assertNotEqual(self.strings[locale][field], en[field], f"{locale} {field}")

    def test_tip_tokens_match_enus(self) -> None:
        want = ls.tip_tokens(self.tip)
        self.assertEqual(want["Ctrl+C"], 2)
        self.assertEqual(want["3"], 3)
        for locale in ls.LOCALES:
            self.assertEqual(ls.tip_tokens(self.strings[locale][ls.TIP]), want, locale)

    def test_dropped_key_in_a_translation_fails(self) -> None:
        # Negative: a translation loses a key, a button label, a line.
        for old, new in (("Ctrl+E", "Strg+E"), ("Chase-Taste", "Verfolgen-Taste"), ("<n/>HELD", " HELD")):
            strings = source_strings()
            strings["deDE"][ls.TIP] = strings["deDE"][ls.TIP].replace(old, new, 1)
            self.assertIn("deDE LoadingScreen/Tip: keys, labels, numbers or lines differ from enUS", ls.check_text(strings), old)

    def test_untranslated_locale_fails(self) -> None:
        strings = source_strings()
        strings["frFR"]["DocInfo/DescLong"] = strings["enUS"]["DocInfo/DescLong"]
        self.assertEqual(ls.check_text(strings), ["frFR DocInfo/DescLong: the enUS text, not translated"])

    def test_tip_starts_with_the_controls(self) -> None:
        # Operator 2026-11-26: no intro line before the controls.
        for locale in ls.LOCALES:
            self.assertNotIn("Two control modes", self.strings[locale][ls.TIP], locale)
        for locale in ("enUS", "enGB"):
            self.assertTrue(self.strings[locale][ls.TIP].startswith("BOTH MODES<n/>"), locale)

    def test_old_texts_fail(self) -> None:
        # Negative: the 2018 enGB tip and the old enUS tip, as they were.
        old = {
            "PAGE UP - Enter unit to TPS Mode": "PAGE UP",
            "E, D, S and F - Move unit in TPS/FPS Mode": "FPS",
            "<CTRL> to zoom in.": "<CTRL> to zoom",
            "Destroy all enemy structures.": "Destroy all enemy structures",
            "Outbreak 3 Players Coop": "Outbreak",
        }
        for text, word in old.items():
            strings = source_strings()
            strings["enGB"][ls.TIP] = text
            self.assertIn(f"enGB {ls.TIP}: old text {word!r}", ls.check_text(strings), text)

    def test_missing_field_fails(self) -> None:
        for field in ls.FIELDS:
            strings = source_strings()
            del strings["enUS"][field]
            self.assertIn(f"enUS {field}: missing or empty", ls.check_text(strings))

    def test_locales_must_agree(self) -> None:
        strings = source_strings()
        strings["enGB"]["DocInfo/DescShort"] += " More."
        self.assertEqual(ls.check_text(strings), ["DocInfo/DescShort: enGB differs from enUS"])

    def test_unbound_key_fails(self) -> None:
        # Negative: a key the tip names and no checked phrase covers.
        for extra, word in (("<n/>Alt+1 - Tosh", "Alt"), ("<n/>PAGE UP - TPS mode", "PAGE"), ("<n/>Tab - mode", "Tab")):
            errors = ls.check_bindings(self.tip + extra, self.script, self.buttons)
            self.assertEqual(errors, [f"tip: key {word!r} named outside the checked phrases"])

    def test_rebound_key_fails(self) -> None:
        # Negative: the script binds another key than the tip says.
        script = self.script.replace("const int gv_zOOM = c_keyZ;", "const int gv_zOOM = c_keyX;")
        self.assertEqual(
            ls.check_bindings(self.tip, script, self.buttons),
            ["tip: 'Z (hold) - zoom' has no script line 'const int gv_zOOM = c_keyZ;'"],
        )
        script = self.script.replace("gv_availableStatPoints[lp_player] += 3;", "gv_availableStatPoints[lp_player] += 5;")
        self.assertEqual(len(ls.check_bindings(self.tip, script, self.buttons)), 1)

    def test_renamed_button_fails(self) -> None:
        buttons = self.buttons.replace("Controls: Actions", "Controls: TPS")
        self.assertEqual(
            ls.check_bindings(self.tip, self.script, buttons),
            ["tip: 'ACTIONS (TPS)' has no button data line 'Controls: Actions'"],
        )

    def test_dropped_phrase_fails(self) -> None:
        tip = self.tip.replace("Ctrl+E - order mode", "order mode")
        self.assertIn("tip: phrase missing: 'Ctrl+E - order mode'", ls.check_bindings(tip, self.script, self.buttons))

    def test_every_binding_line_is_in_the_script(self) -> None:
        for phrase, lines in ls.BINDINGS.items():
            for line in lines:
                self.assertEqual(self.script.count(line) > 0, True, f"{phrase}: {line}")


class WaitForKeyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.data = (SRC / "MapInfo").read_bytes()

    def test_header(self) -> None:
        at = ls.header(self.data)
        self.assertEqual(at.version, 39)
        self.assertEqual(struct.unpack_from("<II", self.data, ls.SIZE_OFF), (128, 128))
        self.assertLessEqual(at.flags_off + 4, len(self.data))
        self.assertEqual(struct.unpack_from("<Q", self.data, ls.HASH_OFF)[0], ls.map_hash(self.data))

    def test_on_and_off(self) -> None:
        on = ls.set_wait_for_key(self.data, True)
        off = ls.set_wait_for_key(self.data, False)
        self.assertTrue(ls.wait_for_key(on))
        self.assertFalse(ls.wait_for_key(off))
        for data in (on, off):
            self.assertEqual(struct.unpack_from("<Q", data, ls.HASH_OFF)[0], ls.map_hash(data))
        # One set flag more: the check value is one lower.
        self.assertEqual(ls.map_hash(off) - ls.map_hash(on), 1)

    def test_only_flag_and_check_value_change(self) -> None:
        at = ls.header(self.data)
        on = ls.set_wait_for_key(self.data, True)
        off = ls.set_wait_for_key(self.data, False)
        self.assertEqual(len(on), len(off))
        changed = {i for i in range(len(on)) if on[i] != off[i]}
        allowed = set(range(ls.HASH_OFF, ls.HASH_OFF + 8)) | set(range(at.flags_off, at.flags_off + 4))
        self.assertTrue(changed)
        self.assertLessEqual(changed, allowed)
        other = struct.unpack_from("<I", on, at.flags_off)[0] ^ struct.unpack_from("<I", off, at.flags_off)[0]
        self.assertEqual(other, ls.WAIT_FOR_KEY)

    def test_idempotent_and_round_trip(self) -> None:
        on = ls.set_wait_for_key(self.data, True)
        self.assertEqual(ls.set_wait_for_key(on, True), on)
        self.assertEqual(ls.set_wait_for_key(ls.set_wait_for_key(on, False), True), on)

    def test_not_a_mapinfo(self) -> None:
        with self.assertRaises(SystemExit):
            ls.header(b"XXXX" + self.data[4:])

    def test_build_sets_it(self) -> None:
        # The build's own MapInfo step: 256 cells, new bounds, the wait on.
        from expand_map import expand_mapinfo

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "MapInfo"
            expand_mapinfo(SRC / "MapInfo", out)
            data = out.read_bytes()
        at = ls.header(data)
        self.assertTrue(ls.wait_for_key(data))
        self.assertEqual(struct.unpack_from("<II", data, ls.SIZE_OFF), (256, 256))
        self.assertEqual(struct.unpack_from("<4i", data, at.bounds_off), (2, 3, 254, 254))
        self.assertEqual(struct.unpack_from("<Q", data, ls.HASH_OFF)[0], ls.map_hash(data))
        # The check value as the build wrote it before this module, flag on.
        flags = struct.unpack_from("<I", data, at.flags_off)[0]
        old = at.desc_len + 7 * 256 + 2 * (252 * 252 + 251 * 251) + 3 * 256 - bin(flags).count("1") - 17
        self.assertEqual(ls.map_hash(data), old)

    def test_test_map_clears_it(self) -> None:
        # A test map must enter the game by itself (testkit/map_builder).
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "MapInfo"
            path.write_bytes(ls.set_wait_for_key(self.data, True))
            patch_mapinfo(path)
            self.assertEqual(path.read_bytes(), ls.set_wait_for_key(self.data, False))


class DocumentHeaderTest(unittest.TestCase):
    """The game shows the text the DocumentHeader holds, not GameStrings.txt alone."""

    def setUp(self) -> None:
        self.data = (SRC / "DocumentHeader").read_bytes()
        self.strings = source_strings()

    def test_read_round_trip(self) -> None:
        prefix, entries = ls.read_document_header(self.data)
        self.assertEqual(len(entries), 172)
        self.assertEqual(ls.write_document_header(prefix, entries), self.data)
        self.assertIn(("DocInfo/Author", "zhTW", "Blizzard Entertainment"), entries)

    def test_source_header_is_old(self) -> None:
        # Negative: this is the text the game showed on 2026-11-26.
        errors = ls.check_document_header(self.data, self.strings)
        self.assertIn("DocumentHeader enUS DocInfo/Name differs from GameStrings", errors)
        self.assertIn("DocumentHeader enGB LoadingScreen/Tip: old text 'PAGE UP'", errors)

    def test_synced_header_matches_the_strings(self) -> None:
        synced = ls.sync_document_header(self.data, self.strings)
        self.assertEqual(ls.check_document_header(synced, self.strings), [])
        entries = dict(((key, loc), value) for key, loc, value in ls.read_document_header(synced)[1])
        for locale in ls.LOCALES:
            for field in ls.FIELDS:
                self.assertEqual(entries[(field, locale)], self.strings[locale][field], f"{locale} {field}")
        self.assertEqual(ls.sync_document_header(synced, self.strings), synced)

    def test_only_enus_and_engb_fields_change(self) -> None:
        before = ls.read_document_header(self.data)
        after = ls.read_document_header(ls.sync_document_header(self.data, self.strings))
        self.assertEqual(before[0], after[0])
        old = {(key, loc): value for key, loc, value in before[1]}
        new = {(key, loc): value for key, loc, value in after[1]}
        changed = {k for k in new if old.get(k) != new[k]} | (old.keys() - new.keys())
        self.assertTrue(changed)
        self.assertLessEqual(changed, {(f, loc) for f in ls.FIELDS for loc in ls.LOCALES})
        # Negative: the player names keep their text in every locale.
        names = {k for k in old if k[0].startswith("MapInfo/Player")}
        self.assertTrue(names)
        self.assertEqual({k: new[k] for k in names}, {k: old[k] for k in names})
        self.assertEqual(new[("DocInfo/Author", "zhTW")], "SCOBA")

    def test_build_writes_it(self) -> None:
        from expand_map import expand_document_header

        with tempfile.TemporaryDirectory() as tmp:
            map_dir = Path(tmp)
            (map_dir / "DocumentHeader").write_bytes(self.data)
            for locale in ls.LOCALES:
                rel = f"{locale}.SC2Data/LocalizedData/GameStrings.txt"
                (map_dir / rel).parent.mkdir(parents=True)
                (map_dir / rel).write_bytes((SRC / rel).read_bytes())
            expand_document_header(map_dir)
            self.assertEqual(ls.check_document_header((map_dir / "DocumentHeader").read_bytes(), self.strings), [])

    def test_not_a_document_header(self) -> None:
        with self.assertRaises(SystemExit):
            ls.read_document_header(b"XXXX" + self.data[4:])
        with self.assertRaises(SystemExit):
            ls.read_document_header(self.data[:-3])


@needs_built("MapInfo")
class BuiltMapTest(unittest.TestCase):
    def test_built_map_passes(self) -> None:
        self.assertEqual(ls.check(workpaths.path("SC2_BUILT_MAP")), [])

    def test_built_map_waits_for_a_key(self) -> None:
        data = (workpaths.path("SC2_BUILT_MAP") / "MapInfo").read_bytes()
        self.assertTrue(ls.wait_for_key(data))
        self.assertEqual(struct.unpack_from("<II", data, ls.SIZE_OFF), (256, 256))

    def test_built_map_without_the_flag_fails(self) -> None:
        # Negative: the validator sees a built map that would not wait.
        built = workpaths.path("SC2_BUILT_MAP")
        with tempfile.TemporaryDirectory() as tmp:
            map_dir = Path(tmp)
            for rel in ("MapInfo", "DocumentHeader", "Base.SC2Data/GameData/ButtonData.xml", *(f"{loc}.SC2Data/LocalizedData/GameStrings.txt" for loc in ls.LOCALES)):
                (map_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                (map_dir / rel).write_bytes((built / rel).read_bytes())
            (map_dir / "scripts").symlink_to(built / "scripts")
            self.assertEqual(ls.check(map_dir), [])
            (map_dir / "MapInfo").write_bytes(ls.set_wait_for_key((built / "MapInfo").read_bytes(), False))
            self.assertEqual(ls.check(map_dir), ["MapInfo: the wait for a key is off"])

    def test_built_map_with_the_old_header_fails(self) -> None:
        # Negative: the state the operator saw on 2026-11-26.
        built = workpaths.path("SC2_BUILT_MAP")
        with tempfile.TemporaryDirectory() as tmp:
            map_dir = Path(tmp)
            for rel in ("MapInfo", "Base.SC2Data/GameData/ButtonData.xml", *(f"{loc}.SC2Data/LocalizedData/GameStrings.txt" for loc in ls.LOCALES)):
                (map_dir / rel).parent.mkdir(parents=True, exist_ok=True)
                (map_dir / rel).write_bytes((built / rel).read_bytes())
            (map_dir / "scripts").symlink_to(built / "scripts")
            (map_dir / "DocumentHeader").write_bytes((SRC / "DocumentHeader").read_bytes())
            self.assertIn("DocumentHeader enUS DocInfo/Name differs from GameStrings", ls.check(map_dir))


if __name__ == "__main__":
    unittest.main()
