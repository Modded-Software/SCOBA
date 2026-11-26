"""The dock icon installers: the SCOBA entries with the right GPUs, and the editor entry.

Every entry starts through the launch dialog (REQ-LAUNCH-DIALOG).
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from project_root import project_root

SCRIPT = project_root() / "scripts" / "install-dock-icon.sh"
EDITOR_SCRIPT = project_root() / "scripts" / "install-editor-dock-icon.sh"
GPU_ENV = project_root() / "env" / "gpu-env.sh"


class InstallDockIconTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.bin = root / "bin"
        self.drm = root / "dri"
        self.apps = self.home / ".local" / "share" / "applications"
        self.favorites = root / "favorites.txt"
        self.home.mkdir()
        self.bin.mkdir()
        self.drm.mkdir()
        (self.drm / "pci-0000:09:00.0-render").touch()
        (self.drm / "pci-0000:03:00.0-render").touch()
        layer = self.home / ".local" / "share" / "vulkan" / "implicit_layer.d"
        layer.mkdir(parents=True)
        (layer / "VkLayer_LSFGVK_frame_generation.json").write_text("{}\n", encoding="utf-8")
        lib = self.home / ".local" / "lib"
        lib.mkdir(parents=True)
        (lib / "liblsfg-vk-layer.so").touch()
        self.favorites.write_text("[]\n", encoding="utf-8")
        self.stub("uv", "exit 0\n")
        self.stub("desktop-file-validate", "exit 0\n")
        self.stub("update-desktop-database", "exit 0\n")
        self.stub("gtk-update-icon-cache", "exit 0\n")
        self.stub(
            "gsettings",
            "#!/bin/sh\n"
            f'case "$1" in\n'
            f'  get) cat "{self.favorites}" ;;\n'
            f'  set) printf "%s\\n" "$4" > "{self.favorites}" ;;\n'
            "  *) exit 1 ;;\n"
            "esac\n",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def stub(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def run_installer(self, **overrides: str) -> subprocess.CompletedProcess[str]:
        env = dict(
            os.environ,
            HOME=str(self.home),
            PATH=f"{self.bin}:{os.environ['PATH']}",
            SCOBA_DRM_BY_PATH=str(self.drm),
            # Named, not found from $0: the path of a script is not its own in every shell.
            SC2_PROJECT_ROOT=str(project_root()),
        )
        env.update(overrides)
        return subprocess.run(["bash", str(SCRIPT)], env=env, text=True, capture_output=True)

    def test_both_entries_are_provisioned(self) -> None:
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("scoba.desktop", "scoba-fg.desktop"):
            path = self.apps / name
            self.assertTrue(path.is_file(), name)
            self.assertTrue(path.stat().st_mode & 0o111, name)

    def test_default_entries_leave_gpu_choice_to_the_launcher(self) -> None:
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        fg = (self.apps / "scoba-fg.desktop").read_text(encoding="utf-8")
        self.assertNotIn("DRI_PRIME", fg)
        self.assertNotIn("LSFGVK_GPU", fg)
        self.assertNotIn("SCOBA_GAME_GPU", fg)
        self.assertNotIn("SCOBA_FG_GPU", fg)
        self.assertIn('LSFGVK_ENV="1"', fg)
        self.assertIn("game on GPU 0000:09:00.0", fg)
        self.assertIn("frame generation on GPU 0000:03:00.0", fg)

    def test_install_time_gpu_override_is_written_to_both_entries(self) -> None:
        result = self.run_installer(SCOBA_GAME_GPU="0000:03:00.0", SCOBA_FG_GPU="0000:09:00.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plain = (self.apps / "scoba.desktop").read_text(encoding="utf-8")
        fg = (self.apps / "scoba-fg.desktop").read_text(encoding="utf-8")
        self.assertEqual(plain.count('SCOBA_GAME_GPU="0000:03:00.0"'), 2)  # the entry and its one action
        self.assertEqual(fg.count('SCOBA_GAME_GPU="0000:03:00.0"'), 2)
        self.assertEqual(fg.count('SCOBA_FG_GPU="0000:09:00.0"'), 2)
        self.assertNotIn("pci-0000_03_00_0", plain)  # negative: provisioner does not pin DRI
        self.assertIn("game on GPU 0000:03:00.0", fg)
        self.assertIn("frame generation on GPU 0000:09:00.0", fg)

    def test_plain_entry_has_no_frame_generation(self) -> None:
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        plain = (self.apps / "scoba.desktop").read_text(encoding="utf-8")
        self.assertNotIn("DRI_PRIME", plain)
        self.assertNotIn("LSFGVK", plain)

    def test_the_one_action_is_the_instant_launch_and_no_entry_picks_textures(self) -> None:
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in ("scoba.desktop", "scoba-fg.desktop"):
            entry = (self.apps / name).read_text(encoding="utf-8")
            self.assertIn("Actions=built;\n", entry)
            self.assertEqual(entry.count("[Desktop Action "), 1, name)
            self.assertIn('launch-dialog.sh" launch-built\n', entry)
            self.assertIn('launch-dialog.sh" launch\n', entry)
            self.assertIn("Right-click: Instant Launch (no build)", entry)
            self.assertNotIn("HD_TEXTURES", entry)  # negative: the build takes its textures from the store
            self.assertNotIn("Textures", entry)

    def test_every_exec_line_goes_through_the_launch_dialog(self) -> None:
        result = self.run_installer(SCOBA_GAME_GPU="0000:03:00.0", SCOBA_FG_GPU="0000:09:00.0")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        root = project_root()
        for name, extra in (("scoba.desktop", ""), ("scoba-fg.desktop", 'LSFGVK_ENV="1" LSFGVK_MULTIPLIER="2" LSFGVK_PERFORMANCE_MODE="1" SCOBA_FG_GPU="0000:09:00.0" ')):
            lines = [line for line in (self.apps / name).read_text(encoding="utf-8").splitlines() if line.startswith("Exec=")]
            self.assertEqual(len(lines), 2, name)  # the entry and its one action
            for line, action in zip(lines, ("launch", "launch-built")):
                self.assertTrue(line.endswith(f' bash "{root}/scripts/launch-dialog.sh" {action}'), line)
                # The dialog hands its environment to the build and the launch.
                for kept in (f'UV_BIN="{self.bin}/uv"', f'SC2_PROJECT_ROOT="{root}"', 'SC2_WINDOW_WIDTH="1920"',
                             'SC2_WINDOW_HEIGHT="1080"', 'SCOBA_GAME_GPU="0000:03:00.0"', extra):
                    self.assertIn(kept, line)
                self.assertNotIn("playtest.sh", line)  # negative: no entry starts a build with no dialog

    def test_a_dialog_that_cannot_load_fails_before_writing_entries(self) -> None:
        self.stub("gjs", 'echo "gjs: cannot load Gtk" >&2\nexit 1\n')
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("launch dialog cannot start: gjs: cannot load Gtk", result.stdout + result.stderr)
        self.assertFalse((self.apps / "scoba.desktop").exists())
        self.assertFalse((self.apps / "scoba-fg.desktop").exists())

    def test_both_entries_are_added_to_favorites(self) -> None:
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        favorites = self.favorites.read_text(encoding="utf-8").splitlines()[-1]
        self.assertIn("'scoba.desktop'", favorites)
        self.assertIn("'scoba-fg.desktop'", favorites)

    def test_missing_lsfg_layer_fails_before_writing_entries(self) -> None:
        (self.home / ".local/share/vulkan/implicit_layer.d/VkLayer_LSFGVK_frame_generation.json").unlink()
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lsfg-vk layer not found", result.stdout + result.stderr)
        self.assertFalse((self.apps / "scoba-fg.desktop").exists())


class InstallEditorDockIconTest(unittest.TestCase):
    """The editor entry, installed into a scratch home against a scratch StarCraft II."""

    OUT_ARG = 'while [ $# -gt 0 ]; do if [ "$1" = "-o" ]; then out="$2"; fi; shift; done\n'

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.bin = root / "bin"
        self.apps = self.home / ".local" / "share" / "applications"
        self.favorites = root / "favorites.txt"
        self.install = root / "sc2"
        self.map = root / "map"
        self.prefix = root / "prefix"
        self.steam = root / "steam"
        proton = self.steam / "compatibilitytools.d" / "GE-Proton-test" / "proton"
        for folder in (self.home, self.bin, self.install / "Support64", self.map, self.prefix / "dosdevices", proton.parent):
            folder.mkdir(parents=True)
        (self.install / "StarCraft II Editor_x64.exe").touch()
        (self.install / "Support64" / "SC2Editor_x64.exe").touch()
        (self.map / "ComponentList.SC2Components").touch()
        (self.prefix / "dosdevices" / "z:").symlink_to("/")
        proton.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        proton.chmod(0o755)
        self.favorites.write_text("[]\n", encoding="utf-8")
        self.stub("wrestool", self.OUT_ARG + ': > "$out"\n')
        self.stub("icotool", self.OUT_ARG + ': > "$out/editor_1_256x256.png"\n')
        self.stub("desktop-file-validate", "exit 0\n")
        self.stub("update-desktop-database", "exit 0\n")
        self.stub("gtk-update-icon-cache", "exit 0\n")
        self.stub("gsettings", f'case "$1" in\n  get) cat "{self.favorites}" ;;\n  set) printf "%s\\n" "$4" > "{self.favorites}" ;;\n  *) exit 1 ;;\nesac\n')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def stub(self, name: str, body: str) -> None:
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body, encoding="utf-8")
        path.chmod(0o755)

    def run_installer(self) -> subprocess.CompletedProcess[str]:
        env = dict(
            os.environ,
            HOME=str(self.home),
            PATH=f"{self.bin}:{os.environ['PATH']}",
            SC2_PROJECT_ROOT=str(project_root()),
            SC2_INSTALL=str(self.install),
            SC2_BUILT_MAP=str(self.map),
            BNET_PREFIX=str(self.prefix),
            # Any name: the installer takes the folder that holds it.
            SC2_WINE_DRIVE="disk-c",
            STEAM_ROOT=str(self.steam),
        )
        env.pop("SC2_EDITOR_MAP", None)
        return subprocess.run(["bash", str(EDITOR_SCRIPT)], env=env, text=True, capture_output=True)

    def test_the_entry_opens_the_editor_through_the_launch_dialog(self) -> None:
        result = self.run_installer()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        root = project_root()
        entry = (self.apps / "scoba-editor.desktop").read_text(encoding="utf-8")
        lines = [line for line in entry.splitlines() if line.startswith("Exec=")]
        self.assertEqual(lines, [f'Exec=env SC2_PROJECT_ROOT="{root}" bash "{root}/scripts/launch-dialog.sh" editor'])
        self.assertNotIn("launch-editor.sh", entry)  # negative: the editor does not start with no dialog
        self.assertTrue((self.home / ".local/share/icons/hicolor/256x256/apps/scoba-editor.png").is_file())
        self.assertIn("'scoba-editor.desktop'", self.favorites.read_text(encoding="utf-8"))

    def test_a_dialog_that_cannot_load_fails_before_writing_the_entry(self) -> None:
        self.stub("gjs", 'echo "gjs: cannot load Gtk" >&2\nexit 1\n')
        result = self.run_installer()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("launch dialog cannot start: gjs: cannot load Gtk", result.stdout + result.stderr)
        self.assertFalse((self.apps / "scoba-editor.desktop").exists())


class GpuEnvTest(unittest.TestCase):
    def run_env(self, **overrides: str) -> tuple[str, str]:
        env = dict(os.environ)
        for name in ("DRI_PRIME", "LSFGVK_ENV", "LSFGVK_GPU", "SCOBA_GAME_GPU", "SCOBA_FG_GPU"):
            env.pop(name, None)
        env.update(overrides)
        command = '. "$1"; sc2_apply_gpu_env; printf "%s\\n%s\\n" "${DRI_PRIME:-}" "${LSFGVK_GPU:-}"'
        result = subprocess.run(
            ["bash", "-c", command, "bash", str(GPU_ENV)],
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        game, frame_gen = result.stdout.splitlines()
        return (game, frame_gen)

    def test_game_default_is_gpu1(self) -> None:
        self.assertEqual(self.run_env(), ("pci-0000_09_00_0", ""))

    def test_game_gpu_env_overrides_the_default(self) -> None:
        self.assertEqual(self.run_env(SCOBA_GAME_GPU="0000:03:00.0")[0], "pci-0000_03_00_0")

    def test_explicit_dri_prime_is_kept(self) -> None:
        self.assertEqual(self.run_env(DRI_PRIME="1")[0], "1")

    def test_fg_defaults_to_gpu0_only_when_fg_is_on(self) -> None:
        self.assertEqual(self.run_env(SCOBA_FG_GPU="0000:09:00.0"), ("pci-0000_09_00_0", ""))
        self.assertEqual(self.run_env(LSFGVK_ENV="1", SCOBA_FG_GPU="0000:09:00.0")[1], "0000:09:00.0")

    def test_explicit_lsfg_gpu_is_kept(self) -> None:
        self.assertEqual(
            self.run_env(LSFGVK_ENV="1", LSFGVK_GPU="0000:03:00.0", SCOBA_FG_GPU="0000:09:00.0")[1],
            "0000:03:00.0",
        )


if __name__ == "__main__":
    unittest.main()