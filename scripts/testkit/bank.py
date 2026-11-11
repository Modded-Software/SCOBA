"""Read and locate StarCraft II bank files."""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from pathlib import Path


def read_bank(path: Path) -> dict | None:
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError) as exc:
        raise RuntimeError(f"cannot parse bank {path}: {exc}") from exc
    data: dict[str, dict[str, int | bool | str]] = {}
    for section in root.findall("Section"):
        name = section.get("name", "")
        values: dict[str, int | bool | str] = {}
        for key in section.findall("Key"):
            value = key.find("Value")
            key_name = key.get("name", "")
            if value is None:
                continue
            if value.get("int") is not None:
                values[key_name] = int(value.get("int"))
            elif value.get("flag") is not None:
                values[key_name] = value.get("flag") == "1"
            elif value.get("string") is not None:
                values[key_name] = value.get("string")
            elif value.get("text") is not None:
                values[key_name] = value.get("text")
        data[name] = values
    return data


def find_latest_bank(docs: Path, bank_name: str, started_at: float) -> Path | None:
    patterns = [f"Banks/{bank_name}.SC2Bank", f"Accounts/*/*/Banks/{bank_name}.SC2Bank"]
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(p for p in docs.glob(pattern) if p.stat().st_mtime >= started_at)
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def delete_banks(docs: Path, bank_names: tuple[str, ...]) -> None:
    for name in bank_names:
        for pattern in (f"Banks/{name}.SC2Bank", f"Accounts/*/*/Banks/{name}.SC2Bank"):
            for path in docs.glob(pattern):
                path.unlink()


def wait_for_bank(docs: Path, bank_name: str, started_at: float, timeout_s: float) -> Path | None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        path = find_latest_bank(docs, bank_name, started_at)
        if path is not None:
            return path
        time.sleep(0.5)
    return None
