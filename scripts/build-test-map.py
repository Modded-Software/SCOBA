#!/usr/bin/env python3
"""Build the combat test map."""

from testmap import build, delegate


if __name__ == "__main__":
    delegate("build-profile", "combat")
    raise SystemExit(build("combat", None))