"""Requests on a kept recipe: it is never made again, a chain takes it as it is, and one request keeps one size
(R-HD-158, R-HD-159, R-HD-123)."""

from __future__ import annotations

from unittest import mock

from hdtex.core import dds, encode, results, variants
from hdtex.core.interfaces import FAILED
from hdtex.core.requests import RequestError
from hdtex.core.roles import ROLES
from hdtex.core.store import ENTRY, plane_key, write_json

from testkit.tests.textures.doubles import ROCK
from testkit.tests.textures.fixtures import colour_rgba, texture_file
from testkit.tests.textures.test_requests import (
    HALF,
    ORIGIN,
    TWO,
    UP,
    RequestCase,
    recipe,
)


class KeptCase(RequestCase):
    """A kept variant, marked by a person, and what its folder holds byte for byte."""

    MARK = "a person looked at it"

    def game(self):
        return self.store.game(self.folder_game.id)

    def folder(self, variant: str = UP):
        return self.game().recipe_dir(ORIGIN, recipe(variant))

    def held(self, variant: str = UP) -> dict[str, bytes]:
        return {path.name: path.read_bytes() for path in sorted(self.folder(variant).iterdir())}

    def rewrite(self, variant: str = UP, **fields: object) -> dict:
        """Write fields into a kept entry, as a person or an older store did."""
        entry = {**self.entry(variant), **fields}
        write_json(self.folder(variant) / ENTRY, entry)
        return entry

    def no_longer_repeats(self) -> None:
        """The same file, described as not repeating: the kept variant's edges are of the other rule."""
        self.folder_game.add("one", ROCK, texture_file("diffuse", colour_rgba()), tiles=False)


class ImmutableTest(KeptCase):
    """R-HD-158: a request never writes a kept variant again; it makes a revision beside it."""

    def test_a_request_of_a_variant_with_edges_of_the_other_rule_makes_a_revision_beside_it(self) -> None:
        self.add()
        self.make()
        self.rewrite(accepted=self.MARK)
        before = self.held()
        self.no_longer_repeats()
        made = self.make()
        self.assertEqual((made["recipe"], made["tiles"]), ("pbrify~2", False))
        self.assertEqual(self.runner.tiling, [True, True, False, False])
        self.assertTrue(self.game().variant_file(ORIGIN, "pbrify~2", 256).is_file())
        self.assertNotIn(results.ACCEPTED, made)
        # Negative: the kept one is the same byte for byte, mark and all, and no request is left in either folder.
        self.assertEqual(self.held(), before)
        self.assertEqual(self.entry()[results.ACCEPTED], self.MARK)
        self.assertIs(self.entry()["tiles"], True)
        self.assertIsNone(self.read())
        self.assertIsNone(self.read("pbrify~2@256"))

    def test_a_second_request_finds_the_revision_and_makes_no_third(self) -> None:
        self.add()
        self.make()
        self.no_longer_repeats()
        first = self.make()
        asked = len(self.runner.asked)
        again = self.make()
        self.assertEqual((again["recipe"], again["files"]), ("pbrify~2", first["files"]))
        # Negative: no job, and no further revision.
        self.assertEqual(len(self.runner.asked), asked)
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify", "pbrify~2"])

    def test_a_stale_variant_stays_and_each_new_original_gets_the_next_revision(self) -> None:
        self.add()
        old = self.make()
        self.rewrite(accepted=self.MARK)
        before = self.held()
        self.add(seed=2)
        second = self.make()
        self.assertEqual(second["recipe"], "pbrify~2")
        self.assertNotEqual(second["original"]["sha256"], old["original"]["sha256"])
        self.add(seed=3)
        third = self.make()
        self.assertEqual(third["recipe"], "pbrify~3")
        # Asked by the id of a revision that cannot serve it: the first above it that can.
        asked = len(self.runner.asked)
        self.assertEqual(self.make(variant="pbrify~2@256")["recipe"], "pbrify~3")
        self.assertEqual(len(self.runner.asked), asked)
        # Negative: the first and the second are as they were.
        self.assertEqual(self.held(), before)
        self.assertEqual(self.entry("pbrify~2@256"), second)
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify", "pbrify~2", "pbrify~3"])

    def test_an_original_that_is_back_is_served_by_the_variant_made_of_it(self) -> None:
        self.add()
        old = self.make()
        self.add(seed=2)
        self.make()
        self.add(seed=1)
        asked = len(self.runner.asked)
        self.assertEqual(self.make(), old)
        self.assertEqual(len(self.runner.asked), asked)
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify", "pbrify~2"])

    def test_a_failed_revision_is_asked_again_under_its_own_id(self) -> None:
        self.add()
        self.make()
        before = self.held()
        self.no_longer_repeats()
        self.runner.fail = {"pbrify": "out of memory"}
        with self.assertRaisesRegex(RequestError, "out of memory"):
            self.make()
        self.assertEqual(self.read("pbrify~2@256")["state"], FAILED)
        self.assertEqual(self.read("pbrify~2@256")["variant"], "pbrify~2@256")
        self.runner.fail = {}
        self.assertEqual(self.make()["recipe"], "pbrify~2")
        # Negative: the failure left nothing in the kept folder, and made no third.
        self.assertEqual(self.held(), before)
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify", "pbrify~2"])


