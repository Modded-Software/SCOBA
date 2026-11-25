#!/usr/bin/env python3
"""Run the controls test profile."""

import os

import workpaths
from project_root import project_root
from testmap import delegate, run

ROOT = project_root()


if __name__ == "__main__":
    delegate("run-profile", "controls")
    launch_timeout_s = float(os.environ.get("SC2_LAUNCH_TIMEOUT", "20"))
    case_timeout_s = float(os.environ.get("SC2_CASE_TIMEOUT", "20"))
    run_root = workpaths.path("SC2_TEST_RUNS")
    raise SystemExit(run("controls", launch_timeout_s, case_timeout_s, run_root))