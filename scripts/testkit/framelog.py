"""Dump and analyze timestamped character frame probe data."""

from __future__ import annotations

import json
import sys
from collections import Counter
from math import hypot
from pathlib import Path

FRAME_FIELDS = (
    "ms",
    "seq",
    "tick",
    "type",
    "up",
    "lo",
    "uc",
    "lc",
    "dir",
    "uclip",
    "lclip",
    "uq",
    "lq",
    "ulen",
    "urem",
    "uplayed",
    "uframe",
    "uframes",
    "ufms",
    "llen",
    "lrem",
    "lplayed",
    "lframe",
    "lframes",
    "lfms",
    "lfid",
    "lplay",
    "lqms",
    "x",
    "y",
    "xf",
    "yf",
    "z",
    "facing",
    "speed",
    "orders",
    "yaw",
    "pitch",
    "dist",
    "aim",
    "action",
    "alt",
    "hold",
    "resets",
    "fwd",
    "mt",
    "mtd",
    "mob",
"a0",
    "a1",
    "a2",
    "a3",
    "a4",
    "a5",
)

EVENT_FIELDS = ("ms", "seq", "kind", "clip", "flags", "up", "lo")

SLIDE_DISTANCE = 5
SLIDE_ATTACHMENT_DELTA = 1.0
SPIKE_DISTANCE = 120.0
TELEPORT_DISTANCE = 50.0
GAP_MS = 500
CHURN_PER_S = 8.0
ATTACHMENT_LIMIT = 6


def _parse_key(key: str) -> tuple[int, int, int]:
    parts = key.split("_")
    if not parts or not parts[0].startswith("p"):
        return 0, 0, 0
    try:
        player = int(parts[0][1:])
        if len(parts) == 2:
            return player, 0, int(parts[1])
        if len(parts) == 3:
            return player, int(parts[1]), int(parts[2])
    except ValueError:
        return 0, 0, 0
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


def _point(value: str) -> tuple[float, float, float] | None:
    parts = value.split(",")
    if len(parts) != 3:
        return None
    try:
        return float(parts[0]), float(parts[1]), float(parts[2])
    except ValueError as exc:
        print(f"warning: invalid point {value!r}: {exc}", file=sys.stderr)
        return None


def _distance(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    return hypot(first[0] - second[0], first[1] - second[1])


def parse_section(section: dict[str, str]) -> list[dict[str, int | str]]:
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
            if name in {"type", "uclip", "lclip", "kind", "clip", "uq", "lq"}:
                record[name] = value
            elif name.startswith("a") and name[1:].isdigit():
                record[name] = value
            else:
                try:
                    record[name] = int(value)
                except ValueError:
                    record[name] = value
        records.append(record)
    return records


def frame_order(item: dict[str, int | str]) -> tuple[int, int, int]:
    return (
        int(item["player"]),
        int(item.get("seq", item["key_seq"])),
        int(item.get("ms", item["key_ms"])),
    )


def event_order(item: dict[str, int | str]) -> tuple[int, int, int]:
    return (
        int(item["player"]),
        int(item.get("ms", item["key_ms"])),
        int(item.get("seq", item["key_seq"])),
    )


def _write_tsv(path: Path, records: list[dict[str, int | str]], fields: tuple[str, ...]) -> None:
    lines = ["\t".join(("player",) + fields)]
    for record in records:
        lines.append("\t".join(str(record.get(name, "")) for name in ("player",) + fields))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict[str, int | str]]) -> None:
    lines = [json.dumps(record, sort_keys=True) for record in records]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _center_index(config: dict[str, str]) -> int | None:
    for index in range(ATTACHMENT_LIMIT):
        name = str(config.get(f"a{index}", ""))
        if "Center" in name:
            return index
    return None


def _attachment_points(record: dict[str, int | str]) -> list[tuple[int, tuple[float, float, float]]]:
    points: list[tuple[int, tuple[float, float, float]]] = []
    for index in range(ATTACHMENT_LIMIT):
        value = record.get(f"a{index}")
        if not isinstance(value, str):
            continue
        point = _point(value)
        if point is not None:
            points.append((index, point))
    return points


def _frame_anomalies(row: dict[str, int | str], previous: dict[str, int | str], counts: Counter[str]) -> None:
    for slot in ("u", "l"):
        frames = int(row.get(f"{slot}frames", 0))
        frame = int(row.get(f"{slot}frame", -1))
        old = int(previous.get(f"{slot}frame", -1))
        if frames <= 0 or frame < 0 or old < 0:
            continue
        if frame == old:
            continue
        if frame > old:
            counts["frame_advance"] += 1
        else:
            counts["frame_wrap"] += 1


