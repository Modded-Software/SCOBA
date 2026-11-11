from __future__ import annotations

import unittest

from testkit.profiles.registry import PROFILE_BANKS, PROFILE_OUTPUTS, profile_module


class ProfileTests(unittest.TestCase):
    def test_outputs_are_isolated(self):
        self.assertNotEqual(PROFILE_OUTPUTS["combat"], PROFILE_OUTPUTS["aim"])
        self.assertNotEqual(PROFILE_BANKS["combat"], PROFILE_BANKS["aim"])

    def test_map_specs_match_registry(self):
        for name in ("combat", "aim"):
            spec = profile_module(name).map_spec()
            self.assertEqual(spec.profile, name)
            self.assertEqual(spec.output, PROFILE_OUTPUTS[name])
            self.assertEqual(spec.bank_names, PROFILE_BANKS[name])

    def test_unknown_profile(self):
        with self.assertRaises(SystemExit):
            profile_module("missing")


if __name__ == "__main__":
    unittest.main()