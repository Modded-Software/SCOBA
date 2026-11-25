"""Where the project writes (SPEC-PATHS). Reads the environment only.

scripts/paths.sh is the one resolver. It reads env/paths.conf, derives every
path, checks it and exports it. `make` and scripts/playtest.sh source it
before they start anything. This module only reads those variables. It
names no folder, file or prefix layout itself.

`path(name)` takes the variable's own name, so a grep for the name finds
every use.
"""

import os
from pathlib import Path

# Every path scripts/paths.sh exports (PATHS_ALL there; test_workpaths checks).
# True: a folder paths.sh made. False: a path that may not exist yet, such as
# the map before the first build or a prefix before the game is installed.
NAMES = {
    "SC2_WORK": True,
    "SC2_OUT": True,
    "SC2_BUILD": True,
    "SC2_TEST_RUNS": True,
    "SC2_TESTKIT": True,
    "SC2_TMP": True,
    "SC2RES": True,
    "WEBVIEWER_WORK": True,
    "TEXTURE_STORE": False,
    "UV_PROJECT_ENVIRONMENT": False,
    "BNET_PREFIX": False,
    "SC2_INSTALL": False,
    "SC2_DOCUMENTS": False,
    "SC2_MAP_CACHE": False,
    "SC2_BUILT_MAP": False,
    "SC2_BUILD_STAMP": False,
}


class PathsError(RuntimeError):
    """A path variable is unknown, unset, blank, relative, or not the folder it should be."""


def path(name: str) -> Path:
    """The absolute path in variable `name`, as scripts/paths.sh exported it."""
    if name not in NAMES:
        raise PathsError(f"{name} is no path variable of SPEC-PATHS")
    value = os.environ.get(name)
    if value is None:
        raise PathsError(
            f"{name} is not set: start this through make or scripts/playtest.sh, which source scripts/paths.sh"
        )
    if not value.strip():
        raise PathsError(f"{name} is blank")
    found = Path(value)
    if not found.is_absolute():
        raise PathsError(f"{name} is not absolute: {value}")
    if NAMES[name] and not found.is_dir():
        raise PathsError(f"{name} is not a folder: {value}")
    return found
