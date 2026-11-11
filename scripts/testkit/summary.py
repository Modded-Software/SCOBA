"""Write run summaries."""

from __future__ import annotations

import json
from pathlib import Path


def write_summary(
    run_dir: Path,
    profile: str,
    map_path: Path,
    bank_path: Path | None,
    failures: int,
    results: list[dict[str, int | str | float | bool | None]],
    log_data: dict,
    artifacts: list[str],
) -> None:
    payload = {
        "profile": profile,
        "run_id": run_dir.name,
        "map": str(map_path),
        "bank": str(bank_path) if bank_path is not None else None,
        "exit_code": 0 if failures == 0 else 1,
        "failures": failures,
        "checks": results,
        "script_errors": [str(p) for p in log_data.get("script_errors", [])],
        "error_folders": [str(p) for p in log_data.get("error_dirs", [])],
        "alerts": list(log_data.get("alerts", [])),
        "artifacts": artifacts,
    }
    (run_dir / "summary.json").write_text(json.dumps(payload, indent=2) + "\n")
    lines = [
        f"profile: {profile}",
        f"run: {run_dir}",
        f"map: {map_path}",
        f"bank: {bank_path}",
        f"failures: {failures}",
    ]
    for item in results:
        lines.append(
            f"{item['section']} {item['tag']} {item['key']}: {item['got']} / {item['want']} {item['status']}"
        )
    (run_dir / "summary.txt").write_text("\n".join(lines) + "\n")