def analyze(
    records: list[dict[str, int | str]],
    events: list[dict[str, int | str]],
    config: dict[str, str],
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    center = _center_index(config)
    per_player: dict[int, list[dict[str, int | str]]] = {}
    for record in records:
        per_player.setdefault(int(record["player"]), []).append(record)
    for player, rows in per_player.items():
        rows.sort(key=frame_order)
        previous: dict[str, int | str] | None = None
        for row in rows:
            if previous is not None:
                delta_ms = int(row.get("ms", 0)) - int(previous.get("ms", 0))
                if delta_ms < 0:
                    counts["clock"] += 1
                if delta_ms > GAP_MS:
                    counts["gap"] += 1
                move = hypot(
                    int(row.get("x", 0)) - int(previous.get("x", 0)),
                    int(row.get("y", 0)) - int(previous.get("y", 0)),
                )
                if move > TELEPORT_DISTANCE:
                    counts["teleport"] += 1
                previous_points = dict(_attachment_points(previous))
                current_points = dict(_attachment_points(row))
                shared = sorted(set(previous_points) & set(current_points))
                if shared:
                    attachment_delta = max(
                        _distance(previous_points[index], current_points[index]) for index in shared
                    )
                    if move >= SLIDE_DISTANCE and attachment_delta < SLIDE_ATTACHMENT_DELTA:
                        counts["slide"] += 1
                if center is not None and center in current_points:
                    for index, point in current_points.items():
                        if index != center and _distance(current_points[center], point) > SPIKE_DISTANCE:
                            counts["spike"] += 1
                            break
                _frame_anomalies(row, previous, counts)
                for slot in ("uq", "lq"):
                    if row.get(slot) == "fail" and previous.get(slot) != "fail":
                        counts["metrics"] += 1
            previous = row
        first_ms = int(rows[0].get("ms", 0)) if rows else 0
        last_ms = int(rows[-1].get("ms", 0)) if rows else 0
        span_s = max((last_ms - first_ms) / 1000.0, 0.001)
        player_events = [item for item in events if int(item["player"]) == player]
        if len(player_events) / span_s > CHURN_PER_S:
            counts["churn"] += 1
    return dict(sorted(counts.items()))


def _summary(
    records: list[dict[str, int | str]],
    events: list[dict[str, int | str]],
    config: dict[str, str],
    anomalies: dict[str, int],
) -> str:
    lines: list[str] = []
    lines.append(f"hero={config.get('hero', '')}")
    lines.append(f"model={config.get('model', '')}")
    lines.append(f"upper={config.get('upper', '')}")
    lines.append(f"lower={config.get('lower', '')}")
    for index in range(ATTACHMENT_LIMIT):
        value = config.get(f"a{index}", "")
        if value:
            lines.append(f"a{index}={value}")
    for player in sorted({int(item["player"]) for item in records}):
        rows = [item for item in records if int(item["player"]) == player]
        if not rows:
            continue
        rows.sort(key=frame_order)
        first_ms = int(rows[0].get("ms", 0))
        last_ms = int(rows[-1].get("ms", 0))
        span_ms = last_ms - first_ms
        lines.append(f"player={player}")
        lines.append(f"  rows={len(rows)} span_ms={span_ms}")
        if span_ms > 0:
            lines.append(f"  sample_hz={len(rows) / (span_ms / 1000.0):.2f}")
        lines.append(f"  upper_states={dict(sorted(Counter(int(item.get('up', 0)) for item in rows).items()))}")
        lines.append(f"  lower_states={dict(sorted(Counter(int(item.get('lo', 0)) for item in rows).items()))}")
        lines.append(f"  upper_query={dict(sorted(Counter(str(item.get('uq', '')) for item in rows).items()))}")
        lines.append(f"  lower_query={dict(sorted(Counter(str(item.get('lq', '')) for item in rows).items()))}")
        
        lines.append(f"  events={dict(sorted(Counter(str(item.get('kind', '')) for item in events if int(item['player']) == player).items()))}")
        first = int(rows[0].get("lframe", -1))
        last = int(rows[-1].get("lframe", -1))
        lines.append(f"  lower_frame_first={first} lower_frame_last={last}")
        
    lines.append(f"anomalies={anomalies}")
    return "\n".join(lines) + "\n"


def write_framelog(run_dir: Path, data: dict) -> None:
    frames = parse_section(data.get("frames", {}))
    events = parse_section(data.get("events", {}))
    frames.sort(key=frame_order)
    events.sort(key=event_order)
    config = {str(key): str(value) for key, value in data.get("config", {}).items()}
    anomalies = analyze(frames, events, config)
    if frames:
        _write_tsv(run_dir / "framelog.tsv", frames, FRAME_FIELDS)
        _write_jsonl(run_dir / "framelog.jsonl", frames)
    if events:
        _write_tsv(run_dir / "frameevents.tsv", events, EVENT_FIELDS)
        _write_jsonl(run_dir / "frameevents.jsonl", events)
    if frames or events:
        (run_dir / "frameprobe.txt").write_text(
            _summary(frames, events, config, anomalies),
            encoding="utf-8",
        )