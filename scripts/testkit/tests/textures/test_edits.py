"""Edit sessions: open, the states, what a scratch may hold, and what refuses it (R-PC-30 to 35, R-PC-42, R-PC-70 to 76).

These tests need PhotoCraft's renderer (`make install-photocraft`).
"""

from __future__ import annotations

from hdtex.core import edits, photocraft
from hdtex.core.photocraft import GROUP, Layer

from testkit.tests.textures.doubles import ROCK
from testkit.tests.textures.edit_fixtures import ORIGIN, EditCase, base_of, cmd, left_half, painted, run_on
from testkit.tests.textures.fixtures import normal_rgba, texture_file

BUMP = "textures\\bump.dds"
NONE = "textures\\none.dds"
BASE = Layer("base", "Pixel", ())


class OpenTest(EditCase):
    def test_a_session_holds_a_base_per_plane_a_scratch_with_a_group_per_plane_and_its_record(self) -> None:
        state = self.open()
        folder = self.folder(state["session"])
        self.assertEqual(state["session"], edits.session_id(ORIGIN, "original"))
        self.assertEqual(
            sorted(path.name for path in folder.iterdir()),
            ["base", "rendered", "scratch.json", "scratch.psd", "session.json"],
        )
        self.assertEqual(sorted(path.name for path in (folder / "base").iterdir()), ["alpha.png", "color.png"])
        found = photocraft.info(self.scratch(state["session"]))
        self.assertEqual((found.width, found.height, found.mode, found.depth), (64, 64, "Rgb", 8))
        # The colour group is on top; each group holds one layer, `base`; nothing else is in the scratch.
        self.assertEqual(found.layers, (Layer("color", GROUP, (BASE,)), Layer("alpha", GROUP, (BASE,))))
        self.assertEqual((state["state"], state["changed"], state["left_out"], state["reason"]), ("unchanged", [], [], ""))
        self.assertEqual((state["variant"], state["size"], state["planes"], state["checked"]), ("original", [64, 64], self.PLANES, True))
        for plane in self.PLANES:
            base = self.picture(state["session"], "base", plane)
            self.assertEqual(base.shape, (64, 64, 3))
            self.assertTrue((self.picture(state["session"], "rendered", plane) == base).all(), plane)
        # A one-channel plane is that channel three times.
        alpha = self.picture(state["session"], "base", "alpha")
        self.assertTrue((alpha[:, :, 0] == alpha[:, :, 1]).all() and (alpha[:, :, 0] == alpha[:, :, 2]).all())
        self.assertGreater(len(set(alpha[:, :, 0].ravel().tolist())), 8, "the plane holds a picture, so the comparison proves something")

    def test_a_second_open_answers_the_session_that_is_there_and_writes_nothing(self) -> None:
        first = self.open()
        scratch = self.scratch(first["session"])
        before = (scratch.stat().st_mtime_ns, (self.folder(first["session"]) / "session.json").stat().st_mtime_ns)
        self.change(first["session"], painted(self.PLANES, "color"))
        edited = scratch.stat().st_mtime_ns
        self.assertNotEqual(edited, before[0])
        again = self.open()
        self.assertEqual(again["session"], first["session"])
        # Negative: the open did not build the scratch again over the person's work.
        self.assertEqual(scratch.stat().st_mtime_ns, edited)
        self.assertEqual(again["state"], "edited")

    def test_a_texture_with_one_plane_has_one_group(self) -> None:
        self.folder_game.add("one", BUMP, texture_file("normal", normal_rgba()), role="normal")
        state = self.open(asset=BUMP)
        self.assertEqual(state["planes"], ["normal"])
        self.assertEqual(photocraft.info(self.scratch(state["session"])).layers, (Layer("normal", GROUP, (BASE,)),))
        self.assertNotEqual(state["session"], self.open()["session"])

    def test_what_is_no_variant_of_the_texture_or_has_no_role_is_refused_and_leaves_no_session(self) -> None:
        self.assertIn("has no variant pbrify@256", self.error("edit", "open", "--asset", ROCK, "--variant", "pbrify@256"))
        self.assertIn("a variant is", self.error("edit", "open", "--asset", ROCK, "--variant", "nonsense"))
        self.assertIn("no texture", self.error("edit", "open", "--asset", "textures\\nope.dds"))
        self.folder_game.add("one", NONE, b"not a texture", role=None, reason="it is a cube map")
        self.assertIn("cannot be edited: it is a cube map", self.error("edit", "open", "--asset", NONE))
        self.assertFalse((self.game.root / edits.EDITS).exists(), "negative: no session folder was made")

    def test_the_words_of_the_command_must_fit(self) -> None:
        session = self.open()["session"]
        self.assertIn("takes --asset", self.error("edit", "open", "--session", session))
        self.assertIn("takes --session", self.error("edit", "check", "--asset", ROCK))
        self.assertIn("16 hex digits", self.error("edit", "check", "--session", "../x"))
        self.assertIn("there is no edit session", self.error("edit", "check", "--session", "0" * 16))


