"""Dump and summarize timestamped animation logs from test banks."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

FRAME_FIELDS = (
    "ms",
    "seq",
    "up",
    "lo",
    "uc",
    "lc",
    "hold",
    "intent",
    "fwd",
    "back",
    "left",
    "right",
    "x",
    "y",
    "facing",
    "orders",
    "ucount",
    "lcount",
    "resets",
)


def _parse_key(key: str) -> tuple[int, int, int]:
    parts = key.split("_")
    if len(parts) != 3 or not parts[0].startswith("p"):
        return 0, 0, 0
    try:
        return int(parts[0][1:]), int(parts[1]), int(parts[2])
    except ValueError:
        return 0, 0, 0


def _parse_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for token in text.split():
        name, separator, value = token.partition("=")
        if separator:
            values[name] = value
    return values


def _int(values: dict[str, str], name: str) -> int:
    try:
        return int(values.get(name, "0"))
    except ValueError:
        return 0


def _records(section: dict[str, str]) -> list[dict[str, int | str]]:
    records: list[dict[str, int | str]] = []
    for key, text in section.items():
        player, key_ms, key_seq = _parse_key(key)
        values = _parse_values(str(text))
        record: dict[str, int | str] = {
            "key": key,
            "player": player,
            "key_ms": key_ms,
            "key_seq": key_seq,
        }
        for name, value in values.items():
            if name in {"kind", "clip"}:
                record[name] = value
            else:
                try:
                    record[name] = int(value)
                except ValueError:
                    record[name] = value
        records.append(record)
    return sorted(records, key=lambda item: (int(item["player"]), int(item.get("ms", item["key_ms"])), int(item.get("seq", item["key_seq"]))))


def _write_tsv(path: Path, records: list[dict[str, int | str]], fields: tuple[str, ...]) -> None:
    lines = ["\t".join(("player",) + fields)]
    for record in records:
        lines.append("\t".join(str(record.get(name, "")) for name in ("player",) + fields))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, int | str]]) -> None:
    lines = [json.dumps(record, sort_keys=True) for record in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _summary(frames: list[dict[str, int | str]], events: list[dict[str, int | str]]) -> str:
    lines: list[str] = []
    for player in sorted({int(item["player"]) for item in frames}):
        player_frames = [item for item in frames if int(item["player"]) == player]
        player_events = [item for item in events if int(item["player"]) == player]
        if not player_frames:
            continue
        times = [int(item.get("ms", 0)) for item in player_frames]
        span_ms = max(times) - min(times)
        lower_changes = 0
        upper_changes = 0
        flaps = 0
        previous_lower = None
        previous_upper = None
        last_lower_change = None
        lower_dwell: list[int] = []
        for item in player_frames:
            lower = int(item.get("lo", 0))
            upper = int(item.get("up", 0))
            moment = int(item.get("ms", 0))
            if previous_lower is not None and lower != previous_lower:
                lower_changes += 1
                if last_lower_change is not None:
                    lower_dwell.append(moment - last_lower_change)
                last_lower_change = moment
                if lower == 1 and previous_lower != 1:
                    flaps += 1
            if previous_upper is not None and upper != previous_upper:
                upper_changes += 1
            previous_lower = lower
            previous_upper = upper
        final = player_frames[-1]
        starts = Counter(str(item.get("kind", "")) for item in player_events)
        lines.append(f"player={player}")
        lines.append(f"  frames={len(player_frames)} span_ms={span_ms} tick_hz={len(player_frames) / max(span_ms, 1) * 1000.0:.2f}")
        lines.append(f"  lower_changes={lower_changes} upper_changes={upper_changes} idle_entries={flaps}")
        if lower_dwell:
            ordered = sorted(lower_dwell)
            lines.append(f"  lower_dwell_ms min={ordered[0]} median={ordered[len(ordered) // 2]} max={ordered[-1]}")
        lines.append(f"  upper_starts={int(final.get('ucount', 0))} lower_starts={int(final.get('lcount', 0))} resets={int(final.get('resets', 0))}")
        if span_ms > 0:
            lines.append(f"  upper_starts_per_s={int(final.get('ucount', 0)) / (span_ms / 1000.0):.2f} lower_starts_per_s={int(final.get('lcount', 0)) / (span_ms / 1000.0):.2f}")
        if starts:
            lines.append(f"  events={dict(sorted(starts.items()))}")
        lines.append("")
    return "\n".join(lines)


def write_animlog(run_dir: Path, data: dict[str, dict[str, int | bool | str]]) -> None:
    frames = _records(data.get("frames", {}))
    events = _records(data.get("events", {}))
    if frames:
        _write_tsv(run_dir / "animlog.tsv", frames, FRAME_FIELDS)
        _write_jsonl(run_dir / "animlog.jsonl", frames)
    if events:
        _write_tsv(run_dir / "animevents.tsv", events, ("ms", "seq", "kind", "clip", "flags", "ustate", "lstate", "ucount", "lcount", "resets"))
        _write_jsonl(run_dir / "animevents.jsonl", events)
    if frames or events:
        (run_dir / "animreport.txt").write_text(_summary(frames, events), encoding="utf-8")