class MeanwhileTest(KeptCase):
    """R-HD-158: of two requests that make one recipe at once, the second takes what the first kept."""

    def test_a_request_that_finds_its_recipe_made_meanwhile_takes_it_and_removes_nothing(self) -> None:
        self.add()
        real = encode.encode
        other: list[dict] = []
        held: list[dict[str, bytes]] = []
        entered: list[bool] = []

        def encode_after_another(*args: object, **kwargs: object):
            if not entered:
                entered.append(True)  # set first: the other request encodes too
                # Another program makes the same recipe while this one is between its upscale and its write.
                other.append(self.make())
                held.append({name: data for name, data in self.held().items() if name.endswith((".dds", ENTRY))})
            return real(*args, **kwargs)

        with mock.patch.object(encode, "encode", encode_after_another):
            made = self.make()
        self.assertEqual(made, other[0])
        # Negative: the other one's files are the same byte for byte, no request is left, no revision came.
        self.assertEqual({name: data for name, data in self.held().items() if name.endswith((".dds", ENTRY))}, held[0])
        self.assertIsNone(self.read())
        self.assertFalse(self.note().exists())
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify"])


class ChainTest(KeptCase):
    """R-HD-159: a step before the last takes the kept variant its id names; it is not made again."""

    FIRST = "pbrify@64"  # the first step of TWO, of a 16 texture

    def first(self) -> dict[str, bytes]:
        self.add(size=16)
        self.make(variant=self.FIRST)
        self.rewrite(self.FIRST, accepted=self.MARK)
        return self.held(self.FIRST)

    def test_a_first_step_kept_without_its_planes_is_read_from_its_file(self) -> None:
        self.add(size=16)
        self.make(variant=self.FIRST)
        self.rewrite(self.FIRST, accepted=self.MARK, planes={})
        before = self.held(self.FIRST)
        asked = len(self.runner.asked)
        made = self.make(variant=TWO)
        self.assertEqual((made["recipe"], made["size"]), ("pbrify@64+seedvr2", [256, 256]))
        # The plane the second step took is the colour of the kept file, decoded.
        rgba = encode.read_texture(before["64.dds"])[1]
        colour = ROLES.get("diffuse").split(rgba)["color"]
        self.assertEqual(self.runner.asked[asked:], [(f"{plane_key(colour)}.png", "seedvr2"), mock.ANY])
        # Negative: no job for the kept step, its folder the same byte for byte, no revision of it.
        self.assertEqual(self.models()[asked:], ["seedvr2", "fast"])
        self.assertEqual(self.held(self.FIRST), before)
        self.assertEqual(self.entry(self.FIRST)[results.ACCEPTED], self.MARK)
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify", "pbrify@64+seedvr2"])

    def test_a_first_step_with_edges_of_the_other_rule_is_used_as_it_is(self) -> None:
        before = self.first()
        self.folder_game.add("one", ROCK, texture_file("diffuse", colour_rgba(1, 16, 16)), tiles=False)
        asked = len(self.runner.asked)
        made = self.make(variant=TWO)
        self.assertEqual((made["recipe"], made["tiles"]), ("pbrify@64+seedvr2", False))
        self.assertEqual(self.runner.tiling[asked:], [False, False])
        # Negative: the first step is not made again, in place or as a revision.
        self.assertEqual(self.models()[asked:], ["seedvr2", "fast"])
        self.assertEqual(self.held(self.FIRST), before)
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify", "pbrify@64+seedvr2"])

    def test_a_stale_first_step_refuses_the_chain_and_leaves_nothing(self) -> None:
        before = self.first()
        self.add(size=16, seed=2)
        asked = len(self.runner.asked)
        with self.assertRaisesRegex(RequestError, "pbrify@64 is stale: the original changed since it was made"):
            self.make(variant=TWO)
        # Negative: no job, no request, no folder of the chain, no revision; the kept one as it was.
        self.assertEqual(len(self.runner.asked), asked)
        self.assertIsNone(self.read(TWO))
        self.assertFalse(self.folder(TWO).exists())
        self.assertEqual(self.held(self.FIRST), before)
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify"])

    def test_a_first_step_without_planes_and_without_the_file_of_its_size_refuses_the_chain(self) -> None:
        self.add(size=16)
        self.make(variant=self.FIRST)
        self.make(variant="pbrify@32")  # its half, asked for: the only file the entry is left with
        entry = self.entry(self.FIRST)
        self.rewrite(self.FIRST, planes={}, files={"32": entry["files"]["32"]})
        asked = len(self.runner.asked)
        with self.assertRaisesRegex(RequestError, "pbrify@64 is not kept"):
            self.make(variant=TWO)
        self.assertEqual(len(self.runner.asked), asked)
        self.assertIsNone(self.read(TWO))
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify"])

    def test_a_file_that_is_not_the_one_its_entry_names_fails_the_chain(self) -> None:
        self.add(size=16)
        self.make(variant=self.FIRST)
        self.rewrite(self.FIRST, planes={})
        path = self.game().variant_file(ORIGIN, "pbrify", 64)
        data = path.read_bytes()
        path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))  # one bit of its last byte
        asked = len(self.runner.asked)
        with self.assertRaisesRegex(RequestError, "is not the file its entry names"):
            self.make(variant=TWO)
        # Negative: nothing was upscaled from it, and no variant came of it.
        self.assertEqual(len(self.runner.asked), asked)
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify"])


