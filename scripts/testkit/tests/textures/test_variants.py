"""Variant ids, recipes, models per plane, sizes, refusals (R-HD-120 to 124, O-HD-10)."""

from __future__ import annotations

import unittest

from hdtex.core import variants
from hdtex.core.interfaces import Plane
from hdtex.core.variants import MODELS, VariantError

COLOUR = Plane("color", colour=True)
DATA = Plane("alpha")


class IdTest(unittest.TestCase):
    def test_a_variant_is_its_recipe_and_its_size(self) -> None:
        self.assertEqual(variants.split("pbrify@2048"), ("pbrify", 2048))
        self.assertEqual(
            variants.split("pbrify@4096+seedvr2@4096"), ("pbrify@4096+seedvr2", 4096)
        )
        self.assertEqual(variants.split(variants.ORIGINAL), ("", 0))
        self.assertEqual(
            variants.variant_id("pbrify@4096+seedvr2", 2048), "pbrify@4096+seedvr2@2048"
        )

    def test_what_is_no_variant_is_refused(self) -> None:
        for text in (
            "pbrify",
            "",
            "pbrify@",
            "pbrify@x",
            "sharpen@2048",
            "pbrify+fast@2048",
            None,
        ):
            with self.assertRaises(VariantError, msg=repr(text)):
                variants.split(text)

    def test_a_recipe_has_a_size_on_every_step_but_the_last(self) -> None:
        steps = variants.parse_recipe("pbrify@2048+seedvr2")
        self.assertEqual(
            [(step.model.id, step.size) for step in steps],
            [("pbrify", 2048), ("seedvr2", None)],
        )
        for text in (
            "",
            "pbrify@2048",
            "pbrify+seedvr2",
            "sharpen",
            "PBRify",
            "pbrify@0+fast",
            "+fast",
            None,
        ):
            with self.assertRaises(VariantError, msg=repr(text)):
                variants.parse_recipe(text)

    def test_a_request_joins_its_input_and_its_model(self) -> None:
        self.assertEqual(
            variants.join(variants.ORIGINAL, "pbrify", 2048), "pbrify@2048"
        )
        self.assertEqual(
            variants.join("pbrify@2048", "seedvr2", 4096), "pbrify@2048+seedvr2@4096"
        )
        self.assertEqual(variants.input_of("pbrify@2048+seedvr2@4096"), "pbrify@2048")
        self.assertEqual(variants.input_of("pbrify@2048"), variants.ORIGINAL)
        with self.assertRaises(VariantError):
            variants.join(variants.ORIGINAL, "sharpen", 2048)
        with self.assertRaises(VariantError):
            variants.join("pbrify", "fast", 2048)

    def test_prefixes_are_the_recipes_after_each_step(self) -> None:
        self.assertEqual(
            variants.prefixes("pbrify@2048+seedvr2"), ("pbrify", "pbrify@2048+seedvr2")
        )
        self.assertEqual(variants.prefixes("fast"), ("fast",))

    def test_a_title_names_each_model_and_the_size(self) -> None:
        self.assertEqual(
            variants.title("pbrify@2048+seedvr2@4096"), "PBRify, then SeedVR2 at 4096"
        )
        self.assertEqual(variants.title(variants.ORIGINAL), "Original")


