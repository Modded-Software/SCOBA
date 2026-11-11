#!/usr/bin/env python3
"""Build the aim test map."""

from testmap import build, delegate


if __name__ == "__main__":
    delegate("build-profile", "aim")
    raise SystemExit(build("aim", None))