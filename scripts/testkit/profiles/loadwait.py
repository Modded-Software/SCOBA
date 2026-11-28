"""Loading screen wait profile (REQ-LOADING-SCREEN R-LOAD-5).

The profile map keeps the built map's wait for a key. The harness writes
its bank one game second after map init, so the bank on disk means the
game was entered. The host sends no input for HOLD_S seconds, then presses
a key, and measures when the bank appears.

HOLD_S is longer than the launch limit of every other profile (60 s,
scripts/playtest.sh): a map that enters by itself has its bank by then,
or its run fails. So no bank at HOLD_S means the game waited.
How the loading screen looks is an operator check.
"""

from __future__ import annotations

from pathlib import Path

import workpaths
from mapgen import loading_screen
from project_root import project_root

from ..map_builder import TestMapSpec
from ..runner import TestRunSpec
from .registry import PROFILE_BANKS, profile_output

ROOT = project_root()
HOLD_S = 90.0     # no input this long after the launch
RETRY_S = 10.0    # a key again, should the first one meet no window focus
ENTER_S = 30.0    # the bank must show this soon after the first key
KEY = "space"


# A label of the loading layout with a style that does not exist. The game
# names it in its Text log only if it read the layout MapInfo names (R-LOAD-8).
MARKER_STYLE = "ScobaLoadWaitNoSuchStyle"
MARKER = (
    f'        <Frame type="Label" name="ScobaLoadWaitMarker">\n'
    f'            <Style val="{MARKER_STYLE}"/>\n'
    f'        </Frame>\n'
    f'    </Frame>\n</Desc>'
)
COLUMNS = ("UI/ScobaLoading/Controls", "UI/ScobaLoading/Hero")


def patch(map_dir: Path) -> None:
    """The marker into the profile map's copy of the loading layout.

    Probe, 2026-11-27: the column strings into DocumentHeader for every
    locale, from enUS, so a label finds its key there or in GameStrings.
    """
    layout = map_dir / "Base.SC2Data" / "UI" / "Layout" / "Custom" / "ScobaLoading.SC2Layout"
    text = layout.read_text(encoding="utf-8")
    end = "    </Frame>\n</Desc>"
    if not text.rstrip().endswith(end):
        raise SystemExit(f"loadwait: {layout} does not end with its root frame")
    layout.write_text(text.rstrip()[: -len(end)] + MARKER + "\n", encoding="utf-8")
    enus = loading_screen.read_strings(map_dir, "enUS")
    header = map_dir / "DocumentHeader"
    prefix, entries = loading_screen.read_document_header(header.read_bytes())
    entries = [e for e in entries if e.key not in COLUMNS]
    entries += [loading_screen.HeaderEntry(key, locale, enus[key]) for locale in loading_screen.LOCALES for key in COLUMNS]
    header.write_bytes(loading_screen.write_document_header(prefix, entries))


def text_lines(since: float) -> list[str]:
    """The lines of the game's Text logs written since then."""
    logs = workpaths.path("SC2_DOCUMENTS") / "GameLogs"
    lines = []
    for path in sorted(logs.glob("*Text.txt")):
        if path.stat().st_mtime >= since:
            lines += [f"{path.name}: {line}" for line in path.read_text(errors="replace").splitlines() if line.strip()]
    return lines


def map_spec() -> TestMapSpec:
    return TestMapSpec(
        profile="loadwait",
        source=workpaths.path("SC2_BUILT_MAP"),
        output=profile_output("loadwait"),
        bank_names=PROFILE_BANKS["loadwait"],
        galaxy_files=(ROOT / "scripts" / "testkit" / "galaxy" / "loadwait" / "loadwait.galaxy",),
        galaxy_includes=("scripts/test/loadwait/loadwait",),
        init_calls=("gt_LoadWaitTest_Init();",),
        options={"wait_for_key": True},
        patch=patch,
    )


def on_wait(ctx, elapsed_s: float) -> None:
    """No bank yet. Nothing before HOLD_S; then the key."""
    keys = ctx.wait_keys
    if elapsed_s < HOLD_S or (keys and elapsed_s - keys[-1] < RETRY_S):
        return
    from .. import input_driver  # opens the X display: only when a key is due

    input_driver.focus()
    input_driver.key(KEY, 150)
    keys.append(elapsed_s)
    print(f"loadwait: key {KEY} at {elapsed_s:.1f} s, no bank before it", flush=True)


def on_ready(ctx, data: dict) -> None:
    return


def check(ctx, data: dict, checks) -> None:
    for error in ctx.errors:
        print(f"{error} FAIL")
        checks.failures += 1
    keys = ctx.wait_keys
    seen = ctx.bank_seen_s
    # The host's measurements, as a section of their own in the summary.
    data["lw_host"] = {
        "holdS": HOLD_S,
        "keys": len(keys),
        "firstKeyS": round(keys[0], 1) if keys else -1.0,
        "bankSeenS": round(seen, 1) if seen is not None else -1.0,
        "afterKeyS": round(seen - keys[0], 1) if keys and seen is not None else -1.0,
    }
    print("lw_host raw " + " ".join(f"{k}={v}" for k, v in data["lw_host"].items())
          + f" keyTimes={[round(k, 1) for k in keys]} gameTimeMs={checks.value('lw_game', '', 'timeMs')}")
    checks.eq("meta", "", "done", 1)
    # Negative: with no key the game was not entered in HOLD_S seconds. A
    # bank before the first key leaves keys at 0 and bankSeenS below HOLD_S.
    checks.gt("lw_host", "", "keys", 0)
    checks.gt("lw_host", "", "bankSeenS", HOLD_S)
    # The key enters the game.
    checks.between("lw_host", "", "afterKeyS", 0.0, ENTER_S)
    # The game clock had only just started when the bank was written.
    checks.between("lw_game", "", "timeMs", 500, 5000)
    # R-LOAD-8: the game read the layout MapInfo names. Raw lines first.
    lines = text_lines(ctx.run_dir.stat().st_mtime)
    for line in lines:
        print(f"lw_text raw {line}")
    marked = [line for line in lines if MARKER_STYLE in line]
    ours = [line for line in lines if "ScobaLoading" in line and MARKER_STYLE not in line]
    data["lw_layout"] = {"textLines": len(lines), "markerLines": len(marked), "otherLayoutLines": len(ours)}
    checks.gt("lw_layout", "", "markerLines", 0)
    # Negative: the layout has no other error.
    checks.eq("lw_layout", "", "otherLayoutLines", 0)


def run_spec(launch_timeout_s: float, case_timeout_s: float, run_root: Path) -> TestRunSpec:
    return TestRunSpec(
        profile="loadwait",
        map_name="SCOBA.SC2Map",
        map_source=profile_output("loadwait"),
        map_cache_name="SCOBA.SC2Map",
        bank_names=PROFILE_BANKS["loadwait"],
        ready_section="lw_start",
        ready_key="ready",
        # The wait is part of the launch here: the hold, then time to enter.
        launch_timeout_s=max(launch_timeout_s, HOLD_S + ENTER_S + RETRY_S),
        case_timeout_s=case_timeout_s,
        run_root=run_root,
        on_ready=on_ready,
        check=check,
        on_wait=on_wait,
    )
