"""The transfer of an edit to a new variant, and the limits of a user-made variant (R-PC-50 to 59, R-PC-80 to 83).

These tests need PhotoCraft's renderer (`make install-photocraft`).
"""

from __future__ import annotations

import subprocess
from unittest import mock

from hdtex.core import dds, edits, edittransfer, encode, limits, photocraft, progress, results, variants
from hdtex.core.interfaces import FAILED
from hdtex.core.roles import ROLES
from hdtex.core.store import file_sha256

from testkit.tests.textures.doubles import ROCK
from testkit.tests.textures.edit_fixtures import ORIGIN, EditCase, base_of, cmd, painted, run_on
from testkit.tests.textures.fixtures import invert
from testkit.tests.textures.test_cli import ROOM, UP

EDIT_ID = r"edit[0-9a-f]{12}"


class TransferCase(EditCase):
    def edited(self, *steps: list[str], variant: str | None = None) -> str:
        """A session whose scratch was changed and checked."""
        session = self.open(variant)["session"]
        self.change(session, *(steps or (painted(self.PLANES, "color"), cmd("layer.setProps", blend="Multiply"))))
        return session

    def inverted(self, variant: str | None = None) -> str:
        """A session whose colour is turned around: another picture than its input."""
        return self.edited(base_of(self.PLANES, "color"), cmd("layer.newAdjustmentLayer.invert"), variant=variant)

    def transfer(self, session: str) -> str:
        """Transfer a session. Returns the id of the variant it made."""
        [made] = self.ok("edit", "transfer", "--session", session)["made"]
        return made["variant"]

    def entry(self, variant: str) -> dict:
        found = self.game.entry(ORIGIN, variants.split(variant)[0])
        self.assertIsNotNone(found, variant)
        return found

    def shown(self, variant: str) -> dict:
        """The variant in the texture's state, as the state index holds it."""
        [found] = [item for item in self.indexed()["variants"] if item["id"] == variant]
        return found

    def original_file(self):
        return self.root / "game" / "storage" / ROCK.replace("\\", "/")


