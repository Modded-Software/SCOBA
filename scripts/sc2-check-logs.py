import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import workpaths
from testkit.logs import texture_warning_lines

MAX_AGE = float(os.environ.get("SC2_LOG_MAX_AGE", "300"))
BANK_SINCE = float(os.environ.get("SC2_BANK_SINCE", "0"))
LOG_SINCE = float(os.environ.get("SC2_LOG_SINCE", "0"))


def expected_stamp() -> str:
    expected = os.environ.get("SC2_EXPECT_STAMP", "")
    if not expected:
        stamp_file = workpaths.path("SC2_BUILD_STAMP")
        if stamp_file.is_file():
            expected = stamp_file.read_text(encoding="utf-8").strip()
    return expected


def recent_logs(log_dir: Path) -> list[Path]:
    now = time.time()
    candidates = []
    for path in log_dir.glob("*.txt"):
        try:
            mtime = path.stat().st_mtime
        except OSError as exc:
            sys.stderr.write(f"WARNING: cannot stat {path}: {exc}\n")
            continue
        if mtime < LOG_SINCE:
            continue
        if now - mtime <= MAX_AGE:
            candidates.append(path)
    return candidates


def findings(candidates: list[Path]) -> tuple[list[tuple[Path, str]], list[str]]:
    errors = []
    warnings = []
    for path in candidates:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            sys.stderr.write(f"WARNING: cannot read {path}: {exc}\n")
            continue
        name = path.name
        if "ScriptError" in name:
            if "Script compile error" in text or "Script load failed" in text:
                errors.append((path, text))
            elif "error" in text.lower() and "error parsing" in text.lower():
                errors.append((path, text))
        if "Alerts" in name:
            for line in text.splitlines():
                low = line.lower()
                if "scripterror" in low or "script error" in low:
                    errors.append((path, line))
                    break
        if "Graphics" in name and texture_warning_lines(text):
            errors.append((path, "\n".join(texture_warning_lines(text))))
        if "TextError" in name:
            for line in text.splitlines():
                if "TextError" in line:
                    warnings.append(f"{path.name}: {line}")
                    break
        low = text.lower()
        for marker in (
            "failed to load map",
            "unable to load map",
            "map load failed",
            "map not found",
        ):
            if marker in low:
                errors.append((path, marker))
                break
    return errors, warnings


def bank_stamp(docs: Path) -> tuple[str, Path] | None:
    patterns = ["Banks/SCOBA.SC2Bank", "Accounts/*/*/Banks/SCOBA.SC2Bank"]
    found: list[Path] = []
    for pattern in patterns:
        for path in docs.glob(pattern):
            try:
                if path.stat().st_mtime >= BANK_SINCE:
                    found.append(path)
            except OSError as exc:
                sys.stderr.write(f"WARNING: cannot stat {path}: {exc}\n")
                continue
    for path in sorted(found, key=lambda p: p.stat().st_mtime, reverse=True):
        for _ in range(3):
            try:
                root = ET.parse(path).getroot()
            except (ET.ParseError, OSError):
                time.sleep(0.2)
                continue
            for section in root.findall("Section"):
                if section.get("name") != "Debug":
                    continue
                for key in section.findall("Key"):
                    if key.get("name") != "Build":
                        continue
                    value = key.find("Value")
                    if value is not None:
                        stamp = value.get("string") or value.get("text") or value.text
                        if stamp:
                            return stamp.strip(), path
            return "", path
    return None


def main() -> int:
    require_stamp = "--require-stamp" in sys.argv
    expected = expected_stamp()
    docs = workpaths.path("SC2_DOCUMENTS")
    log_dir = docs / "GameLogs"
    if not log_dir.is_dir():
        print(f"ERROR: StarCraft II log dir not found: {log_dir}", file=sys.stderr)
        return 2
    candidates = recent_logs(log_dir)
    if not candidates:
        print("ERROR: no recent StarCraft II logs", file=sys.stderr)
        return 2
    errors, warnings = findings(candidates)
    for path, text in errors:
        print(f"ERROR: {path}")
        for line in text.splitlines():
            if line.strip():
                print(line)
        print()
    for warning in warnings:
        print(f"WARNING: {warning}")

    runtime = bank_stamp(docs)
    if runtime is None:
        message = "runtime build stamp bank not found"
        if require_stamp:
            print(f"ERROR: {message}", file=sys.stderr)
            return 1
        print(f"WARNING: {message}")
    else:
        stamp, path = runtime
        print(f"runtime stamp: {stamp or '<missing>'} ({path})")
        if expected and stamp != expected:
            print(
                f"ERROR: runtime stamp mismatch: expected {expected}, got {stamp or '<missing>'}",
                file=sys.stderr,
            )
            return 1

    if errors:
        return 1
    print("OK: no recent script errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