class RevisionTest(unittest.TestCase):
    """A variant made again stands beside the first, with a revision on its last step (R-HD-158)."""

    def test_a_step_may_carry_a_revision_and_keeps_its_model(self) -> None:
        self.assertEqual(variants.split("pbrify~2@512"), ("pbrify~2", 512))
        self.assertEqual(variants.variant_id("pbrify~2", 512), "pbrify~2@512")
        self.assertEqual(
            variants.split("pbrify~2@256+seedvr2~3@1024"), ("pbrify~2@256+seedvr2~3", 1024)
        )
        steps = variants.parse_recipe("pbrify~2@256+seedvr2")
        self.assertEqual(
            [(step.model.id, step.revision, step.size) for step in steps],
            [("pbrify", 2, 256), ("seedvr2", 1, None)],
        )
        self.assertEqual(
            variants.prefixes("pbrify~2@256+seedvr2"), ("pbrify~2", "pbrify~2@256+seedvr2")
        )
        self.assertEqual(variants.input_of("pbrify~2@256+seedvr2@1024"), "pbrify~2@256")
        self.assertEqual(variants.join("pbrify~2@256", "seedvr2", 1024), "pbrify~2@256+seedvr2@1024")
        self.assertEqual(variants.title("pbrify~2@512"), "PBRify #2 at 512")
        self.assertEqual(variants.title("pbrify~2@256+seedvr2@1024"), "PBRify #2, then SeedVR2 at 1024")
        # The sizes and refusals of a revision are those of its model.
        self.assertEqual(variants.refusal("pbrify~2", 64, True), variants.refusal("pbrify", 64, True))
        self.assertEqual(variants.size_refusal("pbrify~2", 256, 64), "")
        self.assertIn("no model for it", variants.model_refusal("pbrify~2", False))

    def test_the_revision_of_a_recipe_is_that_of_its_last_step(self) -> None:
        self.assertEqual(variants.revision_of("pbrify"), ("pbrify", 1))
        self.assertEqual(variants.revision_of("pbrify~4"), ("pbrify", 4))
        self.assertEqual(variants.revision_of("pbrify~2@256+seedvr2"), ("pbrify~2@256+seedvr2", 1))
        self.assertEqual(variants.revision_of("pbrify~2@256+seedvr2~3"), ("pbrify~2@256+seedvr2", 3))
        self.assertEqual(variants.revised("pbrify", 2), "pbrify~2")
        self.assertEqual(variants.revised("pbrify~2", 3), "pbrify~3")
        self.assertEqual(variants.revised("pbrify~2@256+seedvr2", 2), "pbrify~2@256+seedvr2~2")
        # The first make has no revision: one variant has one id.
        self.assertEqual(variants.revised("pbrify~2", 1), "pbrify")
        with self.assertRaises(VariantError):
            variants.revised("pbrify", 0)

    def test_an_edit_step_may_carry_a_revision_too(self) -> None:
        steps = variants.parse_recipe("pbrify@256+edit3fa9c1d2aa10~2")
        self.assertEqual((steps[-1].edit, steps[-1].revision), (True, 2))
        self.assertEqual(variants.split("edit3fa9c1d2aa10~2@64"), ("edit3fa9c1d2aa10~2", 64))

    def test_a_revision_below_two_or_no_plain_number_names_nothing(self) -> None:
        for text in (
            "pbrify~1@512",
            "pbrify~0@512",
            "pbrify~02@512",
            "pbrify~@512",
            "pbrify~x@512",
            "pbrify~-2@512",
            "~2@512",
            "pbrify~2~3@512",
            "pbrify@512~2",
            "pbrify~1@256+seedvr2@1024",
        ):
            with self.assertRaises(VariantError, msg=repr(text)):
                variants.split(text)


class ModelTest(unittest.TestCase):
    def test_data_planes_get_fast_from_every_model(self) -> None:
        for model in MODELS.values():
            self.assertEqual(model.model_for(DATA), "fast", msg=model.id)

    def test_colour_planes_get_the_models_own(self) -> None:
        self.assertEqual(
            {model.id: model.model_for(COLOUR) for model in MODELS.values()},
            {"pbrify": "pbrify", "fast": "fast", "seedvr2": "seedvr2"},
        )
        self.assertEqual(
            [model.id for model in MODELS.values() if model.invents], ["seedvr2"]
        )


class SizeTest(unittest.TestCase):
    def test_the_own_size_is_four_times_the_input_at_most_4096(self) -> None:
        self.assertEqual(variants.own_size(variants.parse_recipe("pbrify"), 256), 1024)
        self.assertEqual(variants.own_size(variants.parse_recipe("pbrify"), 1024), 4096)
        self.assertEqual(
            variants.own_size(variants.parse_recipe("seedvr2"), 4096), 4096
        )
        self.assertEqual(
            variants.own_size(variants.parse_recipe("pbrify@1024+seedvr2"), 1024), 4096
        )
        self.assertEqual(
            variants.own_size(variants.parse_recipe("pbrify@1024+seedvr2"), 64), 1024
        )

    def test_a_variant_can_be_had_at_its_own_size_and_the_kept_levels_below(
        self,
    ) -> None:
        self.assertEqual(variants.size_refusal("pbrify", 4096, 1024), "")
        self.assertEqual(variants.size_refusal("pbrify", 1024, 1024), "")
        self.assertIn("not at 4096", variants.size_refusal("pbrify", 4096, 256))
        self.assertIn("not at 2048", variants.size_refusal("pbrify", 2048, 256))


class RefusalTest(unittest.TestCase):
    def test_a_model_that_adds_nothing_to_a_full_size_input_is_refused(self) -> None:
        self.assertIn("can add nothing", variants.refusal("pbrify", 4096, True))
        self.assertIn("can add nothing", variants.refusal("fast", 4096, True))
        self.assertIn(
            "can add nothing", variants.refusal("pbrify@4096+pbrify", 1024, True)
        )
        self.assertEqual(variants.refusal("seedvr2", 4096, True), "")

    def test_a_step_size_the_input_does_not_have_is_refused(self) -> None:
        self.assertIn(
            "not at 8192", variants.refusal("pbrify@8192+seedvr2", 1024, True)
        )
        self.assertIn("not at 2048", variants.refusal("pbrify@2048+seedvr2", 256, True))

    def test_a_texture_without_colour_takes_fast_only(self) -> None:
        self.assertIn("use fast", variants.refusal("pbrify", 1024, False))
        self.assertIn("use fast", variants.refusal("fast@4096+seedvr2", 1024, False))
        self.assertEqual(variants.refusal("fast", 1024, False), "")

    def test_recipes_that_add_something_are_not_refused(self) -> None:
        for recipe, longest in (
            ("fast", 1024),
            ("pbrify", 2048),
            ("pbrify@1024+pbrify", 1024),
            ("pbrify@4096+seedvr2", 1024),
            ("fast@4096+seedvr2", 1024),
            ("pbrify@4096+seedvr2@4096+seedvr2", 1024),
        ):
            self.assertEqual(
                variants.refusal(recipe, longest, True),
                "",
                msg=f"{recipe} on {longest}",
            )

    def test_the_model_check_holds_whatever_the_size(self) -> None:
        self.assertEqual(variants.model_refusal("pbrify", True), "")
        self.assertIn("use fast", variants.model_refusal("pbrify", False))
        # Negative: a size is never guessed; a full check needs a read side.
        for longest in (0, -1):
            with self.assertRaises(variants.VariantError, msg=str(longest)):
                variants.refusal("pbrify", longest, True)


