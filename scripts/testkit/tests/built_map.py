"""Skip a host test when the built map is absent, asked when the test runs (SPEC-PATHS)."""

import functools
import unittest

import workpaths

REASON = "needs the built map (scripts/playtest.sh build)"


def _require(parts: tuple[str, ...]) -> None:
    path = workpaths.path("SC2_BUILT_MAP").joinpath(*parts)
    if not path.exists():
        raise unittest.SkipTest(f"{REASON}: {path} is absent")


def needs_built(*parts: str):
    """Decorate a test or a test class: skip it unless SC2_BUILT_MAP/<parts> exists."""

    def decorate(target):
        if isinstance(target, type):
            original = target.setUpClass

            def set_up_class(cls) -> None:
                _require(parts)
                original()

            target.setUpClass = classmethod(set_up_class)
            return target

        @functools.wraps(target)
        def run(*args, **kwargs):
            _require(parts)
            return target(*args, **kwargs)

        return run

    return decorate