class OneSizeTest(KeptCase):
    """R-HD-123: a request keeps the size it asks for and no other. A size asked for later is added with no job
    (R-HD-6) and changes no kept file (R-HD-158)."""

    def files(self, variant: str = UP) -> list[str]:
        return sorted(path.name for path in self.folder(variant).glob("*.dds"))

    def held(self, variant: str = UP) -> dict[str, bytes]:
        """The variant's files and its entry. Not the log: a request of the same recipe writes to it."""
        return {name: data for name, data in super().held(variant).items() if name.endswith((".dds", ENTRY))}

    def listed(self) -> list[str]:
        """The variants of the texture, as every reader lists them: one per size its entries hold."""
        found = self.dataset()
        made = found.made(found.texture(ROCK))
        return [variants.variant_id(name, size) for name, one in sorted(made.items()) for size in one.sizes()]

    def level(self, variant: str, index: int = 0) -> bytes:
        name, size = variants.split(variant)
        return dds.parse(self.game().variant_file(ORIGIN, name, size).read_bytes()).level_bytes(index)

    def test_a_request_of_the_half_keeps_the_half_and_no_other_size(self) -> None:
        self.add()
        made = self.make(variant=HALF)
        self.assertEqual((sorted(made["files"]), made["size"]), (["128"], [256, 256]))
        texture = dds.parse(self.game().variant_file(ORIGIN, "pbrify", 128).read_bytes())
        self.assertEqual((texture.width, texture.height), (128, 128))
        # Negative: no file of its own size, and no variant of it for a reader.
        self.assertEqual(self.files(), ["128.dds"])
        self.assertEqual(self.listed(), [HALF])

    def test_a_request_of_the_own_size_keeps_it_and_no_half(self) -> None:
        self.add()
        made = self.make()
        self.assertEqual(sorted(made["files"]), ["256"])
        self.assertEqual(self.files(), ["256.dds"])
        self.assertEqual(self.listed(), [UP])

    def test_a_larger_size_asked_for_later_is_added_with_no_job_and_changes_no_kept_file(self) -> None:
        self.add()
        self.make(variant=HALF)
        kept = self.rewrite(accepted=self.MARK)
        before = self.held()
        asked = len(self.runner.asked)
        made = self.make()
        self.assertEqual(sorted(made["files"]), ["128", "256"])
        self.assertEqual(self.listed(), [HALF, UP])
        # The two files are one mip chain: the half is the own size without its largest level.
        self.assertEqual(self.level(UP, 1), self.level(HALF))
        # Negative: no job, no revision, no request left; the kept file, its hash, the mark and every other key as they were.
        self.assertEqual(len(self.runner.asked), asked)
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify"])
        self.assertIsNone(self.read())
        self.assertFalse(self.note().exists())
        self.assertEqual(self.held()["128.dds"], before["128.dds"])
        self.assertEqual({**made, "files": kept["files"]}, kept)
        self.assertEqual(made["files"]["128"], kept["files"]["128"])
        # Asked for again, either size: nothing is written.
        now = self.held()
        self.make()
        self.make(variant=HALF)
        self.assertEqual(self.held(), now)
        self.assertEqual(len(self.runner.asked), asked)

    def test_a_smaller_size_asked_for_later_is_added_with_no_job(self) -> None:
        self.add()
        self.make()
        before = self.held()
        asked = len(self.runner.asked)
        made = self.make(variant=HALF)
        self.assertEqual(sorted(made["files"]), ["128", "256"])
        self.assertEqual(self.level(HALF), self.level(UP, 1))
        # Negative: no job, and the own size is the same byte for byte.
        self.assertEqual(len(self.runner.asked), asked)
        self.assertEqual(self.held()["256.dds"], before["256.dds"])

    def test_a_recipe_kept_without_planes_gives_a_smaller_size_from_its_larger_file(self) -> None:
        self.add()
        self.make()
        self.rewrite(planes={}, accepted=self.MARK)
        before = self.held()
        asked = len(self.runner.asked)
        made = self.make(variant=HALF)
        self.assertEqual(sorted(made["files"]), ["128", "256"])
        self.assertEqual(self.level(HALF), self.level(UP, 1))
        small = dds.parse(self.game().variant_file(ORIGIN, "pbrify", 128).read_bytes())
        large = dds.parse(before["256.dds"])
        self.assertEqual((small.width, len(small.levels), small.trailer), (128, len(large.levels) - 1, large.trailer))
        # Negative: no job; the larger file and the mark as they were.
        self.assertEqual(len(self.runner.asked), asked)
        self.assertEqual(self.held()["256.dds"], before["256.dds"])
        self.assertEqual(made[results.ACCEPTED], self.MARK)

    def test_a_recipe_kept_without_planes_cannot_give_a_larger_size_and_is_refused(self) -> None:
        self.add()
        self.make(variant=HALF)
        self.rewrite(planes={})
        before = self.held()
        asked = len(self.runner.asked)
        with self.assertRaisesRegex(RequestError, "pbrify@256.*holds no planes"):
            self.make()
        # Negative: a refusal leaves nothing: no job, no request, no file, no revision.
        self.assertEqual(len(self.runner.asked), asked)
        self.assertEqual(self.held(), before)
        self.assertIsNone(self.read())
        self.assertEqual(self.game().recipes(ORIGIN), ["pbrify"])

    def test_a_larger_file_that_is_not_the_one_its_entry_names_gives_no_size(self) -> None:
        self.add()
        self.make()
        self.rewrite(planes={})
        path = self.game().variant_file(ORIGIN, "pbrify", 256)
        data = path.read_bytes()
        path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))  # one bit of its last byte
        with self.assertRaisesRegex(RequestError, "is not the file its entry names"):
            self.make(variant=HALF)
        self.assertEqual(self.files(), ["256.dds"])
        self.assertEqual(sorted(self.entry()["files"]), ["256"])

    def test_a_recipe_of_another_encoder_is_refused_a_new_size(self) -> None:
        self.add()
        self.make(variant=HALF)
        self.rewrite(encoder=encode.ENCODER_VERSION + 1)
        before = self.held()
        with self.assertRaisesRegex(RequestError, f"encoder {encode.ENCODER_VERSION + 1}"):
            self.make()
        # Negative: nothing came of it.
        self.assertEqual(self.held(), before)
        self.assertIsNone(self.read())

    def test_each_step_of_a_longer_recipe_is_kept_at_the_size_its_id_names(self) -> None:
        self.add(size=16)
        self.make(variant=TWO)
        self.assertEqual(self.files("pbrify@64"), ["64.dds"])
        self.assertEqual(self.files(TWO), ["256.dds"])
        # Negative: no half of either step, for a reader too.
        self.assertEqual(self.listed(), ["pbrify@64", TWO])

    def test_a_revision_is_kept_at_the_size_asked_for(self) -> None:
        self.add()
        self.make()
        before = self.held()
        self.add(seed=2)
        made = self.make(variant=HALF)
        self.assertEqual((made["recipe"], sorted(made["files"])), ("pbrify~2", ["128"]))
        self.assertEqual(self.files("pbrify~2@128"), ["128.dds"])
        # Negative: the stale one gets no size and no byte.
        self.assertEqual(self.held(), before)
