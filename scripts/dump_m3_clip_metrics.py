#!/usr/bin/env python3
"""Write SCOBACLIPMETRICS from M3 model sequence frame data."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from project_root import project_root

ROOT = project_root()
M3_VENDOR = ROOT / "scripts" / "vendor" / "m3addon"
sys.path.insert(0, str(M3_VENDOR))

import m3

from dump_m3_anim import animation_blocks

BANK_NAME = "SCOBACLIPMETRICS"
DEFAULT_FRAME_MS = 33


def model_type(path: Path) -> str:
    stem = path.stem
    if stem.endswith("SCOBA"):
        stem = stem[: -len("SCOBA")]
    if stem:
        return stem
    return path.parent.name


def frame_rows(path: Path) -> dict[str, dict[str, int]]:
    model = m3.loadModel(str(path))
    max_frames: dict[str, int] = {}
    for stc in model.sequenceTransformationCollections:
        largest = -1
        for block in animation_blocks(stc):
            largest = max(largest, int(block["max"]), int(block["fend"]))
        if largest < 0:
            continue
        clip_name = stc.name.replace("_full", "")
        max_frames[clip_name] = max(max_frames.get(clip_name, -1), largest)
    rows: dict[str, dict[str, int]] = {}
    for sequence in model.sequences:
        duration = int(sequence.animEndInMS) - int(sequence.animStartInMS)
        if duration <= 0:
            continue
        largest = max_frames.get(sequence.name, -1)
        if largest >= 0:
            frames = largest + 1
        else:
            frames = max(1, round(duration / DEFAULT_FRAME_MS))
        frame_ms = max(1, round(duration / frames))
        rows[sequence.name] = {
            "fms": frame_ms,
            "fc": frames,
            "dur": duration,
        }
    return rows


def map_models(map_path: Path) -> list[Path]:
    return sorted((map_path / "Assets").rglob("*.m3"))


def metrics_bank(models: list[Path]) -> ET.Element:
    bank = ET.Element("Bank", {"version": "1"})
    for path in models:
        section = ET.SubElement(bank, "Section", {"name": model_type(path)})
        for clip, values in sorted(frame_rows(path).items()):
            for suffix in ("fms", "fc", "dur"):
                key = ET.SubElement(section, "Key", {"name": f"{clip}.{suffix}"})
                ET.SubElement(key, "Value", {"int": str(values[suffix])})
    return bank


def write_bank(path: Path, models: list[Path]) -> None:
    bank = metrics_bank(models)
    ET.indent(bank, space="    ")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ET.tostring(bank, encoding="utf-8", xml_declaration=True) + b"\n")


def write_docs_bank(docs: Path, models: list[Path]) -> Path:
    path = docs / "Banks" / f"{BANK_NAME}.SC2Bank"
    write_bank(path, models)
    return path


def print_rows(models: list[Path]) -> None:
    for path in models:
        print(f"model: {path}")
        print(f"type: {model_type(path)}")
        for clip, values in sorted(frame_rows(path).items()):
            print(
                f"  {clip}:"
                f" frames={values['fc']}"
                f" frame_ms={values['fms']}"
                f" duration_ms={values['dur']}"
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, default=ROOT / "out" / "SCOBA256.SC2Map")
    parser.add_argument("--model", type=Path, action="append")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--docs", type=Path)
    args = parser.parse_args()
    models = list(args.model) if args.model else map_models(args.map)
    if not models:
        print(f"no models under {args.map}", file=sys.stderr)
        return 1
    print_rows(models)
    if args.out is not None:
        write_bank(args.out, models)
        print(f"bank: {args.out}")
    if args.docs is not None:
        path = write_docs_bank(args.docs, models)
        print(f"bank: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())