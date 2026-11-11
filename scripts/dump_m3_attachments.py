#!/usr/bin/env python3
"""Dump attachment points for generated hero models."""

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
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    for name, data in assets.SOURCE_MODELS.items():
        target = data[1]
        model = m3.loadModel(str(args.map / target))
        if args.json:
            rows = [
                {
                    "attachment": attachment.name,
                    "bone": model.bones[attachment.boneIndex].name,
                }
                for attachment in model.attachmentPoints
            ]
            print(f'"{name}": {rows}')
            continue
        print(f"model: {name}")
        for attachment in model.attachmentPoints:
            bone = model.bones[attachment.boneIndex].name
            print(f"  {attachment.name}\t{bone}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())