class StateTest(EditCase):
    def test_a_scratch_saved_again_with_the_same_planes_is_unchanged(self) -> None:
        session = self.open()["session"]
        scratch = self.scratch(session)
        before = scratch.read_bytes()
        # Another layer, hidden: other bytes, the same planes.
        state = self.change(session, painted(self.PLANES, "color"), cmd("layer.setProps", visible=False))
        self.assertNotEqual(scratch.read_bytes(), before, "the file is another one")
        self.assertEqual((state["state"], state["changed"]), ("unchanged", []))

    def test_a_changed_scratch_is_not_checked_until_its_check_ran(self) -> None:
        session = self.open()["session"]
        run_on(self.scratch(session), painted(self.PLANES, "color"))
        dataset = self.dataset()
        seen = edits.state(dataset, session)
        # Reading a state runs no check: it says the scratch is not the one that was read.
        self.assertEqual((seen["state"], seen["checked"]), ("unchanged", False))
        state = self.check(session)
        self.assertEqual((state["state"], state["changed"], state["checked"]), ("edited", ["color"], True))

    def test_an_input_that_changed_makes_the_session_stale_and_keeps_its_files(self) -> None:
        session = self.open()["session"]
        self.change(session, painted(self.PLANES, "color"))
        self.add(seed=2)  # the original is another file now
        state = self.check(session)
        self.assertEqual(state["state"], "stale")
        self.assertIn("another file now", state["reason"])
        self.assertTrue(self.scratch(session).is_file(), "the work is kept")
        self.assertIn("another file now", self.error("edit", "transfer", "--session", session))
        self.assertEqual(self.recipes(), [], "negative: a stale session makes no variant")

    def test_a_discard_removes_the_session(self) -> None:
        session = self.open()["session"]
        self.assertEqual(self.ok("edit", "discard", "--session", session), {"session": session, "discarded": True})
        self.assertFalse(self.folder(session).exists())
        self.assertIn("there is no edit session", self.error("edit", "discard", "--session", session))


