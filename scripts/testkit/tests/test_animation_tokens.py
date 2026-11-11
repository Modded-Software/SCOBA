from __future__ import annotations

import unittest

from animation_tokens import (
    invalid_animation_tokens,
    normalized_animation_name,
    validate_animation_name,
)


class AnimationTokenTests(unittest.TestCase):
    def test_valid_single_token(self):
        self.assertEqual(validate_animation_name("Stand"), "Stand")

    def test_valid_composite_name(self):
        self.assertEqual(validate_animation_name("Stand Work"), "Stand Work")

    def test_valid_actor_reference(self):
        self.assertEqual(normalized_animation_name("Stand,Work"), "Stand Work")

    def test_valid_numbered_name(self):
        self.assertEqual(validate_animation_name("Attack 01"), "Attack 01")

    def test_invalid_custom_names(self):
        for name in ("LoIdle", "AimUp", "WalkX"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_animation_name(name)

    def test_invalid_token_report(self):
        self.assertEqual(invalid_animation_tokens("Stand,LoIdle"), ["LoIdle"])

    def test_empty_name(self):
        with self.assertRaises(ValueError):
            validate_animation_name("")


if __name__ == "__main__":
    unittest.main()