"""scripts/setup/deps.sh: dependency checks and the pinned stormex and upscale-on-arc steps."""

from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from project_root import project_root

SCRIPT = project_root() / "scripts" / "setup" / "deps.sh"
STORMEX_COMMIT = "1e931794583869bd8f4de9c18a3292a6715034ed"
# The stormex dependencies as deps.sh pins them: (path, url, tag, commit).
DEPS = [
    tuple(entry.split())
    for entry in re.findall(r'^\s+"(\S+ \S+ \S+ [0-9a-f]{40})"$', SCRIPT.read_text(encoding="utf-8"), re.M)
]
# The only system commands the script may use besides the stubs.
SYSTEM_COMMANDS = (
    "bash", "dirname", "mkdir", "install", "nproc", "cat", "chmod", "rm", "basename", "sha256sum", "cut",
)


class DepsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root / "SC2"
        self.home = root / "home"
        self.stubs = root / "stubs"
        self.system = root / "system"
        self.calls = root / "calls.log"
        for directory in (self.root, self.home, self.stubs, self.system):
            directory.mkdir()
        self.calls.touch()
        for name in SYSTEM_COMMANDS:
            found = shutil.which(name)
            self.assertIsNotNone(found, name)
            (self.system / name).symlink_to(found)
        self.stormex = self.root / "tools" / "stormex"
        self.src = self.root / ".venv/src/stormex"
        self.patches = self.root / "scripts/setup/patches/stormex"
        # The build PATH (STORMEX_PATH): the stubs, but not the ones on PATH first.
        self.toolchain = root / "toolchain"
        self.toolchain.mkdir()
        self.sc2 = self.home / "Games/battlenet-prefix/pfx/drive_c/Program Files (x86)/StarCraft II"
        self.proton = self.home / ".var/app/com.valvesoftware.Steam/data/Steam/compatibilitytools.d/GE-Proton10-1"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def stub(self, name: str, body: str = "exit 0\n") -> None:
        """A command that logs its arguments to calls.log, then runs `body`."""
        path = self.stubs / name
        path.write_text(f'#!/bin/sh\necho "{name} $*" >> "{self.calls}"\n{body}', encoding="utf-8")
        path.chmod(0o755)

    def executable(self, path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def pins(self) -> str:
        """The pins file deps.sh writes for the current pins and patches."""
        lines = [f"stormex v2.2.0 {STORMEX_COMMIT}"] + [" ".join(dep) for dep in DEPS]
        for patch in sorted(self.patches.glob("*.patch")):
            lines.append(f"patch {patch.name} {hashlib.sha256(patch.read_bytes()).hexdigest()}")
        return "\n".join(lines) + "\n"

    def pinned_stormex(self) -> None:
        self.executable(self.stormex, 'echo "stormex v2.2.0 | CascLib v3.0"\n')
        self.stormex.with_name("stormex.pins").write_text(self.pins(), encoding="utf-8")

    def full_machine(self) -> None:
        for name in ("git", "uv", "node", "npm", "cmake"):
            self.stub(name)
        (self.toolchain / "c++").symlink_to(shutil.which("true"))
        self.stub("pkg-config", 'case "$1" in --modversion) echo 2.9.9 ;; esac\nexit 0\n')
        self.pinned_stormex()
        self.sc2.mkdir(parents=True)
        (self.sc2 / "StarCraft II.exe").touch()
        self.executable(self.proton / "proton", "exit 0\n")

    def run_deps(self, command: str) -> subprocess.CompletedProcess[str]:
        env = {
            "HOME": str(self.home),
            "PATH": f"{self.stubs}:{self.system}",
            "STORMEX_PATH": f"{self.toolchain}:{self.system}",
            "SC2_PROJECT_ROOT": str(self.root),
        }
        return subprocess.run(
            [str(self.system / "bash"), str(SCRIPT), command], env=env, text=True, capture_output=True
        )

    def calls_made(self) -> list[str]:
        return self.calls.read_text(encoding="utf-8").splitlines()

    # ------------------------------------------------------------ check

    def test_check_passes_when_every_required_dependency_is_present(self) -> None:
        self.full_machine()
        result = self.run_deps("check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("git", "uv", "node", "npm", "cmake", "c++", "fuse", "stormex", "starcraft2", "ge-proton"):
            self.assertRegex(result.stdout, rf"(?m)^OK +{re.escape(name)} ", name)
        self.assertNotIn("MISSING", result.stdout)

    def test_optional_dependencies_do_not_fail_the_check(self) -> None:
        self.full_machine()
        result = self.run_deps("check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"(?m)^OPTIONAL +lsfg-vk ")
        self.assertRegex(result.stdout, r"(?m)^OPTIONAL +upscale-on-arc ")

    def test_check_fails_and_names_each_missing_dependency(self) -> None:
        self.full_machine()
        (self.stubs / "uv").unlink()
        (self.sc2 / "StarCraft II.exe").unlink()
        result = self.run_deps("check")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"(?m)^MISSING +uv ")
        self.assertRegex(result.stdout, r"(?m)^MISSING +starcraft2 ")
        self.assertIn("2 required dependencies missing", result.stdout)

    def test_stormex_of_another_version_is_missing(self) -> None:
        self.full_machine()
        self.executable(self.stormex, 'echo "stormex v2.1.0 | CascLib v3.0"\n')
        result = self.run_deps("check")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"(?m)^MISSING +stormex ")

    def test_stormex_without_a_pins_file_is_missing(self) -> None:
        # The Nov 7 build reports the same version but came from other commits.
        self.full_machine()
        self.stormex.with_name("stormex.pins").unlink()
        result = self.run_deps("check")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"(?m)^MISSING +stormex .*not built from the current pins")

    def test_c_compiler_is_looked_up_on_the_build_path(self) -> None:
        self.full_machine()
        (self.toolchain / "c++").unlink()
        self.stub("c++")  # on PATH, but not on STORMEX_PATH: it must not count
        result = self.run_deps("check")
        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stdout, r"(?m)^MISSING +c\+\+ ")

    # ------------------------------------------------------------ stormex

    def test_the_pins_cover_each_stormex_dependency(self) -> None:
        self.assertEqual([dep[0] for dep in DEPS], ["CascLib", "cxxopts", "plog"])

    def test_pinned_stormex_is_not_rebuilt(self) -> None:
        self.full_machine()
        result = self.run_deps("stormex")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("already installed", result.stdout)
        self.assertEqual(self.calls_made(), [])  # negative: no clone, no cmake

    def test_source_at_another_commit_is_refused_and_nothing_is_built(self) -> None:
        self.full_machine()
        self.stormex.unlink()
        (self.src / ".git").mkdir(parents=True)
        self.stub("git", 'echo 0000000000000000000000000000000000000000\n')
        result = self.run_deps("stormex")
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"not v2.2.0 ({STORMEX_COMMIT})", result.stderr)
        self.assertFalse(any(call.startswith("cmake") for call in self.calls_made()))
        self.assertFalse(self.stormex.exists())

    def stormex_source(self, heads: dict[str, str] | None = None, applied: bool = False, fits: bool = True) -> None:
        """A stormex checkout at the pinned commit. Each dependency clone reports
        its pinned commit, or the one in `heads`. `applied` and `fits` decide how
        `git apply` answers for every patch."""
        (self.src / ".git").mkdir(parents=True)
        cases = "".join(
            f"  *'{self.src}/{path} rev-parse HEAD'*) echo {(heads or {}).get(path, commit)} ;;\n"
            for path, _url, _tag, commit in DEPS
        )
        self.stub(
            "git",
            'case "$*" in\n'
            + cases
            + f"  *'apply --check --reverse'*) exit {0 if applied else 1} ;;\n"
            + f"  *' apply '*) exit {0 if fits else 1} ;;\n"
            + f"  *'rev-parse HEAD'*) echo {STORMEX_COMMIT} ;;\n"
            + "esac\n",
        )
        built = self.src / "build/bin/stormex"
        self.stub(
            "cmake",
            f'echo "cmake-path $PATH" >> "{self.calls}"\n'
            f'case "$1" in --build) mkdir -p "{built.parent}"; '
            f"printf '#!/bin/sh\\necho \"stormex v2.2.0 | CascLib v3.0\"\\n' > \"{built}\"; "
            f'chmod 755 "{built}" ;; esac\n',
        )

    def add_patch(self, name: str = "0001-fix.patch") -> Path:
        self.patches.mkdir(parents=True, exist_ok=True)
        patch = self.patches / name
        patch.write_text("diff --git a/x b/x\n", encoding="utf-8")
        return patch

    def test_dependency_at_another_commit_is_refused_and_nothing_is_built(self) -> None:
        self.full_machine()
        self.stormex.unlink()
        self.stormex_source(heads={"CascLib": "1" * 40})
        result = self.run_deps("stormex")
        self.assertEqual(result.returncode, 1)
        self.assertIn(f"CascLib is at {'1' * 40}, not 3.0 ({DEPS[0][3]})", result.stderr)
        self.assertFalse(any(call.startswith("cmake") for call in self.calls_made()))

    def test_source_at_the_pins_is_patched_built_and_installed(self) -> None:
        self.full_machine()
        self.stormex.unlink()
        patch = self.add_patch()
        self.stormex_source()
        result = self.run_deps("stormex")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(self.stormex.is_file())
        self.assertIn("installed stormex v2.2.0", result.stdout)
        self.assertEqual(self.stormex.with_name("stormex.pins").read_text(encoding="utf-8"), self.pins())
        calls = self.calls_made()
        for path, url, tag, _commit in DEPS:
            self.assertIn(
                f"git -c advice.detachedHead=false clone --depth 1 --branch {tag} {url} {self.src}/{path}", calls
            )
        self.assertIn(f"git -C {self.src} apply {patch}", calls)
        self.assertLess(calls.index(f"git -C {self.src} apply {patch}"), next(i for i, c in enumerate(calls) if c.startswith("cmake ")))
        self.assertIn(f"cmake-path {self.toolchain}:{self.system}", calls)  # the build PATH, not PATH
        self.assertFalse(any(" submodule " in call for call in calls))  # negative: no git submodule

    def test_an_applied_patch_is_not_applied_again(self) -> None:
        self.full_machine()
        self.stormex.unlink()
        patch = self.add_patch()
        self.stormex_source(applied=True)
        result = self.run_deps("stormex")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("patch already applied: 0001-fix.patch", result.stdout)
        self.assertNotIn(f"git -C {self.src} apply {patch}", self.calls_made())

    def test_a_patch_that_does_not_fit_stops_the_build(self) -> None:
        self.full_machine()
        self.stormex.unlink()
        self.add_patch()
        self.stormex_source(fits=False)
        result = self.run_deps("stormex")
        self.assertEqual(result.returncode, 1)
        self.assertIn("patch 0001-fix.patch does not apply", result.stderr)
        self.assertFalse(any(call.startswith("cmake") for call in self.calls_made()))
        self.assertFalse(self.stormex.exists())

    def test_a_changed_patch_rebuilds_a_stormex_of_the_right_version(self) -> None:
        self.full_machine()  # installed with the pins of no patches
        self.add_patch()
        self.stormex_source()
        result = self.run_deps("stormex")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("already installed", result.stdout)
        self.assertTrue(any(call.startswith("cmake --build") for call in self.calls_made()))
        self.assertEqual(self.stormex.with_name("stormex.pins").read_text(encoding="utf-8"), self.pins())

    # ------------------------------------------------------------ upscale-on-arc

    def test_checkout_without_the_pinned_commit_is_refused(self) -> None:
        self.full_machine()
        (self.root.parent / "upscale-on-arc/.git").mkdir(parents=True)
        self.stub("git", 'case "$*" in *merge-base*) exit 1 ;; esac\n')
        self.stub("make")
        result = self.run_deps("upscale")
        self.assertEqual(result.returncode, 1)
        self.assertIn("does not contain the pinned commit b35fa078", result.stderr)
        self.assertFalse(any(call.startswith("make") for call in self.calls_made()))

    def test_checkout_with_the_pinned_commit_is_installed(self) -> None:
        self.full_machine()
        checkout = self.root.parent / "upscale-on-arc"
        (checkout / ".git").mkdir(parents=True)
        self.stub("make")
        result = self.run_deps("upscale")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"make -C {checkout} install", self.calls_made())
        self.assertFalse(any(" clone " in call for call in self.calls_made()))  # negative: no clone over it

    def test_unknown_subcommand_is_refused(self) -> None:
        result = self.run_deps("nope")
        self.assertEqual(result.returncode, 1)
        self.assertIn("usage: deps.sh", result.stderr)


if __name__ == "__main__":
    unittest.main()
