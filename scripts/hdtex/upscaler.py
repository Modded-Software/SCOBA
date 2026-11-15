"""Run the arc-upscale tool on a directory of PNG planes."""

from __future__ import annotations

import glob
import hashlib
import os
import subprocess
from pathlib import Path

from project_root import project_root


class UpscaleError(RuntimeError):
    """arc-upscale is missing, failed, or wrote no output."""


def find_tool() -> Path:
    """The arc-upscale script: ARC_UPSCALE, or the checkout next to this project."""
    value = os.environ.get("ARC_UPSCALE")
    tool = Path(value) if value else project_root().parent / "upscale-on-arc" / "arc-upscale"
    if not tool.is_file():
        raise UpscaleError(f"arc-upscale not found at {tool}; set ARC_UPSCALE to its path")
    return tool.resolve()


def version() -> str:
    """A hash of the tool's code and of its locked dependencies.

    The same model gives other pixels after a change of the tool, so planes
    made by another version are redone.
    """
    root = find_tool().parent
    digest = hashlib.sha256()
    for name in ("upscale.py", "uv.lock"):
        path = root / name
        if not path.is_file():
            raise UpscaleError(f"{path} is missing; the arc-upscale checkout at {root} is not complete")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def run(
    input_dir: Path,
    output_dir: Path,
    model: str,
    wrap: bool,
    gpu: int | None = None,
    tile: int | None = None,
) -> dict[str, Path]:
    """Upscale every PNG in `input_dir`. Returns the output file per input stem.

    `wrap` makes opposite edges match, for textures that tile.
    """
    tool = find_tool()
    command = [str(tool), "run", str(input_dir), "-o", str(output_dir), "-m", model]
    if wrap:
        command.append("--tiling")
    if gpu is not None:
        command += ["-g", str(gpu)]
    if tile is not None:
        command += ["--tile", str(tile)]
    # The tool finds its project from its own path. That fails when a shell
    # wrapper runs it from a copy, so the project is named explicitly. The
    # caller's virtualenv must not leak into the tool's own environment.
    env = {key: value for key, value in os.environ.items() if key != "VIRTUAL_ENV"}
    env.setdefault("ARC_UPSCALE_ROOT", str(tool.parent))
    result = subprocess.run(command, env=env)
    if result.returncode != 0:
        raise UpscaleError(f"arc-upscale failed with exit code {result.returncode}")
    outputs = {}
    for source in sorted(input_dir.glob("*.png")):
        matches = sorted(output_dir.glob(f"{glob.escape(source.stem)}_*x.png"))
        if len(matches) != 1:
            raise UpscaleError(f"expected one upscaled file for {source.name}, found {len(matches)}")
        outputs[source.stem] = matches[0]
    return outputs
