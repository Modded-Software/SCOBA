"""Placed trees and spores of a map's Objects file, and their blockers."""

from __future__ import annotations

import re

import numpy as np

from . import config
from .blocker import Blocker, build_blocker, disk_blocker
from .catalog import attr, tree_actor_id
from .slices import feet_slices, residual_rotation, segments_world


def tree_pattern(type_pattern: str) -> re.Pattern[str]:
    return re.compile(r'<ObjectDoodad\b[^>]*\bType="' + type_pattern + r'"[^>]*>')


def placed_scale(block: str) -> float:
    value = attr(block, "Scale")
    if value is None:
        raise ValueError(f"placed object has no Scale: {block[:120]}")
    parts = [float(v) for v in value.split(",")]
    if abs(parts[0] - parts[1]) > 1e-6:
        raise ValueError(f"placed object has uneven xy Scale: {block[:120]}")
    return parts[0]


def tree_variations(variation: int) -> list[str]:
    keys = [str(variation)]
    if variation >= config.TREE_VARIATION_COUNT:
        keys.append(str(variation % config.TREE_VARIATION_COUNT))
    return keys


def tree_outlines(data: dict, block: str) -> list[np.ndarray]:
    """Feet-height outlines of one placed tree, scaled and turned by the residual rotation."""
    variation = int(attr(block, "Variation") or 0)
    scale = placed_scale(block)
    angle = residual_rotation(float(attr(block, "Rotation") or 0.0))
    models = data["models"][config.TREE_TYPE]
    outlines = []
    for key in tree_variations(variation):
        if key not in models:
            raise ValueError(f"{config.TREE_TYPE} variation {key} has no measured model")
        for index in feet_slices(data, scale):
            outlines.append(segments_world(models[key][index], scale, angle))
    return outlines


def tree_blocker(data: dict, block: str) -> Blocker:
    return build_blocker(f"tree {attr(block, 'Id')}", tree_outlines(data, block))


def size_trees(text: str, data: dict) -> tuple[str, list[Blocker]]:
    """Objects text with each stock tree retyped to its sized actor, and the blockers."""
    blockers: list[Blocker] = []

    def repl(match: re.Match[str]) -> str:
        block = match.group(0)
        blocker = tree_blocker(data, block)
        blockers.append(blocker)
        return re.sub(r'\bType="[^"]*"', f'Type="{tree_actor_id(blocker.polygon)}"', block, count=1)

    return tree_pattern(config.TREE_TYPE).sub(repl, text), blockers


def size_spores(text: str, data: dict) -> dict[str, Blocker]:
    """One round blocker per spore type, sized from its largest placed instance."""
    scales: dict[str, float] = {}
    for match in re.finditer(r'<ObjectUnit\b[^>]*\bUnitType="([^"]+)"[^>]*>', text):
        unit = match.group(1)
        if unit in config.SPORE_UNITS:
            scales[unit] = max(scales.get(unit, 0.0), placed_scale(match.group(0)))
    blockers = {}
    for unit, scale in scales.items():
        slices = data["models"][unit]["0"]
        outlines = [segments_world(slices[i], scale, 0.0) for i in feet_slices(data, scale)]
        blockers[unit] = disk_blocker(unit, outlines)
    return blockers
