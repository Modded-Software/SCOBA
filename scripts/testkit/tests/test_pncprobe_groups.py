import re
import unittest

from project_root import project_root
from testkit.profiles.pncprobe.check import GROUP_REPORTS
from testkit.profiles.pncprobe.spec import GALAXY, GALAXY_FILES, GROUPS

ROOT = project_root()


class PncProbeGroupsTest(unittest.TestCase):
    def test_every_checked_group_has_a_report(self) -> None:
        # picklog runs for manual play and is never checked.
        self.assertEqual(set(GROUP_REPORTS), (set(GROUPS) - {"picklog"}) | {"all"})

    def test_galaxy_dispatch_names_the_same_groups(self) -> None:
        text = (GALAXY / "pncprobe.galaxy").read_text(encoding="utf-8")
        dispatched = set(re.findall(r'gv_dbgGroup == "(\w+)"', text))
        self.assertEqual(dispatched, set(GROUPS))

    def test_galaxy_sources_exist_and_dispatch_is_last(self) -> None:
        for name in GALAXY_FILES:
            self.assertTrue((GALAXY / f"{name}.galaxy").is_file(), name)
        self.assertEqual(GALAXY_FILES[-1], "pncprobe")

    def test_removed_probes_stay_removed(self) -> None:
        # Negative case: the unused probes deleted in the refactor are not back.
        text = "".join((GALAXY / f"{name}.galaxy").read_text(encoding="utf-8") for name in GALAXY_FILES)
        for name in ("gf_ProbeEnd", "gf_ProbeMoveFire", "gf_ProbeToSingle", "gf_ProbeLateEnd", "gf_ProbeButton", "gf_ProbeTail", "gf_ProbeFirstShot"):
            self.assertNotIn(name, text)


if __name__ == "__main__":
    unittest.main()
