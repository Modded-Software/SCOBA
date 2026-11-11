#!/usr/bin/env python3
"""Build the motion test map."""

from project_root import project_root
from testmap import build, delegate

ROOT = project_root()


if __name__ == "__main__":
    delegate("build-profile", "motion")
    raise SystemExit(build("motion", None))