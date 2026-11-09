"""Resolve the project root for scripts run from any working directory."""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parent.joinpath("..").resolve()