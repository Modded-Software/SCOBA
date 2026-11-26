"""Requests: a variant is made once, reused, and its state is read, not stored (R-HD-97 to 99, R-HD-120 to 123)."""

from __future__ import annotations

import os
import subprocess
import sys
from unittest import mock

from hdtex.core import encode, progress, requests, results, variants
from hdtex.core.interfaces import FAILED
from hdtex.core.requests import RequestError
from hdtex.core.store import StoreError, file_sha256, write_json
from hdtex.core.variants import VariantError

from testkit.tests.textures.doubles import ROCK, Case
from testkit.tests.textures.fixtures import colour_rgba, normal_rgba, texture_file

SAND = "textures\\sand.dds"
ORIGIN = f"storage\\{ROCK}"
UP = "pbrify@256"  # of a 64 texture: its own size
HALF = "pbrify@128"  # of a 64 texture: the 2x of its 4x model
TWO = "pbrify@64+seedvr2@256"  # of a 16 texture


def no_wait(_seconds: float) -> None:
    return None


def recipe(variant: str) -> str:
    return variants.split(variant)[0]


class RequestCase(Case):
    def make(self, asset: str = ROCK, variant: str = UP, wait=no_wait) -> dict:
        found = self.dataset()
        return requests.make(
            found, self.runner, found.texture(asset), variant, wait=wait
        )

    def read(self, variant: str = UP, origin: str = ORIGIN) -> dict | None:
        return progress.read(
            self.store.game(self.folder_game.id),
            lambda: self.runner,
            origin,
            recipe(variant),
        )

    def entry(self, variant: str = UP, origin: str = ORIGIN) -> dict | None:
        return self.store.game(self.folder_game.id).entry(origin, recipe(variant))

    def note(self, variant: str = UP):
        return (
            self.store.game(self.folder_game.id).recipe_dir(ORIGIN, recipe(variant))
            / progress.FILE
        )

    def models(self) -> list[str]:
        return [model for _plane, model in self.runner.asked]


class MakeTest(RequestCase):
    def test_a_request_makes_the_variant_and_leaves_no_request_behind(self) -> None:
        self.add()
        self.assertIsNone(self.read())
        made = self.make()
        self.assertEqual(made["files"], self.entry()["files"])
        self.assertEqual((made["recipe"], made["size"]), ("pbrify", [256, 256]))
        self.assertEqual(made["original"]["size"], [64, 64])
        self.assertEqual(made["models"], {"color": "pbrify", "alpha": "fast"})
        self.assertEqual(made["runner"], "v1")
        self.assertEqual(self.models(), ["pbrify", "fast"])
        self.assertTrue(
            self.store.game(self.folder_game.id)
            .variant_file(ORIGIN, "pbrify", 256)
            .is_file()
        )
        self.assertFalse(self.note().exists())
        self.assertIsNone(self.read())

    def test_a_texture_without_colour_gets_fast_on_every_plane(self) -> None:
        self.folder_game.add(
            "one", ROCK, texture_file("normal", normal_rgba()), role="normal"
        )
        made = self.make(variant="fast@256")
        self.assertEqual(made["models"], {"normal": "fast"})
        self.assertEqual(self.models(), ["fast"])

    def test_a_longer_recipe_makes_the_recipes_before_it(self) -> None:
        self.add(size=16)
        made = self.make(variant=TWO)
        self.assertEqual(self.entry("pbrify@64")["size"], [64, 64])
        self.assertEqual(made["size"], [256, 256])
        self.assertEqual(made["models"], {"color": "seedvr2", "alpha": "fast"})
        self.assertEqual(self.models(), ["pbrify", "fast", "seedvr2", "fast"])

    def test_a_flip_book_keeps_its_size(self) -> None:
        self.add(grid=[2, 2])
        made = self.make()
        self.assertEqual((made["size"], made["grid"]), ([256, 256], [2, 2]))


