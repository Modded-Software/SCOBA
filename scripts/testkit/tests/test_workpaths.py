"""SPEC-PATHS: one resolver, env-only readers, nothing heavy on the repo disk."""

import ast
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import workpaths
from project_root import project_root

ROOT = project_root()
SCRIPTS = ROOT / "scripts"
PRINT = SCRIPTS / "testkit" / "tests" / "paths_print.sh"
# Files that may name the layout: the resolver, its config, this guard.
LAYOUT_OWNERS = {
    SCRIPTS / "paths.sh",
    SCRIPTS / "workpaths.py",
    SCRIPTS / "testkit" / "tests" / "test_workpaths.py",
}
# Text that hard-codes a place the resolver owns.
HARD_CODED = (
    (
        re.compile(
            r"""(?<![.\w])(?:ROOT|root|project_root\(\))\s*/\s*["'](?:out|build)["']"""
        ),
        "a join below the repo's out or build",
    ),
    (
        re.compile(r"""Path\(\s*["'](?:\./)?(?:out|build)(?:/[^"']*)?["']\s*\)"""),
        "a relative out or build path",
    ),
    (
        re.compile(r"""\$\{?ROOT_DIR\}?/(?:out|build)\b"""),
        "the repo's out or build in shell",
    ),
    (re.compile(r"""["']/tmp\b"""), "the system /tmp"),
    (re.compile(r"battlenet-prefix"), "the game prefix"),
    (re.compile(r"drive_c|steamuser"), "the Wine prefix layout"),
)


def _sources(*patterns: str) -> list[Path]:
    found: set[Path] = set()
    for pattern in patterns:
        found.update(SCRIPTS.rglob(pattern))
    return sorted(
        p for p in found if "vendor" not in p.parts and p not in LAYOUT_OWNERS
    )


