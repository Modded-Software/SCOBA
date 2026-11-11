"""Timestamped screenshot collection and frame checks."""

from __future__ import annotations

import time
from pathlib import Path

import input_inject
from PIL import Image, ImageChops


class FrameCollector:
    def __init__(self, run_dir: Path, case: str = "frame") -> None:
        self.dir = run_dir / "frames"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.case = case
        self.index = 0
        self.captured: list[Path] = []

    def capture(self, case: str | None = None) -> Path:
        name = case or self.case
        self.index += 1
        path = self.dir / f"{name}-{self.index:04d}.png"
        if path.exists():
            raise RuntimeError(f"screenshot already exists: {path}")
        input_inject.shot(str(path))
        xwd = Path(str(path) + ".xwd")
        if xwd.exists():
            xwd.unlink()
        if not path.is_file():
            raise RuntimeError(f"screenshot was not created: {path}")
        self.captured.append(path)
        return path

    def sample(self, case: str, count: int, interval_s: float) -> list[tuple[float, Path]]:
        records: list[tuple[float, Path]] = []
        for _ in range(count):
            started = time.monotonic()
            records.append((started, self.capture(case)))
            elapsed = time.monotonic() - started
            time.sleep(max(0.0, interval_s - elapsed))
        lines = [f"{stamp:.6f}\t{path.name}" for stamp, path in records]
        (self.dir / f"{case}-timestamps.tsv").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return records

    def period_ms(self, records: list[tuple[float, Path]], box: tuple[float, float, float, float]) -> int | None:
        if len(records) < 3:
            return None
        first = records[0][1]
        baseline = self.difference(first, first, box)
        pixels = max(1, len(Image.open(first).crop(self._box(first, box)).getdata()))
        threshold = max(50, int(pixels * 0.005))
        moved = False
        for stamp, path in records[1:]:
            delta = self.difference(first, path, box)
            if delta > threshold:
                moved = True
                continue
            if moved and delta <= max(baseline, threshold):
                start = records[0][0]
                return int(round((stamp - start) * 1000.0))
        return None

    @staticmethod
    def _box(path: Path, box: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
        image = Image.open(path)
        width, height = image.size
        return (
            int(width * box[0]),
            int(height * box[1]),
            int(width * box[2]),
            int(height * box[3]),
        )

    def crop(self, path: Path, box: tuple[float, float, float, float]) -> Path:
        image = Image.open(path)
        width, height = image.size
        left = int(width * box[0])
        top = int(height * box[1])
        right = int(width * box[2])
        bottom = int(height * box[3])
        target = path.with_name(path.stem + "-crop.png")
        if target.exists():
            raise RuntimeError(f"crop already exists: {target}")
        image.crop((left, top, right, bottom)).save(target)
        return target

    @staticmethod
    def difference(first: Path, second: Path, box: tuple[float, float, float, float]) -> int:
        left_image = Image.open(first).convert("RGB")
        right_image = Image.open(second).convert("RGB")
        width, height = left_image.size
        crop = (
            int(width * box[0]),
            int(height * box[1]),
            int(width * box[2]),
            int(height * box[3]),
        )
        left_image = left_image.crop(crop)
        right_image = right_image.crop(crop)
        diff = ImageChops.difference(left_image, right_image)
        return sum(1 for pixel in diff.getdata() if pixel != (0, 0, 0))
