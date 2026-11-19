#!/usr/bin/env python3
"""Build check: the per-player input hold (SPEC-ROSTER 3.4).

Every trigger in gf_IntroTrigger (systems/intro_ui.galaxy) must check
gf_InputHeld in its action function, directly or in the helper it returns
through; no script code may disable a trigger of that list.
"""

from __future__ import annotations

import re

GATE = "gf_InputHeld("


def _body(text: str, name: str) -> str | None:
    m = re.search(rf"^bool {name}_Func \(bool testConds, bool runActions\) \{{\n(.*?)^\}}", text, re.S | re.M)
    return None if m is None else m.group(1)


def _helper(text: str, body: str) -> str:
    """The body of a helper the function returns through (unit clicks)."""
    m = re.search(r"return (gf_\w+)\(", body)
    if m is None:
        return ""
    h = re.search(rf"^bool {m.group(1)} \([^)]*\) \{{\n(.*?)^\}}", text, re.S | re.M)
    return "" if h is None else h.group(1)


def gated(text: str) -> list[str]:
    m = re.search(r"trigger gf_IntroTrigger \(int lp_i\) \{\n(.*?)^\}", text, re.S | re.M)
    if m is None:
        return ["input gate: gf_IntroTrigger not found"]
    names = re.findall(r"return (gt_\w+)(\[1\])?;", m.group(1))
    errors = []
    for name, indexed in names:
        funcs = [f"{name}{i}" for i in range(1, 7)] if indexed else [name]
        for func in funcs:
            body = _body(text, func)
            if body is None:
                errors.append(f"input gate: {func}_Func not found")
                continue
            if GATE not in body and GATE not in _helper(text, body):
                errors.append(f"input gate: {func}_Func does not check gf_InputHeld")
        if re.search(rf"TriggerEnable\({name}(\[[^\]]*\])?, false\)", text):
            errors.append(f"input gate: {name} is disabled somewhere; use the per-player hold")
    return errors
