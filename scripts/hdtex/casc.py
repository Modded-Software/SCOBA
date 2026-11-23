"""Read game files out of the StarCraft II CASC storage with stormex."""

from __future__ import annotations

import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from sc2res import find_sc2, find_stormex


class CascError(RuntimeError):
    """stormex failed, or a file is not in the storage."""


class Casc:
    """The game storage. Paths are lower case with backslashes, as stormex lists them."""

    def __init__(self, stormex: Path | None = None, storage: Path | None = None) -> None:
        self.stormex = stormex or find_stormex()
        self.storage = storage or find_sc2()

    def _run(self, args: list[str]) -> str:
        command = [str(self.stormex), "-S", str(self.storage), *args]
        result = subprocess.run(command, text=True, capture_output=True)
        if result.returncode != 0:
            raise CascError(f"stormex failed ({result.returncode}): {result.stderr.strip() or result.stdout.strip()}")
        return result.stdout

    def find(self, suffixes: list[str]) -> list[str]:
        """Every stored path that ends in one of `suffixes`, case ignored."""
        if not suffixes:
            return []
        pattern = "(" + "|".join(re.escape(suffix.lower()) for suffix in suffixes) + ")$"
        lines = self._run(["-I", pattern, "-l"]).splitlines()
        return sorted(line.strip() for line in lines if line.strip())

    def extract(self, paths: list[str], out_dir: Path, batch: int = 0, jobs: int = 1) -> dict[str, Path]:
        """Extract exact paths below `out_dir`. Returns where each one landed.

        batch > 0: at most that many paths per stormex call (its regex has
        a state limit), `jobs` calls at a time.
        """
        if not paths:
            return {}
        out_dir.mkdir(parents=True, exist_ok=True)
        size = batch if batch > 0 else len(paths)
        groups = [paths[i:i + size] for i in range(0, len(paths), size)]

        def run(group: list[str]) -> None:
            # stormex -X extracts only one of several named files. An anchored
            # pattern with -x extracts them all.
            pattern = "^(" + "|".join(re.escape(path) for path in group) + ")$"
            self._run(["-I", pattern, "-x", "-o", str(out_dir)])

        with ThreadPoolExecutor(max_workers=max(1, jobs)) as pool:
            list(pool.map(run, groups))
        found = {}
        for path in paths:
            target = out_dir / Path(*path.split("\\"))
            if not target.is_file():
                raise CascError(f"stormex did not extract {path}")
            found[path] = target
        return found