class ReuseTest(RequestCase):
    def test_a_variant_that_is_there_is_not_made_again(self) -> None:
        self.add()
        first = self.make()
        self.assertEqual(self.make()["files"], first["files"])
        self.assertEqual(len(self.runner.asked), 2)

    def test_a_plane_upscaled_before_is_not_upscaled_again(self) -> None:
        self.add()
        self.make()
        self.add(seed=2)
        self.make()
        self.add(seed=1)
        self.make()
        self.assertEqual(len(self.runner.asked), 4)

    def test_a_longer_recipe_starts_from_the_variant_that_is_there(self) -> None:
        self.add(size=16)
        self.make(variant="pbrify@64")
        self.make(variant=TWO)
        self.assertEqual(self.models(), ["pbrify", "fast", "seedvr2", "fast"])

    def test_a_changed_original_is_made_again(self) -> None:
        self.add()
        old = self.make()
        self.add(seed=2)
        new = self.make()
        self.assertNotEqual(new["original"]["sha256"], old["original"]["sha256"])
        self.assertEqual(len(self.runner.asked), 4)

    def test_equal_planes_of_two_textures_are_upscaled_once(self) -> None:
        rgba = colour_rgba()
        other = rgba.copy()
        other[:, :, :3] = 255 - rgba[:, :, :3]
        self.folder_game.add("one", ROCK, texture_file("diffuse", rgba))
        self.folder_game.add("one", SAND, texture_file("diffuse", other))
        self.make(ROCK)
        self.make(SAND)
        self.assertEqual(sorted(self.models()), ["fast", "pbrify", "pbrify"])

    def test_another_version_of_the_upscaler_shares_no_plane(self) -> None:
        # Three textures with the same pixels: equal planes, one variant each.
        self.add()
        self.make()
        self.add(SAND)
        self.runner.tool = "v2"
        self.assertEqual(self.make(SAND)["runner"], "v2")
        self.assertEqual(len(self.runner.asked), 4)
        # Negative: the same version shares them.
        self.add("textures\\moss.dds")
        self.make("textures\\moss.dds")
        self.assertEqual(len(self.runner.asked), 4)


class TilingTest(RequestCase):
    def test_a_texture_that_repeats_is_upscaled_with_matched_edges_and_says_so(self) -> None:
        self.add()
        made = self.make()
        self.assertEqual(self.runner.tiling, [True, True])
        self.assertIs(made["tiles"], True)

    def test_a_texture_that_does_not_repeat_is_upscaled_and_joined_with_its_edges_apart(self) -> None:
        self.folder_game.add("one", ROCK, texture_file("diffuse", colour_rgba()), tiles=False)
        with mock.patch.object(encode, "encode", wraps=encode.encode) as joined:
            made = self.make()
        self.assertEqual(self.runner.tiling, [False, False])
        self.assertIs(made["tiles"], False)
        self.assertIs(joined.call_args.kwargs["tiles"], False)

    def test_an_upscale_with_matched_edges_is_not_reused_for_a_texture_that_does_not_repeat(self) -> None:
        self.add()
        self.make()
        self.folder_game.add("one", ROCK, texture_file("diffuse", colour_rgba()), tiles=False)
        made = self.make()
        # Made again, each plane asked for again without matched edges: the matched upscale is another one.
        self.assertEqual(self.runner.tiling, [True, True, False, False])
        self.assertIs(made["tiles"], False)

    def test_a_variant_with_matched_edges_of_a_texture_that_does_not_repeat_is_shown_not_stale_and_marked(self) -> None:
        self.add()
        made = self.make()
        self.folder_game.add("one", ROCK, texture_file("diffuse", colour_rgba()), tiles=False)
        found = self.dataset()
        texture = found.texture(ROCK)
        recipes = results.of(self.store.game(self.folder_game.id), texture, made["original"]["sha256"])
        # Not stale: it is shown and may be baked (operator 2026-11-26). Marked, so a request makes it again.
        self.assertEqual((recipes["pbrify"].stale, recipes["pbrify"].why_stale, recipes["pbrify"].edges_off), (False, "", True))
        self.assertEqual(results.refusal(recipes, UP), "")
        # Negative: the texture as it was made, repeating, is not marked.
        tiled = results.of(self.store.game(self.folder_game.id), texture._replace(tiles=True), made["original"]["sha256"])
        self.assertFalse(tiled["pbrify"].edges_off)

    def test_an_entry_without_the_edge_rule_is_refused_and_an_edit_is_never_off(self) -> None:
        self.folder_game.add("one", ROCK, texture_file("diffuse", colour_rgba()), tiles=False)
        self.make()
        entry = self.entry()
        self.assertIs(results.made_tiling(entry), False)
        del entry[results.TILES]
        with self.assertRaisesRegex(StoreError, "has no 'tiles'"):
            results.made_tiling(entry)
        # Negative: a person's edit is never off: it is not upscaled, and its key is not read.
        self.assertFalse(results.edges_off({**entry, results.EDIT: {"changed": ["color"]}}, True))