class LayerTest(EditCase):
    def test_a_layer_with_a_mask_and_a_blend_mode_changes_its_plane_only_to_the_pixels_expected(self) -> None:
        session = self.open()["session"]
        state = self.change(
            session,
            painted(self.PLANES, "color"),
            cmd("layer.setProps", blend="Multiply"),
            left_half(self.SIZE),
        )
        self.assertEqual((state["state"], state["changed"], state["left_out"]), ("edited", ["color"], []))
        base, now = self.picture(session, "base", "color"), self.picture(session, "rendered", "color")
        half = self.SIZE // 2
        # Red in Multiply keeps red and takes green and blue away, where the mask shows the layer.
        self.assertTrue((now[:, :half, 0] == base[:, :half, 0]).all())
        self.assertTrue((now[:, :half, 1:] == 0).all())
        self.assertGreater(int(base[:, :half, 1:].max()), 0, "the base had green and blue there")
        self.assertTrue((now[:, half:] == base[:, half:]).all(), "negative: the masked half is as it was")
        self.assertTrue((self.picture(session, "rendered", "alpha") == self.picture(session, "base", "alpha")).all())

    def test_an_adjustment_layer_in_a_group_changes_that_plane(self) -> None:
        session = self.open()["session"]
        state = self.change(session, base_of(self.PLANES, "alpha"), cmd("layer.newAdjustmentLayer.invert"))
        self.assertEqual(state["changed"], ["alpha"])
        self.assertTrue((self.picture(session, "rendered", "alpha") == 255 - self.picture(session, "base", "alpha")).all())

    def test_a_hidden_group_is_still_read(self) -> None:
        session = self.open()["session"]
        shown = self.change(session, painted(self.PLANES, "color"))
        was = self.picture(session, "rendered", "color")
        hidden = self.change(session, cmd("layer.select", name="color"), cmd("layer.setProps", visible=False))
        self.assertEqual((hidden["state"], hidden["changed"]), (shown["state"], ["color"]))
        self.assertTrue((self.picture(session, "rendered", "color") == was).all())

    def test_a_layer_outside_the_groups_is_left_out_and_named(self) -> None:
        session = self.open()["session"]
        state = self.change(
            session,
            cmd("layer.select", name="color"),
            cmd("layer.new.layer", name="stray"),
            cmd("edit.fill", contents="color", color="#0000ff"),
        )
        self.assertEqual([layer.name for layer in photocraft.info(self.scratch(session)).layers], ["stray", "color", "alpha"])
        # Every plane is as without it, and the record names the layer.
        self.assertEqual((state["state"], state["changed"], state["left_out"]), ("unchanged", [], ["stray"]))
        self.assertEqual(sorted(path.name for path in (self.folder(session) / "rendered").iterdir()), ["alpha.png", "color.png"])


class RefusedTest(EditCase):
    def refused(self, *steps: list[str]) -> str:
        """Change the scratch so it cannot give every plane. Returns the reason; no transfer makes a variant of it."""
        session = self.open()["session"]
        state = self.change(session, *steps)
        self.assertEqual((state["state"], state["changed"]), ("edited", []))
        self.assertEqual(self.error("edit", "transfer", "--session", session).split(": ", 1)[1], state["reason"])
        self.assertEqual(self.recipes(), [], "negative: no variant was made")
        return state["reason"]

    def test_another_size_is_refused(self) -> None:
        self.assertEqual(self.refused(cmd("image.imageSize", width=32, height=32)), "the scratch is 32x32; the texture is 64x64")

    def test_a_renamed_group_is_refused(self) -> None:
        reason = self.refused(cmd("layer.select", name="color"), cmd("layer.setProps", name="colour"))
        self.assertIn("the group color is missing", reason)

    def test_a_deleted_group_is_refused(self) -> None:
        self.assertIn("the group alpha is missing", self.refused(cmd("layer.select", name="alpha"), cmd("layer.delete")))

    def test_a_base_erased_in_part_is_refused_with_the_count(self) -> None:
        reason = self.refused(
            base_of(self.PLANES, "color"),
            cmd("select.rect", x=0, y=0, width=8, height=4, antiAlias=False),
            cmd("edit.clear"),
            cmd("select.deselect"),
        )
        self.assertIn("the group color has 32 pixels that are not opaque", reason)

    def test_another_depth_is_refused(self) -> None:
        self.assertIn("16 bits a channel", self.refused(cmd("image.mode.bits16")))

    def test_a_file_that_is_no_document_is_refused_and_the_next_whole_one_is_read(self) -> None:
        session = self.open()["session"]
        scratch = self.scratch(session)
        whole = scratch.read_bytes()
        scratch.write_bytes(whole[: len(whole) // 3])  # half written by another program
        state = self.check(session)
        self.assertEqual(state["state"], "edited")
        self.assertIn("the renderer failed", state["reason"])
        scratch.write_bytes(whole)
        self.assertEqual(self.check(session)["state"], "unchanged")
