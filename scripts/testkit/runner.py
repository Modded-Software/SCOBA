"""Generic StarCraft II test runner."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, NamedTuple

from .animlog import write_animlog
from .bank import delete_banks, find_latest_bank, read_bank
from .framelog import write_framelog
from dump_m3_clip_metrics import map_models, write_docs_bank
from .checks import Checks
from .frames import FrameCollector
from .logs import latest_script_error, report_logs
from .summary import write_summary

SCRIPTS_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

ANIM_BANK = "SCOBAANIMLOG"
FRAME_BANK = "SCOBAFRAMELOG"
METRICS_BANK = "SCOBACLIPMETRICS"


def disable_bell() -> None:
    for command in (["xset", "b", "off"], ["xset", "b", "0", "0", "0"]):
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"warning: {' '.join(command)} failed: {result.stderr.strip()}", file=sys.stderr)


class TestContext:
    def __init__(self, run_dir: Path, frames: FrameCollector) -> None:
        self.run_dir = run_dir
        self.frames = frames
        self.errors: list[str] = []
        self.frame_data: dict = {}
        self.anim_data: dict = {}


class TestRunSpec(NamedTuple):
    profile: str
    map_name: str
    map_source: Path
    map_cache_name: str
    bank_names: tuple[str, ...]
    ready_section: str
    ready_key: str
    launch_timeout_s: float
    case_timeout_s: float
    run_root: Path
    on_ready: Callable
    check: Callable


def _sc2_pids() -> list[int]:
    result = subprocess.run(["pgrep", "-f", "SC2_x64.exe"], capture_output=True, text=True)
    if result.returncode not in (0, 1):
        raise RuntimeError(f"pgrep failed with exit code {result.returncode}")
    return [int(x) for x in result.stdout.split() if x.isdigit()]


def kill_sc2() -> None:
    for pid in _sc2_pids():
        try:
            os.kill(pid, signal.SIGTERM)
        except ProcessLookupError as exc:
            print(f"SC2 process {pid} already exited during SIGTERM: {exc}", file=sys.stderr)
            continue
    time.sleep(3)
    for pid in _sc2_pids():
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError as exc:
            print(f"SC2 process {pid} already exited during SIGKILL: {exc}", file=sys.stderr)
            continue


def _run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S")


def run_test(spec: TestRunSpec) -> int:
    disable_bell()
    game_prefix = Path(os.environ.get("SC2_GAME_PREFIX", str(Path.home() / "Games" / "battlenet-prefix")))
    docs = Path(
        os.environ.get(
            "SC2_DOCUMENTS",
            str(game_prefix / "pfx/drive_c/users/steamuser/Documents/StarCraft II"),
        )
    )
    cache = (
        game_prefix
        / "pfx/drive_c/ProgramData/Blizzard Entertainment/StarCraft II/Maps/Cache"
        / spec.map_cache_name
    )
    logs = docs / "GameLogs"
    run_dir = spec.run_root / spec.profile / _run_id()
    run_dir.mkdir(parents=True, exist_ok=False)
    frames = FrameCollector(run_dir)
    ctx = TestContext(run_dir=run_dir, frames=frames)

    if cache.exists():
        shutil.rmtree(cache)
    kill_sc2()
    time.sleep(0.5)
    delete_banks(docs, spec.bank_names + (ANIM_BANK, FRAME_BANK, METRICS_BANK))
    write_docs_bank(docs, map_models(spec.map_source))
    started = time.time()
    env = {**os.environ, "SC2_MAP_SOURCE": str(spec.map_source)}
    launch_log = open(run_dir / "launch.log", "ab")
    launcher = subprocess.Popen(
        ["bash", str(SCRIPTS_DIR / "launch-scoba.sh")],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=launch_log,
        stderr=launch_log,
        start_new_session=True,
    )

    launch_deadline = started + spec.launch_timeout_s
    case_deadline: float | None = None
    bank_path: Path | None = None
    data: dict | None = None
    ready_done = False
    sc2_seen = False
    missing_since: float | None = None
    while True:
        now = time.time()
        deadline = case_deadline if case_deadline is not None else launch_deadline
        if now >= deadline:
            break
        time.sleep(1)
        script_error = latest_script_error(logs, started)
        if script_error is not None:
            print(f"FAIL: script compile or runtime error: {script_error}", flush=True)
            report_logs(logs, started)
            kill_sc2()
            return 1
        pids = _sc2_pids()
        if pids:
            sc2_seen = True
            missing_since = None
        else:
            if missing_since is None:
                missing_since = now
            if sc2_seen and now - missing_since >= 5:
                break
            if not sc2_seen and launcher.poll() is not None:
                print("FAIL: launcher exited before StarCraft II started", flush=True)
                kill_sc2()
                return 1
        bank_path = find_latest_bank(docs, spec.bank_names[0], started)
        if bank_path is None:
            continue
        try:
            data = read_bank(bank_path)
        except RuntimeError as exc:
            print(f"warning: bank read failed, retrying: {exc}", file=sys.stderr)
            continue
        if data is None:
            continue
        if case_deadline is None:
            case_deadline = now + spec.case_timeout_s
        if not ready_done and data.get(spec.ready_section, {}).get(spec.ready_key) == 1:
            try:
                spec.on_ready(ctx, data)
            except Exception as exc:
                ctx.errors.append(f"input hook: {exc}")
            ready_done = True
        if data.get("meta", {}).get("done") == 1:
            break

    if bank_path is None:
        print(f"FAIL: no {spec.profile} test bank produced", flush=True)
        kill_sc2()
        return 1
    try:
        data = read_bank(bank_path)
    except RuntimeError as exc:
        print(f"warning: final bank read failed: {exc}", file=sys.stderr)
        data = None
    if data is None or data.get("meta", {}).get("done") != 1:
        print(f"FAIL: {spec.profile} test bank incomplete", flush=True)
        kill_sc2()
        return 1

    anim_path = find_latest_bank(docs, ANIM_BANK, started)
    if anim_path is not None:
        try:
            anim_data = read_bank(anim_path) or {}
        except RuntimeError as exc:
            print(f"warning: animation bank read failed: {exc}", file=sys.stderr)
            anim_data = {}
        write_animlog(run_dir, anim_data)
        ctx.anim_data = anim_data

    frame_path = find_latest_bank(docs, FRAME_BANK, started)
    if frame_path is not None:
        try:
            frame_data = read_bank(frame_path) or {}
        except RuntimeError as exc:
            print(f"warning: frame bank read failed: {exc}", file=sys.stderr)
            frame_data = {}
        ctx.frame_data = frame_data
        write_framelog(run_dir, frame_data)

    log_failures, log_data = report_logs(logs, started)
    checks = Checks(data)
    spec.check(ctx, data, checks)
    failures = checks.failures + log_failures
    artifacts = sorted(str(p.relative_to(run_dir)) for p in frames.dir.glob("*.png"))
    write_summary(
        run_dir,
        spec.profile,
        spec.map_source,
        bank_path,
        failures,
        checks.results,
        log_data,
        artifacts,
    )
    print(f"summary: {run_dir / 'summary.txt'}")
    print(f"failures: {failures}")
    kill_sc2()
    return 0 if failures == 0 else 1