class RefusalTest(RequestCase):
    def nothing_is_left(self) -> None:
        self.assertEqual(self.runner.asked, [])
        self.assertFalse(self.store.game(self.folder_game.id).variants.exists())

    def test_a_texture_without_a_role_is_refused_with_its_reason(self) -> None:
        self.folder_game.add("one", SAND, b"", role=None, reason="it is a cube map")
        with self.assertRaises(RequestError) as refused:
            self.make(SAND)
        self.assertIn("it is a cube map", str(refused.exception))
        self.assertEqual(self.folder_game.read, [])
        self.nothing_is_left()

    def test_a_recipe_that_adds_nothing_is_refused_before_any_job(self) -> None:
        self.add()
        with (
            mock.patch.object(variants, "MAX_OUTPUT", 256),
            self.assertRaises(RequestError) as refused,
        ):
            self.make(variant="pbrify@256+pbrify@256")
        self.assertIn("can add nothing", str(refused.exception))
        self.nothing_is_left()

    def test_a_size_the_variant_cannot_have_is_refused_before_any_job(self) -> None:
        self.add()
        with self.assertRaises(RequestError) as refused:
            self.make(variant="pbrify@4096")
        self.assertIn("not at 4096", str(refused.exception))
        self.nothing_is_left()

    def test_a_texture_without_colour_is_refused_any_model_but_fast(self) -> None:
        self.folder_game.add(
            "one", ROCK, texture_file("normal", normal_rgba()), role="normal"
        )
        for variant in (UP, "fast@256+seedvr2@1024"):
            with self.assertRaises(RequestError, msg=variant) as refused:
                self.make(variant=variant)
            self.assertIn("use fast", str(refused.exception))
        self.nothing_is_left()

    def test_the_original_is_not_made(self) -> None:
        self.add()
        with self.assertRaises(RequestError):
            self.make(variant=variants.ORIGINAL)
        self.nothing_is_left()

    def test_an_original_that_is_no_texture_is_refused(self) -> None:
        self.folder_game.add("one", SAND, b"not a texture")
        with self.assertRaises(RequestError) as refused:
            self.make(SAND)
        self.assertIn("cannot be read", str(refused.exception))
        self.nothing_is_left()

    def test_text_that_names_no_variant_is_refused_and_leaves_no_request(self) -> None:
        self.add()
        for text in ("sharpen@256", "pbrify"):
            with self.assertRaises(VariantError, msg=text):
                self.make(variant=text)
        self.nothing_is_left()


