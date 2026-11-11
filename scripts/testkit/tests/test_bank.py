from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from testkit.bank import find_latest_bank, read_bank


XML = """<?xml version="1.0" encoding="UTF-8"?>
<Bank version="1">
  <Section name="meta">
    <Key name="done"><Value int="1"/></Key>
    <Key name="profile"><Value string="aim"/></Key>
    <Key name="ready"><Value flag="1"/></Key>
  </Section>
</Bank>
"""


class BankTests(unittest.TestCase):
    def test_read_types(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "SCOBAAIMTEST.SC2Bank"
            path.write_text(XML)
            data = read_bank(path)
            self.assertEqual(data["meta"]["done"], 1)
            self.assertEqual(data["meta"]["profile"], "aim")
            self.assertTrue(data["meta"]["ready"])

    def test_find_latest(self):
        with tempfile.TemporaryDirectory() as tmp:
            docs = Path(tmp)
            banks = docs / "Banks"
            banks.mkdir()
            first = banks / "SCOBAAIMTEST.SC2Bank"
            second = banks / "Other.SC2Bank"
            first.write_text(XML)
            second.write_text(XML)
            found = find_latest_bank(docs, "SCOBAAIMTEST", 0)
            self.assertEqual(found, first)


if __name__ == "__main__":
    unittest.main()