EDIT = "edit3fa9c1d2aa10"
DIGEST = "3fa9c1d2aa10" + "0" * 52


class EditStepTest(unittest.TestCase):
    """A person's edit as a step of a variant id (SPEC-PHOTOCRAFT 10, R-PC-54)."""

    def test_an_edit_joins_its_input_with_twelve_digits_of_its_hash_at_the_inputs_size(self) -> None:
        self.assertEqual(variants.edited(variants.ORIGINAL, DIGEST, 512), f"{EDIT}@512")
        self.assertEqual(variants.edited("pbrify@2048", DIGEST, 2048), f"pbrify@2048+{EDIT}@2048")
        self.assertEqual(variants.split(f"pbrify@2048+{EDIT}@2048"), (f"pbrify@2048+{EDIT}", 2048))
        self.assertEqual(variants.input_of(f"pbrify@2048+{EDIT}@2048"), "pbrify@2048")
        self.assertEqual(variants.input_of(f"{EDIT}@512"), variants.ORIGINAL)
        self.assertEqual(variants.title(f"pbrify@2048+{EDIT}@2048"), "PBRify, then Edit at 2048")
        self.assertEqual(variants.prefixes(f"{EDIT}@512+fast"), (EDIT, f"{EDIT}@512+fast"))
        [step] = variants.parse_recipe(EDIT)
        self.assertEqual((step.edit, step.model.id), (True, EDIT))
        self.assertEqual([step.edit for step in variants.parse_recipe(f"pbrify@2048+{EDIT}@2048+fast")], [False, True, False])

    def test_what_is_no_edit_step_is_no_model_either(self) -> None:
        for name in ("edit", "edit3fa9c1d2aa1", "edit3fa9c1d2aa100", "edit3FA9C1D2AA10", "edit3fa9c1d2aa1g", "xedit3fa9c1d2aa10"):
            self.assertFalse(variants.is_edit(name), name)
            with self.assertRaises(VariantError, msg=name):
                variants.parse_recipe(name)
        self.assertNotIn(variants.EDIT, MODELS, "no request can name the edit as its model")

    def test_an_edit_keeps_the_size_of_its_input_and_has_that_one_size(self) -> None:
        self.assertEqual(variants.own_size(variants.parse_recipe(EDIT), 512), 512)
        self.assertEqual(variants.own_size(variants.parse_recipe(f"pbrify@2048+{EDIT}"), 1024), 2048)
        self.assertEqual(variants.own_size(variants.parse_recipe(f"{EDIT}@512+pbrify"), 512), 2048)
        self.assertEqual(variants.size_refusal(f"pbrify@2048+{EDIT}", 2048, 1024), "")
        # Negative: not at a level below, though its input's recipe is kept there.
        self.assertIn("not at 1024", variants.size_refusal(f"pbrify@2048+{EDIT}", 1024, 1024))
        self.assertIn("not at 2048", variants.size_refusal(f"pbrify@4096+{EDIT}", 2048, 1024))

    def test_a_request_may_build_on_an_edit_at_its_size_and_cannot_make_one(self) -> None:
        self.assertEqual(variants.refusal(f"{EDIT}@512+pbrify", 512, True), "")
        self.assertEqual(variants.refusal(f"pbrify@2048+{EDIT}@2048+seedvr2", 1024, True), "")
        self.assertIn("is kept at 512, not at 256", variants.refusal(f"{EDIT}@256+pbrify", 512, True))
        self.assertIn("is kept at 2048, not at 1024", variants.refusal(f"pbrify@2048+{EDIT}@1024+fast", 1024, True))
        self.assertIn("a request cannot", variants.refusal(EDIT, 512, True))
        self.assertIn("a request cannot", variants.refusal(f"pbrify@2048+{EDIT}", 1024, True))
        self.assertIn("can add nothing", variants.refusal(f"{EDIT}@4096+fast", 4096, True))

    def test_an_edit_step_is_no_model_a_texture_without_colour_must_avoid(self) -> None:
        self.assertEqual(variants.model_refusal(EDIT, False), "")
        self.assertEqual(variants.model_refusal(f"{EDIT}@512+fast", False), "")
        self.assertIn("use fast", variants.model_refusal(f"{EDIT}@512+pbrify", False))
