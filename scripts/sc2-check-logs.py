import os
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(os.environ.get("SC2_PROJECT_ROOT", Path(__file__).resolve().parent.parent))
DOCS = Path(
    os.environ.get(
        "SC2_DOCUMENTS",
        str(
            Path.home()
            / "Games/battlenet-prefix/pfx/drive_c/users/steamuser/Documents/StarCraft II"
        ),
    )
)
LOG_DIR = DOCS / "GameLogs"
MAX_AGE = float(os.environ.get("SC2_LOG_MAX_AGE", "300"))
BANK_SINCE = float(os.environ.get("SC2_BANK_SINCE", "0"))
REQUIRE_STAMP = "--require-stamp" in sys.argv
EXPECTED = os.environ.get("SC2_EXPECT_STAMP", "")
if not EXPECTED:
    stamp_file = ROOT / "out" / ".last-build-stamp"
    if stamp_file.is_file():
        EXPECTED = stamp_file.read_text(encoding="utf-8").strip()

if not LOG_DIR.is_dir():
    print(f"ERROR: StarCraft II log dir not found: {LOG_DIR}", file=sys.stderr)
    sys.exit(2)

now = time.time()
candidates = []
for path in LOG_DIR.glob("*.txt"):
    try:
        age = now - path.stat().st_mtime
    except OSError:
        continue
    if age <= MAX_AGE:
        candidates.append(path)

if not candidates:
    print("ERROR: no recent StarCraft II logs", file=sys.stderr)
    sys.exit(2)

errors = []
warnings = []
for path in candidates:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
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
    if "TextError" in name:
        for line in text.splitlines():
            if "TextError" in line:
                warnings.append(f"{path.name}: {line}")
                break
    low = text.lower()
    for marker in ("failed to load map", "unable to load map", "map load failed", "map not found"):
        if marker in low:
            errors.append((path, marker))
            break


def bank_stamp() -> tuple[str, Path] | None:
    patterns = ["Banks/SCOBA.SC2Bank", "Accounts/*/*/Banks/SCOBA.SC2Bank"]
    found: list[Path] = []
    for pattern in patterns:
        for path in DOCS.glob(pattern):
            try:
                if path.stat().st_mtime >= BANK_SINCE:
                    found.append(path)
            except OSError:
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


for path, text in errors:
    print(f"ERROR: {path}")
    for line in text.splitlines():
        if line.strip():
            print(line)
    print()
for warning in warnings:
    print(f"WARNING: {warning}")

runtime = bank_stamp()
if runtime is None:
    message = "runtime build stamp bank not found"
    if REQUIRE_STAMP:
        print(f"ERROR: {message}", file=sys.stderr)
        sys.exit(1)
    print(f"WARNING: {message}")
else:
    stamp, path = runtime
    print(f"runtime stamp: {stamp or '<missing>'} ({path})")
    if EXPECTED and stamp != EXPECTED:
        print(f"ERROR: runtime stamp mismatch: expected {EXPECTED}, got {stamp or '<missing>'}", file=sys.stderr)
        sys.exit(1)

if errors:
    sys.exit(1)

print("OK: no recent script errors")
sys.exit(0)