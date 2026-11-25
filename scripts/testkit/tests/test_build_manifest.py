"""The built map's BuildManifest.txt: one line per file, in byte order.

scripts/build.sh writes it. Its hash is the build's fingerprint, so it must not
depend on the order a disk lists a folder in.
"""

import hashlib
import unittest

import workpaths
from testkit.tests.built_map import needs_built

NAME = "BuildManifest.txt"


def _entries() -> list[tuple[str, str]]:
    text = (workpaths.path("SC2_BUILT_MAP") / NAME).read_text(encoding="utf-8")
    entries = []
    for line in text.splitlines():
        digest, sep, rel = line.partition("  ")
        entries.append((digest, rel if sep else ""))
    return entries


@needs_built(NAME)
class BuildManifestTest(unittest.TestCase):
    def test_lines_are_in_byte_order(self) -> None:
        names = [rel for _, rel in _entries()]
        self.assertEqual(names, sorted(names, key=lambda rel: rel.encode()))

    def test_every_file_is_listed_once_with_its_hash(self) -> None:
        built = workpaths.path("SC2_BUILT_MAP")
        entries = _entries()
        names = [rel for _, rel in entries]
        self.assertEqual(len(names), len(set(names)))
        on_disk = {
            path.relative_to(built).as_posix()
            for path in built.rglob("*")
            if path.is_file() and path.name != NAME
        }
        self.assertEqual(set(names), on_disk)
        for digest, rel in entries:
            got = hashlib.sha256((built / rel).read_bytes()).hexdigest()
            self.assertEqual(got, digest, rel)

    def test_the_manifest_does_not_list_itself(self) -> None:
        self.assertNotIn(NAME, [rel for _, rel in _entries()])


if __name__ == "__main__":
    unittest.main()
