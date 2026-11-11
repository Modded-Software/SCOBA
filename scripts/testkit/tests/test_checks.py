from __future__ import annotations

import unittest

from testkit.checks import Checks


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.data = {
            "case": {
                "t0Auto": 0,
                "t0Stand": 1,
                "t0Flag": True,
                "t0HeroX": 10,
                "t0HeroY": 10,
                "t1HeroX": 14,
                "t1HeroY": 10,
                "t0EnemyHp": 500,
                "t1EnemyHp": 400,
                "t0Value": 5,
            }
        }

    def test_pass(self):
        checks = Checks(self.data)
        checks.eq("case", "t0", "Auto", 0)
        checks.true("case", "t0", "Flag")
        checks.displacement("case", "t0", "t1")
        checks.damage("case", "t0", "t1")
        self.assertEqual(checks.failures, 0)

    def test_missing_value_fails(self):
        checks = Checks(self.data)
        checks.eq("case", "t0", "Missing", 1)
        self.assertEqual(checks.failures, 1)

    def test_ranges(self):
        checks = Checks(self.data)
        checks.gt("case", "t0", "Value", 4)
        checks.lt("case", "t0", "Value", 6)
        checks.between("case", "t0", "Value", 4, 6)
        self.assertEqual(checks.failures, 0)

    def test_failed_compare(self):
        checks = Checks(self.data)
        checks.decrease("case", "t0", "t1", "Value")
        self.assertEqual(checks.failures, 1)


if __name__ == "__main__":
    unittest.main()