class TransferTest(TransferCase):
    def test_a_transfer_makes_one_variant_of_the_rendered_planes_and_changes_nothing_else(self) -> None:
        original = file_sha256(self.original_file())
        session = self.edited()
        folder = self.folder(session)
        record, said = edits.read_record(self.game, session), edits.read_said(folder)
        variant = self.transfer(session)
        digest = edittransfer.planes_digest(record, said)
        self.assertRegex(variant, rf"^{EDIT_ID}@64$")
        self.assertEqual(variant, variants.edited("original", digest, 64))
        entry = self.entry(variant)
        self.assertEqual(entry["edit"], {"input": "original", "changed": ["color"], "hash": digest, "session": session})
        self.assertEqual(entry["models"], {"color": "edit", "alpha": None})
        self.assertIsNone(entry["runner"])
        self.assertEqual((list(entry["files"]), entry["size"]), (["64"], [64, 64]))
        # The changed plane is the rendered one; the other is the input's own, in the role's shape.
        self.assertTrue((self.game.get_plane(entry["planes"]["color"]) == self.picture(session, "rendered", "color")).all())
        alpha = self.game.get_plane(entry["planes"]["alpha"])
        self.assertEqual(alpha.ndim, 2)
        self.assertTrue((alpha == self.picture(session, "base", "alpha")[:, :, 0]).all())
        # The file has the original's layout and shows the edit: red in Multiply leaves no green and no blue.
        was = dds.parse(self.original_file().read_bytes())
        data = self.game.variant_file(ORIGIN, entry["recipe"], 64).read_bytes()
        header, rgba = encode.read_texture(data)
        self.assertEqual((header.format, header.width, header.height), (was.format, 64, 64))
        self.assertLessEqual(int(rgba[:, :, 1:3].max()), 8)
        self.assertGreater(int(encode.read_texture(self.original_file().read_bytes())[1][:, :, 1:3].min()), 30)
        # The index lists it, with no request left behind.
        shown = self.shown(variant)
        self.assertEqual((shown["input"], shown["title"], shown["edited"], shown["size"]), ("original", "Edit at 64", True, 64))
        self.assertEqual(self.indexed()["requests"], {})
        self.assertFalse((self.game.recipe_dir(ORIGIN, entry["recipe"]) / progress.FILE).exists())
        state = self.check(session)
        self.assertEqual((state["state"], state["transfers"]), ("transferred", [variant]))
        # Negative: the original is the file it was, and nothing was handed to the upscaler.
        self.assertEqual(file_sha256(self.original_file()), original)
        self.assertEqual(self.runner.asked, [])

    def test_an_edit_is_joined_across_the_border_only_for_a_texture_that_tiles(self) -> None:
        found = {}
        for tiles in (True, False):
            self.add(tiles=tiles)
            with mock.patch.object(edittransfer.encode, "encode", wraps=encode.encode) as called:
                variant = self.transfer(self.edited() if tiles else self.inverted())
            found[tiles] = (called.call_args.kwargs["tiles"], self.entry(variant)[results.TILES], self.shown(variant)["stale"])
        # Negative: the one that does not tile is not joined across it; neither is stale.
        self.assertEqual(found, {True: (True, True, False), False: (False, False, False)})

    def test_the_same_scratch_twice_is_one_variant(self) -> None:
        session = self.edited()
        first = self.transfer(session)
        file = self.game.variant_file(ORIGIN, variants.split(first)[0], 64)
        written = file.stat().st_mtime_ns
        self.assertEqual(self.transfer(session), first)
        self.assertEqual(self.recipes(), [variants.split(first)[0]])
        self.assertEqual(file.stat().st_mtime_ns, written, "negative: the variant was not made again")
        self.assertEqual(len(edits.read_record(self.game, session)["transfers"]), 1)

    def test_an_edit_after_a_transfer_is_edited_again_and_makes_a_second_variant(self) -> None:
        session = self.edited()
        first = self.transfer(session)
        state = self.change(session, painted(self.PLANES, "alpha", colour="#ffffff", name="mask"))
        self.assertEqual((state["state"], state["changed"]), ("edited", ["color", "alpha"]))
        second = self.transfer(session)
        self.assertNotEqual(second, first)
        self.assertEqual(len(self.recipes()), 2)
        self.assertEqual(self.entry(second)["models"], {"color": "edit", "alpha": "edit"})
        self.assertEqual(self.check(session)["transfers"], [first, second])

    def test_a_scratch_with_no_changed_plane_is_refused(self) -> None:
        session = self.open()["session"]
        self.assertIn("changes no plane", self.error("edit", "transfer", "--session", session))
        self.assertEqual(self.recipes(), [])

    def test_a_transfer_checks_a_scratch_that_changed_since_its_check(self) -> None:
        session = self.open()["session"]
        run_on(self.scratch(session), painted(self.PLANES, "color"))
        self.assertFalse(edits.state(self.dataset(), session)["checked"])
        self.assertRegex(self.transfer(session), rf"^{EDIT_ID}@64$")

    def test_a_stopped_transfer_leaves_no_variant_and_says_so(self) -> None:
        session = self.edited()
        with mock.patch.object(encode, "encode", side_effect=KeyboardInterrupt("stopped")), self.assertRaises(KeyboardInterrupt):
            self.call("edit", "transfer", "--session", session)
        self.assertEqual(self.recipes(), [], "negative: no variant")
        [(recipe, request)] = self.indexed()["requests"].items()
        self.assertRegex(recipe, rf"^{EDIT_ID}$")
        self.assertEqual(request["state"], FAILED)
        self.assertIn("KeyboardInterrupt", request["reason"])
        self.assertEqual(self.check(session)["state"], "edited")
        # Asked again, it is made, and the failed request is gone.
        variant = self.transfer(session)
        self.assertEqual(variants.split(variant)[0], recipe)
        self.assertEqual(self.indexed()["requests"], {})

    def test_an_edit_of_a_models_variant_joins_its_id_and_keeps_its_other_planes(self) -> None:
        self.ok("request", "--asset", ROCK, "--variant", UP)
        input_file = self.game.variant_file(ORIGIN, "pbrify", 256)
        before = file_sha256(input_file)
        asked = len(self.runner.asked)
        session = self.edited(variant=UP)
        self.assertEqual(self.check(session)["size"], [256, 256])
        variant = self.transfer(session)
        self.assertRegex(variant, rf"^pbrify@256\+{EDIT_ID}@256$")
        entry = self.entry(variant)
        self.assertEqual(entry["models"], {"color": "edit", "alpha": "fast"})
        self.assertEqual(self.shown(variant)["input"], UP)
        self.assertEqual(self.shown(variant)["title"], "PBRify, then Edit at 256")
        # Negative: the input variant is the file it was, and no job was asked for.
        self.assertEqual(file_sha256(input_file), before)
        self.assertEqual(len(self.runner.asked), asked)

    def test_a_request_cannot_make_an_edit(self) -> None:
        session = self.edited()
        variant = self.transfer(session)
        self.ok("edit", "discard", "--session", session)
        self.assertTrue(self.game.variant_file(ORIGIN, variants.split(variant)[0], 64).is_file(), "the variant stays")
        self.assertIn("a transfer of the edit makes it", self.error("request", "--asset", ROCK, "--variant", "edit0123456789ab@64"))


