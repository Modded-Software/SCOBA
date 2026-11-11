#!/usr/bin/env python3
"""Build and run test profiles."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from project_root import project_root
from testkit.map_builder import build_instrumented_map
from testkit.profiles.registry import PROFILE_OUTPUTS, profile_module
from testkit.runner import run_test

ROOT = project_root()


def delegate(action: str, profile: str) -> None:
    if os.environ.get("SC2_PLAYTEST_ACTIVE") == "1":
        return
    entry = ROOT / "scripts" / "playtest.sh"
    env = {**os.environ, "SC2_PLAYTEST_ACTIVE": "1"}
    os.execvpe("bash", ["bash", str(entry), action, profile], env)


def build(profile: str, output: Path | None) -> int:
    module = profile_module(profile)
    spec = module.map_spec()
    if output is not None:
        spec = type(spec)(
            profile=spec.profile,
            source=spec.source,
            output=output,
            bank_names=spec.bank_names,
            galaxy_files=spec.galaxy_files,
            galaxy_includes=spec.galaxy_includes,
            init_calls=spec.init_calls,
            options=spec.options,
        )
    path = build_instrumented_map(spec)
    print(path)
    return 0


def run(profile: str, launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> int:
    module = profile_module(profile)
    spec = module.run_spec(launch_timeout_s, case_timeout_s, run_root)
    return run_test(spec)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "run"))
    parser.add_argument("profile")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--launch-timeout", type=float)
    parser.add_argument("--case-timeout", type=float)
    parser.add_argument("--run-root", type=Path)
    parser.add_argument("--visual", action="store_true")
    args = parser.parse_args()
    if args.action == "build":
        delegate("build-profile", args.profile)
        return build(args.profile, args.out)
    delegate("run-profile", args.profile)
    launch_timeout_s = args.launch_timeout if args.launch_timeout is not None else 20.0
    case_timeout_s = args.case_timeout if args.case_timeout is not None else 20.0
    run_root = args.run_root or ROOT / "out" / "test-runs"
    return run(args.profile, launch_timeout_s, case_timeout_s, run_root)


if __name__ == "__main__":
    raise SystemExit(main())