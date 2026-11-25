"""scripts/setup/photocraft.sh through deps.sh: the PhotoCraft install steps (SPEC-PHOTOCRAFT section 5).

The tools of the build (git, rustup, cargo, curl, tar, trunk and the built
renderer) are stubs that log their calls and leave the files a real one
leaves. What is tested is the order of the steps, the pins record, what a
failed step leaves, and what the install folder holds.
"""

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
# The pins as deps.sh names them: PHOTOCRAFT_<name>="<value>".
PINS = dict(re.findall(r'^PHOTOCRAFT_(\w+)="([^"$]*)"$', SCRIPT.read_text(encoding="utf-8"), re.M))
LICENCES = ("LICENSE-APACHE", "LICENSE-MIT", "NOTICE", "ATTRIBUTION.md")
# The system commands the script and the stubs may use.
SYSTEM_COMMANDS = (
    "bash", "dirname", "mkdir", "install", "nproc", "cat", "chmod", "rm", "basename", "sha256sum", "cut",
    "mv", "cp", "stat", "env", "truncate",
)
# The renderer as the build leaves it: it writes each file it is asked for, and one picture per group.
RENDERER = """#!/bin/sh
previous=
for word in "$@"; do
  if [ "$previous" = "--out" ]; then : > "$word"; fi
  case "$word" in
    *'"dir":"'*) folder=${word#*\\"dir\\":\\"}; folder=${folder%%\\"*}; : > "$folder/plane_0000_b.png"; : > "$folder/plane_0001_a.png" ;;
  esac
  previous=$word
done
echo "photocraft-cli of the test"
"""


class PhotocraftDepsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.root = root / "SC2"
        self.stubs = root / "stubs"
        self.system = root / "system"
        self.calls = root / "calls.log"
        self.build = root / "work" / "build"
        self.home = self.build / "photocraft"
        self.src = self.build / "deps/photocraft"
        self.tree = self.build / "deps/photocraft-tree"
        self.tools = self.build / "deps/photocraft-tools"
        self.target = self.build / "deps/photocraft-target"
        self.logs = self.build / "deps/photocraft-logs"
        self.patches = self.root / "scripts/setup/patches/photocraft"
        for directory in (self.stubs, self.system, self.patches):
            directory.mkdir(parents=True)
        self.calls.touch()
        for name in SYSTEM_COMMANDS:
            found = shutil.which(name)
            self.assertIsNotNone(found, name)
            (self.system / name).symlink_to(found)
        # deps.sh sources its PhotoCraft steps from the repo root it is given.
        (self.root / "scripts/setup/photocraft.sh").symlink_to(SCRIPT.with_name("photocraft.sh"))
        self.renderer = root / "renderer.sh"
        self.renderer.write_text(RENDERER, encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def stub(self, path: Path, body: str = "exit 0\n") -> None:
        """A command that logs its name and arguments to calls.log, then runs `body`."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f'#!/bin/sh\necho "{path.name} $*" >> "{self.calls}"\n{body}', encoding="utf-8")
        path.chmod(0o755)

    def machine(self, *, archive_as_pinned: bool = True, patches_fit: bool = True, module_bytes: int = 2 * 1024 * 1024) -> None:
        """The build's tools as stubs. Each leaves what the next step reads."""
        licences = " ".join(LICENCES)
        self.stub(
            self.stubs / "git",
            'for last in "$@"; do :; done\n'
            'case "$*" in\n'
            '  *" clone "*) mkdir -p "$last/.git" "$last/apps/photocraft-web"\n'
            f'    for name in {licences}; do echo "$name of upstream" > "$last/$name"; done ;;\n'
            f'  *"rev-parse HEAD"*) echo {PINS["COMMIT"]} ;;\n'
            f'  *" apply "*) exit {0 if patches_fit else 1} ;;\n'
            "esac\n",
        )
        self.stub(self.stubs / "rustup")
        self.stub(self.stubs / "curl", ': > "$3"\n')
        self.stub(self.stubs / "tar")
        if archive_as_pinned:
            # The archive of the test is not Trunk's: its hash is answered as the pinned one. Not logged.
            path = self.stubs / "sha256sum"
            path.write_text(
                "#!/bin/sh\n"
                f'case "$1" in *.tar.gz) echo "{PINS["TRUNK_SHA256"]}  $1" ;; *) exec "{self.system}/sha256sum" "$@" ;; esac\n',
                encoding="utf-8",
            )
            path.chmod(0o755)
        self.stub(
            self.tools / "bin/trunk",
            "mkdir -p ../../dist/web\n"
            "echo '<script type=\"module\" src=\"./editor.js\"></script>' > ../../dist/web/index.html\n"
            "echo built > ../../dist/web/editor.js\n"
            f"truncate -s {module_bytes} ../../dist/web/editor_bg.wasm\n",
        )
        toolchain = self.tools / f'rustup/toolchains/{PINS["RUST"]}-{PINS["HOST"]}/bin'
        self.stub(
            toolchain / "cargo",
            'mkdir -p "$CARGO_TARGET_DIR/release"\n'
            f'cp "{self.renderer}" "$CARGO_TARGET_DIR/release/photocraft-cli"\n'
            'chmod 755 "$CARGO_TARGET_DIR/release/photocraft-cli"\n',
        )

    def add_patch(self, name: str = "0001-host-bridge.patch") -> Path:
        patch = self.patches / name
        patch.write_text(f"diff --git a/{name} b/{name}\n", encoding="utf-8")
        return patch

    def pins(self) -> str:
        """The pins record deps.sh writes for the current pins and patches."""
        lines = [
            f'photocraft {PINS["TAG"]} {PINS["COMMIT"]}',
            f'rust {PINS["RUST"]} {PINS["HOST"]} wasm32-unknown-unknown',
            f'trunk {PINS["TRUNK"]} {PINS["TRUNK_SHA256"]}',
            f'renderer {PINS["CLI_BUILD"]}',
            "fonts none",
        ]
        for patch in sorted(self.patches.glob("*.patch")):
            lines.append(f"patch {patch.name} {hashlib.sha256(patch.read_bytes()).hexdigest()}")
        return "\n".join(lines) + "\n"

    def installed(self, pins: str, mark: str = "the old site") -> None:
        """An install folder as an earlier run left it, with the given pins record."""
        (self.home / "site").mkdir(parents=True)
        (self.home / "bin").mkdir()
        (self.home / "site/index.html").write_text(mark, encoding="utf-8")
        cli = self.home / "bin/photocraft-cli"
        cli.write_text("#!/bin/sh\necho old\n", encoding="utf-8")
        cli.chmod(0o755)
        (self.home / "photocraft.pins").write_text(pins, encoding="utf-8")

    def run_deps(self, command: str, status: int) -> subprocess.CompletedProcess[str]:
        """Run deps.sh; it must end with `status`. Another status fails the test with all it printed."""
        env = {
            "HOME": str(self.root.parent / "home"),
            "PATH": f"{self.stubs}:{self.system}",
            "STORMEX_PATH": str(self.system),
            "PHOTOCRAFT_PATH": f"{self.stubs}:{self.system}",
            "SC2_PROJECT_ROOT": str(self.root),
            "SC2_BUILD": str(self.build),
            "WEBVIEWER_WORK": str(self.root.parent / "work/webviewer"),
            "SC2_INSTALL": str(self.root.parent / "sc2"),
            "PHOTOCRAFT_HOME": str(self.home),
        }
        result = subprocess.run(
            [str(self.system / "bash"), str(SCRIPT), command], env=env, text=True, capture_output=True
        )
        self.assertEqual(result.returncode, status, result.stdout + result.stderr)
        return result

    def calls_made(self) -> list[str]:
        return self.calls.read_text(encoding="utf-8").splitlines()

    def old_install_is_kept(self) -> None:
        self.assertEqual((self.home / "site/index.html").read_text(encoding="utf-8"), "the old site")
        self.assertEqual((self.home / "photocraft.pins").read_text(encoding="utf-8"), "photocraft v0.0.1 0000\n")
        self.assertFalse(self.home.with_name("photocraft.new").exists())
        self.assertFalse(self.home.with_name("photocraft.old").exists())

    # ------------------------------------------------------------ the pins

    def test_the_pins_are_read_from_deps_sh(self) -> None:
        for name in ("REPO", "TAG", "COMMIT", "RUST", "HOST", "TRUNK", "TRUNK_SHA256", "CLI_BUILD"):
            self.assertTrue(PINS.get(name), name)
        self.assertRegex(PINS["COMMIT"], r"^[0-9a-f]{40}$")
        self.assertRegex(PINS["TRUNK_SHA256"], r"^[0-9a-f]{64}$")

    # ------------------------------------------------------------ install

    def test_the_steps_build_and_install_the_site_the_renderer_the_licences_and_the_pins(self) -> None:
        self.machine()
        patch = self.add_patch()
        result = self.run_deps("photocraft", 0)
        self.assertIn(f'installed photocraft {PINS["TAG"]}: {self.home}', result.stdout)
        # The site, the renderer and the record of what they were built from.
        self.assertIn("./editor.js", (self.home / "site/index.html").read_text(encoding="utf-8"))
        self.assertEqual((self.home / "site/editor_bg.wasm").stat().st_size, 2 * 1024 * 1024)
        cli = self.home / "bin/photocraft-cli"
        self.assertEqual(cli.read_text(encoding="utf-8"), RENDERER)
        self.assertTrue(cli.stat().st_mode & 0o111)
        self.assertEqual((self.home / "photocraft.pins").read_text(encoding="utf-8"), self.pins())
        self.assertIn(f"patch {patch.name} ", self.pins())
        # Upstream's licence, notice and attribution files, beside the site.
        for name in LICENCES:
            self.assertEqual((self.home / "site" / name).read_text(encoding="utf-8"), f"{name} of upstream\n", name)
        # The fonts manifest: one comment line, so no font is named.
        manifest = (self.home / "site/fonts/manifest.txt").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(manifest), 1)
        self.assertTrue(manifest[0].startswith("#"), manifest[0])
        # Negative: the swap leaves no folder beside the install.
        self.assertFalse(self.home.with_name("photocraft.new").exists())
        self.assertFalse(self.home.with_name("photocraft.old").exists())

        calls = self.calls_made()
        clone = f'git -c advice.detachedHead=false clone --depth 1 --branch {PINS["TAG"]} {PINS["REPO"]} {self.src}'
        tree = f'git -c advice.detachedHead=false clone --depth 1 --branch {PINS["TAG"]} file://{self.src} {self.tree}'
        apply = f"git -C {self.tree} apply {patch}"
        site = "trunk build --release --locked"
        renderer = f'cargo build {PINS["CLI_BUILD"]}'
        toolchain = f'rustup toolchain install {PINS["RUST"]} --profile minimal --target wasm32-unknown-unknown --no-self-update'
        for call in (toolchain, clone, tree, apply, site, renderer):
            self.assertIn(call, calls)
        # The order: the toolchain, the clone, the fresh tree, its patches, then the two builds.
        order = [calls.index(call) for call in (toolchain, clone, tree, apply, site, renderer)]
        self.assertEqual(order, sorted(order), calls)
        # Negative: the patch goes to the build tree, never to the first clone.
        self.assertFalse(any(call.startswith(f"git -C {self.src} apply") for call in calls), calls)
        # One log per step.
        for step in ("toolchain", "trunk", "clone", "tree", "build-site", "build-renderer", "check-site", "check-renderer", "install"):
            self.assertTrue((self.logs / f"{step}.log").is_file(), step)

    def test_a_present_install_at_the_pins_does_no_work(self) -> None:
        self.machine()
        self.add_patch()
        self.installed(self.pins())
        result = self.run_deps("photocraft", 0)
        self.assertIn(f'photocraft present: {self.home} ({PINS["TAG"]})', result.stdout)
        self.assertEqual(self.calls_made(), [])  # negative: no clone, no toolchain, no build
        self.assertEqual((self.home / "site/index.html").read_text(encoding="utf-8"), "the old site")
        self.assertFalse(self.logs.exists())

    # ------------------------------------------------------------ check

    def test_check_names_no_install_as_optional_with_the_command(self) -> None:
        # The machine of the test lacks the required tools of the project: the check ends with 1.
        result = self.run_deps("check", 1)
        self.assertRegex(result.stdout, r"(?m)^OPTIONAL +photocraft +not installed; only texture editing needs it \(make install-photocraft\)$")
        self.assertNotRegex(result.stdout, r"(?m)^MISSING +photocraft ")

    def test_check_names_a_pinned_install(self) -> None:
        self.installed(self.pins())
        # The machine of the test lacks the required tools of the project: the check ends with 1.
        result = self.run_deps("check", 1)
        self.assertRegex(result.stdout, rf'(?m)^OK +photocraft +{re.escape(str(self.home))} \({re.escape(PINS["TAG"])}\)$')

    def test_check_names_the_pin_a_stale_install_was_built_without(self) -> None:
        self.installed(self.pins())
        patch = self.add_patch("0002-later.patch")
        # The machine of the test lacks the required tools of the project: the check ends with 1.
        result = self.run_deps("check", 1)
        pin = f"patch {patch.name} {hashlib.sha256(patch.read_bytes()).hexdigest()}"
        self.assertRegex(result.stdout, rf'(?m)^OPTIONAL +photocraft +stale: built without the pin "{re.escape(pin)}"; run: make install-photocraft$')
        self.assertNotRegex(result.stdout, r"(?m)^OK +photocraft ")

    def test_check_names_an_install_built_with_a_pin_that_is_gone(self) -> None:
        self.installed(self.pins() + "patch 0009-gone.patch 00\n")
        # The machine of the test lacks the required tools of the project: the check ends with 1.
        result = self.run_deps("check", 1)
        self.assertRegex(result.stdout, r"(?m)^OPTIONAL +photocraft +stale: built with a pin that is gone; run: make install-photocraft$")

    def test_a_stale_install_is_built_again(self) -> None:
        self.machine()
        self.installed("photocraft v0.0.1 0000\n")
        result = self.run_deps("photocraft", 0)
        self.assertNotIn("photocraft present", result.stdout)
        self.assertEqual((self.home / "photocraft.pins").read_text(encoding="utf-8"), self.pins())
        self.assertIn("./editor.js", (self.home / "site/index.html").read_text(encoding="utf-8"))
        self.assertFalse(self.home.with_name("photocraft.old").exists())

    # ------------------------------------------------------------ a failed step

    def test_a_trunk_archive_of_another_hash_stops_the_steps_and_keeps_the_old_install(self) -> None:
        self.machine(archive_as_pinned=False)
        self.installed("photocraft v0.0.1 0000\n")
        result = self.run_deps("photocraft", 1)
        log = self.logs / "trunk.log"
        self.assertIn(f"photocraft: step 'trunk' failed; log: {log}", result.stderr)
        self.assertIn(f'not {PINS["TRUNK_SHA256"]}', log.read_text(encoding="utf-8"))
        calls = self.calls_made()
        # Negative: nothing is unpacked, cloned or built after the failed step.
        self.assertFalse(any(call.startswith(("tar ", "git ", "trunk ", "cargo ")) for call in calls), calls)
        self.old_install_is_kept()

    def test_a_patch_that_does_not_fit_stops_the_steps_and_keeps_the_old_install(self) -> None:
        self.machine(patches_fit=False)
        self.add_patch()
        self.installed("photocraft v0.0.1 0000\n")
        result = self.run_deps("photocraft", 1)
        log = self.logs / "tree.log"
        self.assertIn(f"photocraft: step 'tree' failed; log: {log}", result.stderr)
        self.assertIn(f'patch 0001-host-bridge.patch does not apply to {PINS["TAG"]}', log.read_text(encoding="utf-8"))
        self.assertFalse(any(call.startswith(("trunk ", "cargo ")) for call in self.calls_made()))
        self.old_install_is_kept()

    def test_a_site_with_too_small_a_module_fails_its_check_and_keeps_the_old_install(self) -> None:
        self.machine(module_bytes=1024)
        self.installed("photocraft v0.0.1 0000\n")
        result = self.run_deps("photocraft", 1)
        log = self.logs / "check-site.log"
        self.assertIn(f"photocraft: step 'check-site' failed; log: {log}", result.stderr)
        self.assertIn("has 1024 bytes: too small for the editor", log.read_text(encoding="utf-8"))
        # Both builds ran; the install step did not.
        self.assertTrue(any(call.startswith("cargo build") for call in self.calls_made()))
        self.assertFalse((self.logs / "install.log").exists())
        self.old_install_is_kept()

    def test_a_first_clone_at_another_commit_stops_the_steps(self) -> None:
        self.machine()
        git = (self.stubs / "git").read_text(encoding="utf-8").replace(f'echo {PINS["COMMIT"]}', f'echo {"1" * 40}')
        (self.stubs / "git").write_text(git, encoding="utf-8")
        result = self.run_deps("photocraft", 1)
        log = self.logs / "tree.log"
        self.assertIn(f"photocraft: step 'tree' failed; log: {log}", result.stderr)
        self.assertIn(f'names {"1" * 40}, not {PINS["COMMIT"]}', log.read_text(encoding="utf-8"))
        self.assertFalse(any(call.startswith(("trunk ", "cargo ")) for call in self.calls_made()))
        self.assertFalse(self.home.exists())  # negative: no install is made


if __name__ == "__main__":
    unittest.main()
