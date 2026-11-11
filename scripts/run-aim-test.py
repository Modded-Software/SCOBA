#!/usr/bin/env python3
"""Run the aim test profile."""

import os
from pathlib import Path

from project_root import project_root
from testmap import delegate, run

ROOT = project_root()


if __name__ == "__main__":
    delegate("run-profile", "aim")
    launch_timeout_s = float(os.environ.get("SC2_LAUNCH_TIMEOUT", "20"))
    case_timeout_s = float(os.environ.get("SC2_CASE_TIMEOUT", "40"))
    run_root = Path(os.environ.get("SC2_TEST_RUN_ROOT", str(ROOT / "out" / "test-runs")))
    raise SystemExit(run("aim", launch_timeout_s, case_timeout_s, run_root))