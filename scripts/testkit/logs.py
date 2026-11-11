"""Collect new StarCraft II logs and report failures."""

from __future__ import annotations

import re
import sys
from pathlib import Path

RED = "\033[31m"
RESET = "\033[0m"
ALERT_PREFIX = re.compile(r"^USER\s+\d+\s+[\d.]+\s+[\d.]+\s+(.*)$")
FAIL_WORDS = ("error", "damaged", "failed", "exception", "assert", "script")
SKIP_PREFIXES = (
    "StarCraft II",
    "Executable",
    "Parent Executable",
    "Grandparent Executable",
    "<Parameters>",
    "LocalTime",
    "<ComputerUser>",
    "<ComputerName>",
    "<Exe.Architecture>",
    "<Version>",
    "<DataBuild>",
    "<CodeBranch>",
    "<CodeRevision>",
    "<Locale.",
    "<AccountCountry>",
    "<AgentVersion>",
)


def latest_script_error(logs: Path, started_at: float) -> Path | None:
    if not logs.is_dir():
        return None
    candidates = [p for p in logs.glob("*ScriptError.txt") if p.stat().st_mtime >= started_at]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def collect_new_logs(logs: Path, started_at: float) -> dict:
    result = {"script_errors": [], "error_dirs": [], "alerts": []}
    if not logs.is_dir():
        return result
    result["script_errors"] = sorted(
        p for p in logs.glob("*ScriptError.txt") if p.stat().st_mtime >= started_at
    )
    result["error_dirs"] = sorted(
        p for p in logs.glob("*Error") if p.is_dir() and p.stat().st_mtime >= started_at
    )
    for path in sorted(logs.glob("*Alerts.txt")):
        if path.stat().st_mtime < started_at:
            continue
        for line in path.read_text(errors="replace").splitlines():
            match = ALERT_PREFIX.match(line)
            if not match:
                continue
            message = match.group(1).strip()
            if not message or message.startswith("===="):
                continue
            if message.startswith(SKIP_PREFIXES):
                continue
            result["alerts"].append(f"{path.name}: {message}")
    return result


def print_red(title: str, lines: list[str]) -> None:
    print(f"{RED}{title}{RESET}", file=sys.stderr)
    for line in lines:
        print(f"{RED}{line}{RESET}", file=sys.stderr)


def report_logs(logs: Path, started_at: float) -> tuple[int, dict]:
    data = collect_new_logs(logs, started_at)
    failures = 0
    script_lines: list[str] = []
    for path in data["script_errors"]:
        script_lines.append(str(path))
        script_lines.extend(path.read_text(errors="replace").splitlines())
    if script_lines:
        print_red("CONSOLE SCRIPT ERRORS", script_lines)
        failures += 1
    if data["error_dirs"]:
        print_red("CONSOLE ERROR FOLDERS", [str(p) for p in data["error_dirs"]])
        failures += 1
    if data["alerts"]:
        error_alerts = [
            line for line in data["alerts"] if any(word in line.lower() for word in FAIL_WORDS)
        ]
        warnings = [line for line in data["alerts"] if line not in error_alerts]
        if error_alerts:
            print_red("CONSOLE ALERTS", error_alerts)
            failures += 1
        if warnings:
            print("CONSOLE WARNINGS", file=sys.stderr)
            for line in warnings:
                print(line, file=sys.stderr)
    return failures, data