def _printed(env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    # This run's own exports would win over the file; start from none of them.
    derived = set(workpaths.NAMES) | {"TMPDIR"}
    clean = {key: value for key, value in os.environ.items() if key not in derived}
    full = {**clean, "SC2_PROJECT_ROOT": str(ROOT), **env}
    try:
        return subprocess.run(
            ["bash", str(PRINT), *args],
            env=full,
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as error:
        raise AssertionError(f"paths.sh refused (rc {error.returncode}): {error.stderr}") from error


def _refused(env: dict[str, str], *args: str) -> str:
    """What paths.sh prints when it refuses `env`. A run it takes fails the test."""
    try:
        done = _printed(env, *args)
    except AssertionError as refused:
        return str(refused)
    raise AssertionError(f"paths.sh took {env}: {done.stdout}")


def _exported(env: dict[str, str]) -> dict[str, str]:
    return dict(line.split("=", 1) for line in _printed(env).stdout.splitlines())


class ResolverTest(unittest.TestCase):
    """scripts/paths.sh derives, checks and exports every path."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name) / "work"

    def test_it_exports_every_name_python_reads_and_no_other(self) -> None:
        exported = _exported({"SC2_WORK": str(self.work)})
        self.assertEqual(set(exported) - {"TMPDIR"}, set(workpaths.NAMES))

    def test_every_path_derives_from_the_work_root_or_the_prefix(self) -> None:
        exported = _exported({"SC2_WORK": str(self.work), "BNET_PREFIX": "/prefix"})
        for name, value in exported.items():
            self.assertTrue(Path(value).is_absolute(), name)
        self.assertEqual(exported["TMPDIR"], str(self.work / "tmp"))
        self.assertEqual(exported["SC2_OUT"], str(self.work / "out"))
        self.assertEqual(exported["UV_PROJECT_ENVIRONMENT"], str(self.work / "venv"))
        self.assertTrue(exported["SC2_DOCUMENTS"].startswith("/prefix/"))
        self.assertTrue(exported["SC2_BUILT_MAP"].startswith(exported["SC2_OUT"] + "/"))
        for name in ("SC2_OUT", "SC2_BUILD", "SC2_TEST_RUNS", "SC2_TESTKIT", "SC2_TMP"):
            self.assertTrue(Path(exported[name]).is_dir(), name)

    def test_the_environment_wins(self) -> None:
        other = Path(self.temp.name) / "elsewhere"
        exported = _exported({"SC2_WORK": str(self.work), "SC2_OUT": str(other)})
        self.assertEqual(exported["SC2_OUT"], str(other))
        self.assertEqual(exported["SC2_BUILT_MAP"], str(other / "SCOBA256.SC2Map"))

    def test_a_blank_or_relative_path_is_refused(self) -> None:
        for env in (
            {"SC2_WORK": "  "},
            {"SC2_WORK": str(self.work), "SC2_OUT": "rel/out"},
        ):
            self.assertIn("ERROR", _refused(env), env)

    def test_a_folder_on_the_repo_disk_is_refused(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as inside:
            env = {"SC2_WORK": str(self.work), "SC2_TMP": inside}
            if os.stat(inside).st_dev == os.stat(self.work.parent).st_dev:
                self.skipTest("the scratch folder of this run is on the repo disk")
            self.assertIn("disk of the repository", _refused(env, "--device"))
            self.assertEqual(
                _printed({**env, "SC2_ALLOW_REPO_DISK": "1"}, "--device").returncode, 0
            )


class ReaderTest(unittest.TestCase):
    """scripts/workpaths.py reads; a bad value is an error, not a guess."""

    def test_a_set_folder_is_returned(self) -> None:
        with (
            tempfile.TemporaryDirectory() as folder,
            mock.patch.dict(os.environ, {"SC2_OUT": folder}),
        ):
            self.assertEqual(workpaths.path("SC2_OUT"), Path(folder))

    def test_each_bad_value_raises(self) -> None:
        with tempfile.NamedTemporaryFile() as file:
            cases = {
                "": "blank",
                " ": "blank",
                "rel/out": "not absolute",
                file.name: "not a folder",
            }
            for value, words in cases.items():
                with (
                    mock.patch.dict(os.environ, {"SC2_OUT": value}),
                    self.assertRaisesRegex(workpaths.PathsError, words),
                ):
                    workpaths.path("SC2_OUT")
        with mock.patch.dict(os.environ):
            os.environ.pop("SC2_OUT", None)
            with self.assertRaisesRegex(
                workpaths.PathsError, "make or scripts/playtest.sh"
            ):
                workpaths.path("SC2_OUT")
        with self.assertRaisesRegex(workpaths.PathsError, "no path variable"):
            workpaths.path("SC2_NOT_A_NAME")

    def test_a_path_that_may_be_missing_is_not_checked_for_a_folder(self) -> None:
        with mock.patch.dict(os.environ, {"SC2_BUILT_MAP": "/nowhere/map.SC2Map"}):
            self.assertEqual(
                workpaths.path("SC2_BUILT_MAP"), Path("/nowhere/map.SC2Map")
            )


def _import_time(tree: ast.Module):
    """Expressions Python evaluates when the module is imported."""
    for stmt in tree.body:
        if isinstance(stmt, (ast.Import, ast.ImportFrom)):
            continue
        if isinstance(stmt, ast.If) and "__main__" in ast.unparse(stmt.test):
            continue
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield from stmt.decorator_list
            yield from stmt.args.defaults
            yield from (d for d in stmt.args.kw_defaults if d is not None)
        elif isinstance(stmt, ast.ClassDef):
            yield from stmt.decorator_list
            for inner in stmt.body:
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield from inner.decorator_list
                    yield from inner.args.defaults
                    yield from (d for d in inner.args.kw_defaults if d is not None)
                else:
                    yield inner
        else:
            yield stmt


def _reads_paths(tree: ast.Module) -> set[str]:
    """Module functions that call workpaths.path, directly or through each other."""
    bodies = {
        s.name: s
        for s in tree.body
        if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    found: set[str] = set()
    while True:
        more = {
            name
            for name, body in bodies.items()
            if name not in found and _calls(body, found)
        }
        if not more:
            return found
        found |= more


def _calls(node: ast.AST, local: set[str]) -> bool:
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "path"
            and isinstance(func.value, ast.Name)
            and func.value.id == "workpaths"
        ):
            return True
        if isinstance(func, ast.Name) and func.id in local:
            return True
    return False


class CallerTest(unittest.TestCase):
    """Callers ask workpaths when they run; none names a place itself."""

    def test_no_module_reads_a_path_at_import(self) -> None:
        bad = []
        for file in _sources("*.py"):
            tree = ast.parse(file.read_text(encoding="utf-8"))
            local = _reads_paths(tree)
            bad.extend(
                f"{file.relative_to(ROOT)}:{node.lineno}"
                for node in _import_time(tree)
                if _calls(node, local)
            )
        self.assertFalse(bad, "\n" + "\n".join(bad))

    def test_no_file_hard_codes_a_place_the_resolver_owns(self) -> None:
        bad = []
        for file in _sources("*.py", "*.sh"):
            for number, line in enumerate(
                file.read_text(encoding="utf-8").splitlines(), 1
            ):
                for pattern, what in HARD_CODED:
                    if pattern.search(line):
                        bad.append(f"{file.relative_to(ROOT)}:{number}: {what}")
        self.assertFalse(bad, "\n" + "\n".join(bad))

    def test_no_python_reads_a_path_variable_past_workpaths(self) -> None:
        names = "|".join(sorted(workpaths.NAMES))
        # A read; a harness may still set a variable for what it starts.
        pattern = re.compile(
            rf"""environ(?:\.get\(\s*["'](?:{names}|SC2_TEST_RUN_ROOT|SC2_GAME_PREFIX)["']"""
            rf"""|\[\s*["'](?:{names}|SC2_TEST_RUN_ROOT|SC2_GAME_PREFIX)["']\s*\](?!\s*=[^=]))"""
        )
        bad = []
        for file in _sources("*.py"):
            for number, line in enumerate(
                file.read_text(encoding="utf-8").splitlines(), 1
            ):
                if pattern.search(line) and "mock" not in line:
                    bad.append(f"{file.relative_to(ROOT)}:{number}")
        self.assertFalse(bad, "\n" + "\n".join(bad))


if __name__ == "__main__":
    unittest.main()
