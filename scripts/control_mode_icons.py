#!/usr/bin/env python3
"""Generate control mode command-card icons."""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MARKER = ".control_mode_icons"
ICON_DIR = Path("Assets") / "Textures"
ICONS = {
    "SCOBAModeRPG.dds": ("RPG", (20, 62, 116), (114, 208, 255)),
    "SCOBAModeActions.dds": ("ACT", (124, 40, 24), (255, 184, 96)),
}


def draw_icon(label: str, background: tuple[int, int, int], accent: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGBA", (64, 64), background + (255,))
    draw = ImageDraw.Draw(image)
    draw.rectangle((1, 1, 62, 62), outline=accent + (255,), width=3)
    draw.rectangle((6, 6, 57, 57), outline=accent + (128,), width=1)
    if label == "RPG":
        draw.line((12, 48, 20, 38, 28, 48), fill=accent + (255,), width=4)
        draw.line((36, 48, 44, 38, 52, 48), fill=accent + (255,), width=4)
        draw.ellipse((26, 18, 38, 30), outline=accent + (255,), width=3)
    else:
        draw.ellipse((18, 14, 46, 42), outline=accent + (255,), width=3)
        draw.line((32, 10, 32, 18), fill=accent + (255,), width=3)
        draw.line((32, 38, 32, 46), fill=accent + (255,), width=3)
        draw.line((14, 28, 22, 28), fill=accent + (255,), width=3)
        draw.line((42, 28, 50, 28), fill=accent + (255,), width=3)
        draw.ellipse((29, 25, 35, 31), fill=accent + (255,))
    font = ImageFont.load_default()
    left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
    draw.text((32 - (right - left) / 2, 49 - top), label, fill=(255, 255, 255, 255), font=font)
    return image


def generate(root: Path, force: bool) -> None:
    marker = root / MARKER
    if marker.exists() and not force:
        return
    out_dir = root / ICON_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, (label, background, accent) in ICONS.items():
        draw_icon(label, background, accent).save(out_dir / name, format="DDS")
    marker.write_text("1\n")


def revert(root: Path) -> None:
    for name in ICONS:
        (root / ICON_DIR / name).unlink(missing_ok=True)
    (root / MARKER).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, required=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--revert", action="store_true")
    args = parser.parse_args()
    root = args.map.resolve()
    if args.revert:
        revert(root)
        return 0
    generate(root, args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())