class StateTest(RequestCase):
    def test_the_state_follows_the_upscalers_queue(self) -> None:
        self.add()
        self.runner.hold = True
        seen: list[str] = []

        def wait(_seconds: float) -> None:
            seen.append(self.read()["state"])
            self.runner.advance()

        encoder = encode.encode

        def watched(*args, **kwargs):
            seen.append(self.read()["state"])
            return encoder(*args, **kwargs)

        with mock.patch.object(encode, "encode", watched):
            self.make(wait=wait)
        self.assertEqual(
            seen,
            [
                progress.QUEUED,
                progress.UPSCALING,
                progress.UPSCALING,
                progress.ENCODING,
            ],
        )
        self.assertIsNone(self.read())

    def test_a_request_says_its_step_and_its_planes(self) -> None:
        self.add(size=16)
        self.runner.hold = True
        seen: list[tuple[int, int, int]] = []

        def wait(_seconds: float) -> None:
            state = self.read(TWO)
            seen.append((state["step"], state["steps"], state["planes"]))
            self.runner.advance()

        self.make(variant=TWO, wait=wait)
        self.assertEqual(sorted(set(seen)), [(1, 2, 2), (2, 2, 2)])

    def by(self, pid: int, began: int | None) -> dict:
        """The state of a request that the given process is said to make."""
        write_json(
            self.note(),
            {
                "pid": pid,
                "started": began,
                "step": 1,
                "steps": 1,
                "phase": progress.UPSCALING,
                "jobs": [],
                "failed": "",
            },
        )
        return self.read()

    def test_a_request_whose_program_is_gone_has_failed(self) -> None:
        self.add()
        gone = subprocess.Popen([sys.executable, "-c", "pass"])
        began = progress.started(gone.pid)
        gone.wait()
        self.assertIsNotNone(began)
        self.assertIsNone(progress.started(gone.pid))
        state = self.by(gone.pid, began)
        self.assertEqual(state["state"], FAILED)
        self.assertIn(
            f"process {gone.pid}) stopped before it was done", state["reason"]
        )
        self.assertEqual(
            self.by(os.getpid(), progress.started(os.getpid()))["state"],
            progress.QUEUED,
        )

    def test_another_program_with_the_same_process_id_is_not_taken_for_the_one_that_asked(
        self,
    ) -> None:
        self.add()
        state = self.by(os.getpid(), progress.started(os.getpid()) - 1)
        self.assertEqual(state["state"], FAILED)
        self.assertIn("stopped before it was done", state["reason"])

    def test_a_request_names_its_log(self) -> None:
        self.add()
        self.assertEqual(
            self.by(os.getpid(), progress.started(os.getpid()))["log"],
            str(self.note().with_name(progress.LOG_FILE)),
        )


class FailureTest(RequestCase):
    def test_a_failed_job_fails_the_request_with_the_upscalers_reason(self) -> None:
        self.add()
        self.runner.fail = {"fast": "out of GPU memory"}
        with self.assertRaises(RequestError) as failed:
            self.make()
        self.assertIn("out of GPU memory", str(failed.exception))
        self.assertIsNone(self.entry())
        state = self.read()
        self.assertEqual(state["state"], FAILED)
        self.assertIn("out of GPU memory", state["reason"])

    def test_asking_again_keeps_the_planes_that_were_made(self) -> None:
        self.add()
        self.runner.fail = {"fast": "out of GPU memory"}
        with self.assertRaises(RequestError):
            self.make()
        self.runner.fail = {}
        self.assertEqual(self.make()["size"], [256, 256])
        self.assertEqual(self.models(), ["pbrify", "fast", "fast"])
        self.assertIsNone(self.read())

    def test_a_job_that_wrote_nothing_fails_the_request(self) -> None:
        self.add()
        self.runner.empty = True
        with self.assertRaises(RequestError) as failed:
            self.make()
        self.assertIn("job 0001.json is done and wrote nothing", str(failed.exception))
        self.assertIsNone(self.entry())

    def test_a_job_that_left_the_queue_fails_the_request_at_once(self) -> None:
        self.add()
        self.runner.hold = True
        waits: list[float] = []

        def wait(seconds: float) -> None:
            waits.append(seconds)
            self.runner.forget()

        with self.assertRaises(RequestError) as failed:
            self.make(wait=wait)
        self.assertIn("job 0001.json is not in the queue", str(failed.exception))
        self.assertEqual(len(waits), 1)
        self.assertIn("is not in the queue", self.read()["reason"])

    def test_a_job_that_is_gone_is_asked_for_again_by_the_next_request(self) -> None:
        self.add()
        self.runner.fail = {"fast": "out of GPU memory"}
        with self.assertRaises(RequestError):
            self.make()
        self.runner.fail = {}
        self.runner.forget()
        self.assertEqual(self.make()["size"], [256, 256])
        self.assertEqual(self.models(), ["pbrify", "fast", "fast"])

    def test_every_half_file_is_named_and_kept_aside_and_the_next_request_is_whole(
        self,
    ) -> None:
        self.add()
        self.runner.broken = True
        with self.assertRaises(RequestError) as failed:
            self.make()
        said = str(failed.exception)
        self.assertIn("left 2 broken files", said)
        upscaled = self.store.game(self.folder_game.id).upscaled
        self.assertEqual(list(upscaled.glob("*/*.png")), [])
        kept = sorted(upscaled.glob(f"*/*{requests.BROKEN}"))
        self.assertEqual(len(kept), 2)
        for path in kept:
            self.assertEqual(path.stat().st_size, 40)
            self.assertIn(
                f"(40 bytes, sha256 {file_sha256(path)}); kept as {path.name}", said
            )
        self.assertIsNone(self.entry())
        self.runner.broken = False
        self.assertEqual(self.make()["size"], [256, 256])
        self.assertEqual(len(self.runner.asked), 4)

    def test_an_output_of_another_size_fails_the_request(self) -> None:
        self.add()
        self.runner.enlarge = lambda image: image.repeat(2, axis=0).repeat(2, axis=1)
        with self.assertRaises(RequestError) as failed:
            self.make()
        self.assertIn("not 4 times as much", str(failed.exception))
        self.assertIsNone(self.entry())


