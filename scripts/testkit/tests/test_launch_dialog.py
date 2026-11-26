"""Host tests of the launch dialog (REQ-LAUNCH-DIALOG).

The dialog runs for real, on a private broadway display: nothing shows on
the desktop. Its commands are scripted ones in a scratch project folder, and
its target process is a renamed `sleep`. The dialog writes its state to a
report file; the tests read that file and the processes. How the dialog
looks is an operator check.
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from project_root import project_root

ROOT = project_root()
UI = ROOT / "scripts" / "launchui"
WRAPPER = ROOT / "scripts" / "launch-dialog.sh"
CLOSE_S = 2.5  # window.js CLOSE_MS

BUILD_LINES = """\
echo "fresh build: src"
echo "expanding map"
echo "normalizing line endings"
echo "writing build stamp"
echo "writing manifest"
echo "validating map"
echo "OK: built"
"""
# What scripts/launch-scoba.sh does: output to the log file, then the game.
HAND_OVER = """\
exec >>"$XDG_STATE_HOME/scoba/@LOG@" 2>&1
stamp() { date '+%Y-%m-%d %H:%M:%S'; }
"""
GAME_LINES = """\
echo "$(stamp) gpu: game pci-test"
echo "$(stamp) source: /x"
echo "$(stamp) stamp: abc-123"
echo "$(stamp) launching SCOBA.SC2Map"
"""


def need(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise unittest.SkipTest(f"needs {tool}")
    return path


def bracket(name: str) -> str:
    """A pgrep pattern for `name` that does not match a command line holding the pattern."""
    return f"{name[:5]}[{name[5]}]{name[6:]}"


def pids(name: str) -> list[str]:
    result = subprocess.run(["pgrep", "-f", "--", bracket(name)], text=True, capture_output=True)
    return result.stdout.split()


class LogicTest(unittest.TestCase):
    def run_gjs(self, name: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([need("gjs"), "-m", str(UI / "tests" / name), *args], text=True, capture_output=True, timeout=120)

    def test_tracker(self) -> None:
        result = self.run_gjs("tracker_test.js")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("failures: 0", result.stdout)
        self.assertNotIn("tests: 0 ", result.stdout)

    def test_markers_match_the_scripts(self) -> None:
        result = self.run_gjs("markers_test.js", str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("failures: 0", result.stdout)
        self.assertNotIn("tests: 0 ", result.stdout)

    def test_runner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            result = self.run_gjs("runner_test.js", tmp)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("failures: 0", result.stdout)
        self.assertNotIn("tests: 0 ", result.stdout)


class WrapperTest(unittest.TestCase):
    def run_wrapper(self, *args: str) -> subprocess.CompletedProcess[str]:
        need("gjs")
        # The dock entries name the project folder the same way.
        env = dict(os.environ, SC2_PROJECT_ROOT=str(ROOT))
        return subprocess.run(["bash", str(WRAPPER), *args], env=env, text=True, capture_output=True, timeout=60)

    def test_check_loads_the_toolkit(self) -> None:
        result = self.run_wrapper("--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout, r"^gjs 1\.\d+\.\d+, GTK 4\.\d+\.\d+, libadwaita 1\.\d+\.\d+\n$")

    def test_no_action_is_refused(self) -> None:
        result = self.run_wrapper()
        self.assertEqual(result.returncode, 1)
        self.assertIn("usage: launch-dialog.sh", result.stderr)

    def test_unknown_action_is_refused(self) -> None:
        result = self.run_wrapper("launch-everything")
        self.assertEqual(result.returncode, 2)
        self.assertIn("--action is not one of launch, launch-built, editor: launch-everything", result.stderr)


class DialogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gjs = need("gjs")
        daemon = need("gtk4-broadwayd")
        cls.tmp = tempfile.TemporaryDirectory()
        cls.display = 200 + os.getpid() % 500
        cls.daemon_log = open(Path(cls.tmp.name) / "broadwayd.log", "wb")
        cls.daemon = subprocess.Popen(
            [daemon, "--unixsocket", str(Path(cls.tmp.name) / "http.sock"), f":{cls.display}"],
            stdout=cls.daemon_log,
            stderr=cls.daemon_log,
        )
        socket = Path(os.environ["XDG_RUNTIME_DIR"]) / f"broadway{cls.display + 1}.socket"
        deadline = time.time() + 10
        while not socket.exists():
            if cls.daemon.poll() is not None or time.time() > deadline:
                cls.tearDownClass()
                raise RuntimeError(f"gtk4-broadwayd did not open {socket}")
            time.sleep(0.05)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls.daemon.poll() is None:
            cls.daemon.terminate()
            cls.daemon.wait(timeout=10)
        cls.daemon_log.close()
        cls.tmp.cleanup()

    def setUp(self) -> None:
        self.case = Path(tempfile.mkdtemp(dir=self.tmp.name))
        self.root = self.case / "root"
        self.state = self.case / "state"
        self.report = self.case / "report.json"
        # The dialog's own output: a file, so it can never fill a pipe; failures quote it.
        self.output = self.case / "dialog-output.txt"
        (self.root / "scripts").mkdir(parents=True)
        self.target = f"scobadialog{os.getpid()}x{len(os.listdir(self.tmp.name))}"
        self.dialog: subprocess.Popen[str] | None = None
        self.addCleanup(self.stop)

    def stop(self) -> None:
        if self.dialog is not None:
            if self.dialog.poll() is None:
                self.dialog.terminate()
                self.dialog.wait(timeout=10)
        for pid in pids(self.target):  # each by its pid, never by name
            os.kill(int(pid), signal.SIGKILL)

    def command(self, name: str, body: str) -> None:
        text = "#!/usr/bin/env bash\nset -euo pipefail\n" + body
        (self.root / "scripts" / name).write_text(text.replace("@TARGET@", self.target), encoding="utf-8")

    def start(self, action: str, **extra: str) -> None:
        env = dict(os.environ, GDK_BACKEND="broadway", BROADWAY_DISPLAY=f":{self.display}", XDG_STATE_HOME=str(self.state))
        env.update(extra)
        with self.output.open("w", encoding="utf-8") as output:
            self.dialog = subprocess.Popen(
                [self.gjs, "-m", str(UI / "main.js"), "--root", str(self.root), "--action", action,
                 "--process", bracket(self.target), "--report", str(self.report)],
                env=env, text=True, stdout=output, stderr=subprocess.STDOUT,
            )

    def said(self) -> str:
        """What the dialog printed so far."""
        return self.output.read_text(encoding="utf-8")

    def read_report(self) -> dict:
        return json.loads(self.report.read_text(encoding="utf-8"))

    def settled(self, limit_s: float = 20.0) -> dict:
        """The report of the ended run."""
        deadline = time.time() + limit_s
        while time.time() < deadline:
            if self.report.exists():
                return self.read_report()
            if self.dialog.poll() is not None:
                break
            time.sleep(0.05)
        self.fail(f"no report in {limit_s} s; dialog exit {self.dialog.poll()}; it said: {self.said()}")

    def assert_stays_open(self) -> None:
        """Negative of the closing by itself: past the close delay it is still there."""
        time.sleep(CLOSE_S + 2.0)
        self.assertIsNone(self.dialog.poll(), "the dialog closed")
        report = self.read_report()
        self.assertTrue(report["windowVisible"])
        self.assertFalse(report["closing"])

    def test_failed_build_stays_open_with_the_error(self) -> None:
        self.command("playtest.sh", 'echo "expanding map"\necho "ERROR: another build is running" >&2\nexit 1\n')
        self.start("launch")
        report = self.settled()
        self.assertEqual((report["status"], report["reason"], report["exitCode"], report["step"]), ("failed", "exit", 1, "expand"))
        self.assertEqual([s["state"] for s in report["steps"][:3]], ["done", "failed", "pending"])
        self.assertEqual(report["headline"], "Failed: Expand the map")
        self.assertEqual(report["banner"], "Failed: Expand the map. The log has the details.")
        self.assertIn("ERROR: another build is running (exit code 1)", report["detail"])
        self.assertIn("Another build is running. Wait for it to end, then retry.", report["detail"])
        self.assertEqual(report["buttons"], {"retry": True, "lastBuild": True, "main": "Close"})
        self.assertIn("$ bash scripts/playtest.sh launch\nexpanding map\nERROR: another build is running\n", report["logText"])
        self.assertLess(report["fraction"], 1.0)
        saved = Path(report["logFile"])
        self.assertEqual(saved, self.state / "scoba" / "dialog-launch.log")
        self.assertIn("ERROR: another build is running\n", saved.read_text(encoding="utf-8"))
        self.assert_stays_open()

    def test_clean_start_closes_and_the_game_runs_on(self) -> None:
        self.command("playtest.sh", BUILD_LINES + HAND_OVER.replace("@LOG@", "launcher.log") + GAME_LINES + "exec -a @TARGET@ sleep 60\n")
        self.start("launch")
        self.assertEqual(self.dialog.wait(timeout=30), 0, self.said())
        report = self.read_report()
        self.assertEqual((report["status"], report["errorLines"], report["banner"]), ("done", [], ""))
        self.assertTrue(report["closing"])
        self.assertEqual({s["state"] for s in report["steps"]}, {"done"})
        self.assertEqual(len(report["steps"]), 8)
        self.assertEqual(report["headline"], "StarCraft II started")
        self.assertEqual(report["fraction"], 1.0)
        self.assertIn("launching SCOBA.SC2Map\n", report["logText"])
        # The game is not the dialog's to end.
        self.assertEqual(len(pids(self.target)), 1)
        times = json.loads((self.state / "scoba" / "dialog-times.json").read_text(encoding="utf-8"))
        self.assertEqual(list(times), ["launch"])

    def test_start_with_an_error_line_stays_open(self) -> None:
        body = HAND_OVER.replace("@LOG@", "launcher.log") + GAME_LINES
        body += 'echo "$(stamp) ERROR: could not configure Variables.txt"\nexec -a @TARGET@ sleep 60\n'
        self.command("playtest.sh", 'echo "launching the built map, no build"\n' + body)
        self.start("launch-built")
        report = self.settled()
        self.assertEqual(report["status"], "done")
        self.assertEqual(len(report["errorLines"]), 1)
        self.assertEqual(report["banner"], "Started, but the log shows 1 error line.")
        self.assertEqual(report["buttons"], {"retry": False, "lastBuild": False, "main": "Close"})
        self.assert_stays_open()

    def test_editor_error_in_its_log_file_is_shown(self) -> None:
        body = HAND_OVER.replace("@LOG@", "editor.log")
        body += 'echo "$(stamp) ERROR: unpacked map folder not found, run scripts/playtest.sh build: /x"\nexit 1\n'
        self.command("launch-editor.sh", body)
        self.start("editor")
        report = self.settled()
        self.assertEqual((report["status"], report["step"], report["exitCode"]), ("failed", "check", 1))
        self.assertIn("ERROR: unpacked map folder not found", report["detail"])
        self.assertEqual(report["hints"], ["There is no built map yet. Build it with the SCOBA icon first."])
        # Negative: the editor has no build to step around.
        self.assertEqual(report["buttons"], {"retry": True, "lastBuild": False, "main": "Close"})
        self.assert_stays_open()

    def test_a_tool_that_is_not_there_fails_with_the_shell_message(self) -> None:
        self.command("playtest.sh", 'echo "launching the built map, no build"\nscoba-no-such-tool --start\n')
        self.start("launch-built")
        report = self.settled()
        self.assertEqual((report["status"], report["exitCode"]), ("failed", 127))
        self.assertIn("scoba-no-such-tool: command not found", report["detail"])
        self.assertIn("scoba-no-such-tool: command not found", report["logText"])
        self.assert_stays_open()

    def test_buttons(self) -> None:
        """Cancel, Retry, Launch Last Build, Hide, the stop question, Copy Log: window_test.js."""
        work = self.case / "work"
        work.mkdir()
        env = dict(os.environ, GDK_BACKEND="broadway", BROADWAY_DISPLAY=f":{self.display}")
        result = subprocess.run(
            [self.gjs, "-m", str(UI / "tests" / "window_test.js"), str(work)],
            env=env, text=True, capture_output=True, timeout=180,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("tests: 8 failures: 0", result.stdout)
        self.assertEqual(pids("scobawindow"), [], "a process of the button tests is left")

    def test_the_command_runs_in_the_root_with_the_environment_of_the_entry(self) -> None:
        body = 'echo "width=${SC2_WINDOW_WIDTH:-none} fg=${LSFGVK_ENV:-none} other=${SCOBA_NOT_SET:-none}"\n'
        self.command("playtest.sh", body + 'echo "cwd=$PWD"\necho "ERROR: stop here" >&2\nexit 3\n')
        self.start("launch-built", SC2_WINDOW_WIDTH="1234", LSFGVK_ENV="1")
        report = self.settled()
        self.assertEqual(report["exitCode"], 3)
        self.assertIn("width=1234 fg=1 other=none\n", report["logText"])
        self.assertIn(f"cwd={self.root}\n", report["logText"])

    def test_a_long_log_is_shown_in_time_trimmed_and_saved_whole(self) -> None:
        self.command("playtest.sh", 'echo "expanding map"\nseq 1 30000\necho "ERROR: after the flood" >&2\nexit 1\n')
        self.start("launch")
        report = self.settled(limit_s=20.0)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["lines"], 30003)  # the command line, the marker, the numbers, the error
        shown = report["logText"].splitlines()
        self.assertLessEqual(len(shown), 6000)
        self.assertEqual(shown[-2:], ["30000", "ERROR: after the flood"])
        saved = Path(report["logFile"]).read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(saved), 30003)
        self.assertEqual(saved[2], "1")


if __name__ == "__main__":
    unittest.main()
