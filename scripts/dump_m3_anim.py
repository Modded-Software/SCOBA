#!/usr/bin/env python3
"""Dump model animation groups, clips, and sequence timing."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from project_root import project_root

ROOT = project_root()
M3_VENDOR = ROOT / "scripts" / "vendor" / "m3addon"
sys.path.insert(0, str(M3_VENDOR))

import m3

DEFAULT_MODELS = (
    Path("Assets") / "Units" / "Terran" / "Tosh" / "ToshSCOBA.m3",
    Path("Assets") / "Units" / "Zerg" / "Kerrigan" / "KerriganSCOBA.m3",
)
JsonValue = int | float | str | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


def animation_blocks(stc) -> list[dict[str, int]]:
    rows: list[dict[str, int]] = []
    block_sets = (
        ("sdev", stc.sdev),
        ("sd2v", stc.sd2v),
        ("sd3v", stc.sd3v),
        ("sd4q", stc.sd4q),
        ("sdcc", stc.sdcc),
        ("sdr3", stc.sdr3),
        ("sds6", stc.sds6),
        ("sdu6", stc.sdu6),
        ("sdu3", stc.sdu3),
        ("sdfg", stc.sdfg),
        ("sdmb", stc.sdmb),
    )
    for name, blocks in block_sets:
        if not blocks:
            continue
        for block in blocks:
            frames = [int(value) for value in block.frames]
            if not frames:
                continue
            rows.append(
                {
                    "kind": name,
                    "frames": len(frames),
                    "min": min(frames),
                    "max": max(frames),
                    "fend": int(block.fend),
                    "keys": len(block.keys),
                }
            )
    return rows


def sequence_rows(model) -> dict[str, dict[str, JsonValue]]:
    rows: dict[str, dict[str, JsonValue]] = {}
    for sequence in model.sequences:
        rows[sequence.name] = {
            "start_ms": int(sequence.animStartInMS),
            "end_ms": int(sequence.animEndInMS),
            "duration_ms": int(sequence.animEndInMS) - int(sequence.animStartInMS),
            "speed": float(sequence.movementSpeed),
            "frequency": int(sequence.frequency),
            "flags": int(sequence.flags),
        }
    return rows


def model_rows(path: Path) -> dict[str, JsonValue]:
    model = m3.loadModel(str(path))
    sequences = sequence_rows(model)
    name_counts = Counter(stc.name for stc in model.sequenceTransformationCollections)
    groups: list[dict[str, JsonValue]] = []
    for group in model.sequenceTransformationGroups:
        clips: list[dict[str, JsonValue]] = []
        for index in group.stcIndices:
            stc = model.sequenceTransformationCollections[index]
            sts = model.sts[stc.stsIndex]
            sequence = sequences.get(stc.name, {})
            clips.append(
                {
                    "index": index,
                    "name": stc.name,
                    "priority": int(stc.priority),
                    "anim_ids": len(stc.animIds),
                    "sts_index": int(stc.stsIndex),
                    "sts_ids": len(sts.animIds),
                    "start_ms": sequence.get("start_ms"),
                    "end_ms": sequence.get("end_ms"),
                    "duration_ms": sequence.get("duration_ms"),
                    "speed": sequence.get("speed"),
                    "frequency": sequence.get("frequency"),
                    "flags": sequence.get("flags"),
                    "blocks": animation_blocks(stc),
                }
            )
        groups.append({"name": group.name, "clips": clips})
    duplicates = {name: count for name, count in name_counts.items() if count > 1}
    return {
        "model": str(path),
        "groups": groups,
        "sequences": sequences,
        "duplicates": duplicates,
    }


def print_text(rows: dict[str, JsonValue]) -> None:
    print(f"model: {rows['model']}")
    duplicates = rows["duplicates"]
    if duplicates:
        print(f"duplicate_clips: {duplicates}")
    for group in rows["groups"]:
        print(f"group: {group['name']}")
        for clip in group["clips"]:
            print(
                "  clip:"
                f" index={clip['index']}"
                f" name={clip['name']}"
                f" priority={clip['priority']}"
                f" anim_ids={clip['anim_ids']}"
                f" sts={clip['sts_index']}"
                f" sts_ids={clip['sts_ids']}"
                f" start={clip['start_ms']}"
                f" end={clip['end_ms']}"
                f" duration={clip['duration_ms']}"
                f" speed={clip['speed']}"
                f" frequency={clip['frequency']}"
                f" flags={clip['flags']}"
                f" blocks={clip['blocks']}"
            )
    print("sequences:")
    for name, sequence in sorted(rows["sequences"].items()):
        print(
            f"  {name}:"
            f" start={sequence['start_ms']}"
            f" end={sequence['end_ms']}"
            f" duration={sequence['duration_ms']}"
            f" speed={sequence['speed']}"
            f" frequency={sequence['frequency']}"
            f" flags={sequence['flags']}"
        )
    print("")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, default=ROOT / "out" / "SCOBA256.SC2Map")
    parser.add_argument("--model", type=Path, action="append")
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()

    models = tuple(args.model) if args.model else tuple(args.map / path for path in DEFAULT_MODELS)
    rows = [model_rows(path) for path in models]
    for item in rows:
        print_text(item)
    if args.json is not None:
        args.json.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())