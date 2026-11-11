#!/usr/bin/env python3
"""Dump upper and lower bone classification for generated hero models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from project_root import project_root
import character_anim_assets as assets

ROOT = project_root()
sys.path.insert(0, str(ROOT / "scripts" / "vendor" / "m3addon"))

import m3


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, default=ROOT / "out" / "SCOBA256.SC2Map")
    args = parser.parse_args()
    for name, data in assets.SOURCE_MODELS.items():
        target = data[1]
        upper_roots = data[4]
        lower_roots = data[5]
        model = m3.loadModel(str(args.map / target))
        upper, lower = assets.classify_bones(model, upper_roots, lower_roots)
        print(f"model: {name}")
        for group_name, ids in (("upper", upper), ("lower", lower)):
            names = sorted(
                bone.name
                for bone in model.bones
                if assets.bone_anim_ids(bone) and set(assets.bone_anim_ids(bone)).issubset(ids)
            )
            print(f"  {group_name} ({len(names)}):")
            print("    " + " ".join(names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())