class WorkerTest(RequestCase):
    def test_jobs_that_wait_with_no_worker_fail_the_request_with_the_reason(
        self,
    ) -> None:
        self.add()
        self.runner.hold = True
        self.runner.no_worker = "no worker runs on the queue /q"
        waits: list[float] = []
        with self.assertRaises(RequestError) as failed:
            self.make(wait=waits.append)
        self.assertIn(
            "2 jobs waited 30 s and no worker runs on the queue /q",
            str(failed.exception),
        )
        self.assertEqual(sum(waits), requests.IDLE_LIMIT_SECONDS)
        self.assertEqual(
            self.runner.looks, 4, "one look every ten seconds, not one per poll"
        )
        self.assertEqual(self.read()["state"], FAILED)
        self.assertIsNone(self.entry())

    def test_jobs_that_wait_behind_a_worker_are_waited_for(self) -> None:
        self.add()
        self.runner.hold = True
        waits: list[float] = []

        def wait(seconds: float) -> None:
            waits.append(seconds)
            if sum(waits) > 3 * requests.IDLE_LIMIT_SECONDS:
                self.runner.advance()

        self.assertEqual(self.make(wait=wait)["size"], [256, 256])
        self.assertGreater(sum(waits), 3 * requests.IDLE_LIMIT_SECONDS)

    def test_a_worker_that_starts_in_time_is_waited_for(self) -> None:
        self.add()
        self.runner.hold = True
        self.runner.no_worker = "no worker runs"
        waits: list[float] = []

        def wait(seconds: float) -> None:
            waits.append(seconds)
            if sum(waits) >= requests.IDLE_LIMIT_SECONDS - requests.IDLE_LOOK_SECONDS:
                self.runner.no_worker = ""
                self.runner.advance()

        self.assertEqual(self.make(wait=wait)["size"], [256, 256])

    def test_a_second_request_for_a_plane_waits_for_the_job_that_is_asked_for(
        self,
    ) -> None:
        self.add()
        self.runner.hold = True
        self.runner.no_worker = "no worker runs"
        with self.assertRaises(RequestError):
            self.make()
        self.assertEqual(len(self.runner.asked), 2)
        self.runner.no_worker = ""
        self.assertEqual(
            self.make(wait=lambda _seconds: self.runner.advance())["size"], [256, 256]
        )
        self.assertEqual(len(self.runner.asked), 2, "no job is asked for twice")
