"""Base AI lane mode (REQ-BASE-AI R-BASE-37, SPEC-BASE-AI 4.10).

core/base_ai.galaxy names the mode in one line. The validator checks the
line; the baseai test profile swaps it (SC2_BA_MODE).
"""

from __future__ import annotations

import re
from pathlib import Path

MODE_FILE = Path("scripts") / "app" / "core" / "base_ai.galaxy"
MODES = {"middle": "c_BASE_AI_MODE_MIDDLE", "3v3": "c_BASE_AI_MODE_3V3"}
MODE_VALUES = {"middle": 0, "3v3": 1}
DEFAULT = "middle"
# core/roster.galaxy gf_RosterIsMiddle: the lanes that meet at the center X.
MIDDLE_LANES = (1, 4)
LINE_RE = re.compile(r"^const int c_BASE_AI_MODE = (\w+);$", re.MULTILINE)


def lanes_with_base(mode: str) -> tuple[int, ...]:
    """The lanes that get a town hall and the AI in a mode."""
    mode_line(mode)
    return MIDDLE_LANES if mode == "middle" else tuple(range(1, 7))


def mode_line(mode: str) -> str:
    if mode not in MODES:
        raise ValueError(f"base AI mode must be one of {', '.join(MODES)}, got {mode}")
    return f"const int c_BASE_AI_MODE = {MODES[mode]};"


def check_script(text: str) -> list[str]:
    """Validator: one mode line, naming a known mode."""
    found = LINE_RE.findall(text)
    if len(found) != 1:
        return [f"base mode: expected one c_BASE_AI_MODE line, found {len(found)}"]
    if found[0] not in MODES.values():
        return [f"base mode: c_BASE_AI_MODE = {found[0]}, want one of {', '.join(MODES.values())}"]
    return []


def patch_mode(root: Path, mode: str) -> None:
    """Set the mode of a copied map (test maps only)."""
    path = root / MODE_FILE
    text = path.read_text(encoding="utf-8")
    problems = check_script(text)
    if problems:
        raise SystemExit(f"{path}: {problems[0]}")
    path.write_text(LINE_RE.sub(mode_line(mode), text), encoding="utf-8")