class NoGpuTest(TransferCase):
    def test_a_transfer_finishes_with_an_upscaler_that_refuses_every_job_and_the_renderer_runs_without_a_gpu(self) -> None:
        self.runner.fail = dict.fromkeys(variants.MODELS, "no GPU")
        real = subprocess.run
        commands: list[list[str]] = []

        def recorded(command, *args, **kwargs):
            commands.append(list(command))
            return real(command, *args, **kwargs)

        with mock.patch.object(subprocess, "run", recorded):
            variant = self.transfer(self.edited())
        self.assertRegex(variant, rf"^{EDIT_ID}@64$")
        composing = [command for command in commands if command[1] == "run"]
        self.assertGreaterEqual(len(composing), 3, "the scratch was built and rendered")
        for command in composing:
            self.assertEqual(command[0], str(photocraft.program()))
            self.assertIn(photocraft.NO_GPU, command)
        self.assertEqual(self.runner.asked, [])


class LimitsTest(TransferCase):
    def bake(self, variant: str) -> tuple[int, dict]:
        self.hd(variant)
        return self.call("bake", "--owner", ROOM, "--skin", "hd")

    def test_a_user_made_variant_far_from_its_original_has_its_numbers_no_problem_and_is_baked(self) -> None:
        variant = self.transfer(self.inverted())
        numbers = self.entry(variant)["numbers"]
        self.assertEqual(sorted(numbers), ["coarse_rmse", "encode_psnr", "fidelity_corr", "fidelity_psnr", "seam", "seam_source"])
        # A model's variant with these numbers would miss a limit.
        self.assertIn("correlation", [miss["limit"] for miss in limits.missed(numbers, True)])
        shown = self.shown(variant)
        self.assertEqual(shown["problems"], [])
        self.assertEqual([number["limit"] for number in shown["numbers"]], ["encode_psnr", "correlation", "coarse_rmse", "seam"])
        self.assertEqual({number["band"] for number in shown["numbers"]}, {limits.NONE})
        self.assertLess(next(number["value"] for number in shown["numbers"] if number["limit"] == "correlation"), 0)
        status, answer = self.bake(variant)
        self.assertEqual((status, answer.get("textures")), (0, {ROCK: variant}))

    def test_a_models_variant_with_such_pixels_has_the_problem_and_its_bake_is_refused(self) -> None:
        self.runner.enlarge = invert
        self.ok("request", "--asset", ROCK, "--variant", UP)
        shown = self.shown(UP)
        self.assertEqual(shown["edited"], False)
        self.assertIn("correlation", [miss["limit"] for miss in shown["problems"]])
        self.assertIn(limits.PROBLEM, {number["band"] for number in shown["numbers"]})
        status, answer = self.bake(UP)
        self.assertEqual(status, 1)
        self.assertIn("has problems", answer["error"])

    def upscaled(self, edit: str) -> str:
        """A model's variant made from the edited variant `edit`."""
        [made] = self.ok("request", "--asset", ROCK, "--input", edit, "--model", "pbrify", "--factor", "4")["made"]
        return made["variant"]

    def test_a_models_variant_made_from_an_edit_is_compared_with_the_edit(self) -> None:
        edit = self.transfer(self.inverted())
        variant = self.upscaled(edit)
        self.assertRegex(variant, rf"^{EDIT_ID}@64\+pbrify@256$")
        entry = self.entry(variant)
        self.assertEqual(entry["reference"], edit)
        shown = self.shown(variant)
        self.assertEqual((shown["edited"], shown["reference"], shown["problems"]), (False, edit, []))
        self.assertNotIn(limits.NONE, {number["band"] for number in shown["numbers"]}, "the limits bind a model's variant")
        # Against the original, the same planes miss the limit: so the reference was the edit.
        planes = {name: self.game.get_plane(key) for name, key in entry["planes"].items()}
        against_original = encode.encode(self.original_file().read_bytes(), ROLES.get("diffuse"), planes).numbers
        self.assertIn("correlation", [miss["limit"] for miss in limits.missed(against_original, True)])
        status, answer = self.bake(variant)
        self.assertEqual((status, answer.get("textures")), (0, {ROCK: variant}))

    def test_a_models_variant_far_from_its_user_made_input_has_the_problem(self) -> None:
        edit = self.transfer(self.inverted())
        self.runner.enlarge = invert  # the model turns the edit around again
        variant = self.upscaled(edit)
        shown = self.shown(variant)
        self.assertEqual(shown["reference"], edit)
        self.assertIn("correlation", [miss["limit"] for miss in shown["problems"]])
        status, answer = self.bake(variant)
        self.assertEqual(status, 1)
        self.assertIn("has problems", answer["error"])

    def test_a_variant_with_no_edit_among_its_inputs_keeps_the_original_as_its_reference(self) -> None:
        self.ok("request", "--asset", ROCK, "--variant", UP)
        self.assertEqual(self.entry(UP)["reference"], "")
        shown = self.shown(UP)
        self.assertEqual((shown["reference"], shown["problems"]), ("", []))
