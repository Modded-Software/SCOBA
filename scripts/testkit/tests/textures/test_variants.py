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
