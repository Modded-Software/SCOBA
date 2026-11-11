#!/usr/bin/env python3
"""Build the controls test map."""

from testmap import build, delegate


if __name__ == "__main__":
    delegate("build-profile", "controls")
    raise SystemExit(build("controls", None))