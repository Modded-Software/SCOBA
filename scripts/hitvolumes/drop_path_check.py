#!/usr/bin/env python3
"""Build check: the drop sequence exists once, outside the intro (R-DROP-11,
SPEC-HERO-DROP 3a).

- Drop internals (zoom, fall, touchdown, pod unit, zoom constants) appear
  only in core/hero_drop.galaxy and systems/hero_drop.galaxy.
- The scene writers (cinematic mode, the input hold flag) appear only in
  systems/scene.galaxy.
- The old split path is gone: no c_INTRO_ROW_ZOOM, no gf_HeroDropStart.
- The intro (core/intro, systems/intro*) calls only gf_HeroDropBegin and
  gf_HeroDropGo, and reads no drop state or constant.
- gf_HeroDropGo is called only by the intro deploy and the reinforcement.

Comments are ignored. Input: {path relative to scripts/app: text}.
"""

from __future__ import annotations

import re
from pathlib import Path

DROP_FILES = {"core/hero_drop.galaxy", "systems/hero_drop.galaxy"}
SCENE_FILE = "systems/scene.galaxy"
INTRO_RE = re.compile(r"^(core/intro|systems/intro\w*)\.galaxy$")
GO_CALLERS = {"systems/hero_drop.galaxy", "systems/intro_flow.galaxy", "systems/spawns.galaxy"}

# Pattern, files allowed to hold it, what it is.
OWNED: tuple[tuple[str, set[str], str], ...] = (
    (r"\bgf_HeroDropZoom\w*\b", DROP_FILES, "drop zoom"),
    (r"\bgf_HeroDropFall\b", DROP_FILES, "drop fall"),
    (r"\bgf_HeroDropLand\b", DROP_FILES, "drop touchdown"),
    (r"\bc_DROP_ZOOM_\w+\b", DROP_FILES, "drop zoom constant"),
    (r"\bc_DROP_POD_UNIT\b", DROP_FILES, "drop pod unit"),
    (r"\bCinematicMode\s*\(", {SCENE_FILE}, "cinematic mode"),
    (r"\bgv_inputHeld\s*\[[^\]]*\]\s*=(?!=)", {SCENE_FILE}, "input hold write"),
)
GONE: tuple[tuple[str, str], ...] = (
    (r"\bc_INTRO_ROW_ZOOM\b", "the intro zoom row"),
    (r"\bgf_HeroDropStart\b", "the old public pod start"),
    (r"\bc_INTRO_(ZOOM|FALL)\b", "the intro zoom and fall states"),
)
INTRO_ALLOWED_DROP = {"gf_HeroDropBegin", "gf_HeroDropGo"}


def strip_comments(text: str) -> str:
    return re.sub(r"//[^\n]*", "", text)


def problems(files: dict[str, str]) -> list[str]:
    out: list[str] = []
    code = {rel: strip_comments(text) for rel, text in files.items()}
    for pattern, owners, what in OWNED:
        for rel, text in sorted(code.items()):
            if rel not in owners and re.search(pattern, text):
                out.append(f"drop path: {what} ({pattern}) outside {sorted(owners)}: {rel}")
    for pattern, what in GONE:
        for rel, text in sorted(code.items()):
            if re.search(pattern, text):
                out.append(f"drop path: {what} ({pattern}) still in {rel}")
    for rel, text in sorted(code.items()):
        if INTRO_RE.match(rel):
            for name in sorted(set(re.findall(r"\bgf_HeroDrop\w*\b", text)) - INTRO_ALLOWED_DROP):
                out.append(f"drop path: the intro calls {name} ({rel}); it may call only {sorted(INTRO_ALLOWED_DROP)}")
            for name in sorted(set(re.findall(r"\b(?:gv_drop\w*|c_DROP_\w+|gv_dropPod)\b", text))):
                out.append(f"drop path: the intro reads {name} ({rel})")
        if rel not in GO_CALLERS and re.search(r"\bgf_HeroDropGo\s*\(", text) and rel != "header.galaxy":
            out.append(f"drop path: gf_HeroDropGo called in {rel}; callers: {sorted(GO_CALLERS - DROP_FILES)}")
    for need, rel in (("gf_HeroDropGo(", "systems/intro_flow.galaxy"), ("gf_HeroDropGo(", "systems/spawns.galaxy"), ("gf_SceneEnter(", "systems/hero_drop.galaxy"), ("gf_SceneLeave(", "systems/hero_drop.galaxy")):
        if need not in code.get(rel, ""):
            out.append(f"drop path: {rel} must call {need.rstrip('(')}")
    return out


def app_files(app_dir: Path) -> dict[str, str]:
    return {p.relative_to(app_dir).as_posix(): p.read_text(encoding="utf-8", errors="replace") for p in sorted(app_dir.rglob("*.galaxy"))}


def check(map_dir: Path) -> list[str]:
    return problems(app_files(map_dir / "scripts" / "app"))
