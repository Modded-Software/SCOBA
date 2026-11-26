# REQ-LAUNCH-DIALOG: Launch Dialog of the Dock Icons

**Date:** 2026-11-26
**Status:** Asked by the operator on 2026-11-26. In the agent's words, not a
quote: a click on a SCOBA dock icon shows a GNOME dialog with the progress
and a visible log of the build and the launch. It stays open when errors
show. It is helpful and it answers at once.

The specification lists the state of each requirement.

## 1. Scope

In scope:

- the dock entries `SCOBA`, `SCOBA FG`, their `Instant Launch (no build)`
  action, and `SCOBA Editor`;
- the dialog they open: steps, progress, log, errors, buttons.

Out of scope:

- what the build and the launchers do;
- `scripts/playtest.sh` started from a terminal: no dialog there;
- test runs.

## 2. Definitions

- **Entry**: one desktop entry or one of its actions.
- **Command**: what an entry ran before this change: `scripts/playtest.sh
  launch`, `scripts/playtest.sh launch-built` or `scripts/launch-editor.sh`.
- **Launcher log**: the file a launcher appends to, `launcher.log` or
  `editor.log` in `~/.local/state/scoba/`.
- **Target**: the process the run is for: StarCraft II or its editor.
- **Hand-over**: the moment the command is past the project's own build and
  is starting the target. From then on, stopping the command would stop the
  target.
- **Clean start**: the target started and the run showed no error line.
- **Error line**: a log line with the word `ERROR`, a Python traceback
  header, or a line that begins with `FAIL`, `FAILED` or `error:`.

## 3. Requirements

| ID | Requirement |
| --- | --- |
| R-DLG-1 | Every entry MUST start through the dialog. No entry MUST run its command with no dialog. |
| R-DLG-2 | The dialog MUST run the entry's command in the project folder, with the environment of the entry (GPU, frame generation, window size, `UV_BIN`). |
| R-DLG-3 | The dialog MUST list the steps of the run in order. Each step MUST show its state (pending, running, done, failed, cancelled) and its time. A step begins when its script prints the step's line. A line the scripts no longer print MUST fail the host tests. |
| R-DLG-4 | The dialog MUST show one progress bar for the run. It MUST NOT go back. It MUST be full only when the target started. A time left MUST show only when every step has a time from an earlier good run. |
| R-DLG-5 | The dialog MUST show every line of the run, in order: the output of the command, then the lines the launcher appends to its log. Lines the launcher log held before the run MUST NOT show. Error lines and warning lines MUST be marked. |
| R-DLG-6 | The whole log of a run MUST be saved to `~/.local/state/scoba/dialog-<action>.log`. The dialog MUST show the path. The shown log MAY keep only its last 5000 lines. |
| R-DLG-7 | The run is done when a new target process shows. A command that ends with code 0 and no new target process within 60 s MUST count as failed. |
| R-DLG-8 | The dialog MUST stay open after a failed run, after a cancelled run, and after a start whose log shows an error line. It MUST close by itself only after a clean start. |
| R-DLG-9 | After a failed run the dialog MUST name the failed step, the last error line and the exit code. For a failure the scripts are known to print, it MUST add what to do. |
| R-DLG-10 | `Copy Log` MUST put the shown log on the clipboard. `Retry` MUST show after a failed or cancelled run and run the action again with a new log. `Launch Last Build` MUST show after a failed build step and launch the last built map. |
| R-DLG-11 | Before the hand-over, `Cancel` MUST stop the command and every process it started. A command that ignores the request MUST be killed 3 s later, also when `Retry` is pressed in between. |
| R-DLG-12 | Closing the window before the hand-over MUST ask first. `Keep Running` MUST change nothing. `Stop` MUST stop the command and close the window. |
| R-DLG-13 | After the hand-over the dialog MUST NOT stop the command. The button reads `Hide`. Closing the window MUST leave the start running. A `Stop` answered after the hand-over MUST stop nothing. The target MUST outlive the dialog. |
| R-DLG-14 | The dialog MUST stay usable under a flood of output. A run of 30 000 lines MUST show its end within 20 s. |
| R-DLG-15 | The installers MUST fail before they write an entry when the dialog cannot load. `make deps-check` MUST report the dialog's toolkit. |
| R-DLG-16 | The dialog MUST use what GNOME ships: `gjs`, GTK 4 and libadwaita. |

## 4. Acceptance

| ID | Check |
| --- | --- |
| AC-DLG-1 | Click `SCOBA`: the dialog shows, the steps advance, the log fills, the game starts, the dialog closes. Operator check. |
| AC-DLG-2 | Make the build fail: the dialog stays, names the step and the error, and offers `Retry` and `Launch Last Build`. |
| AC-DLG-3 | `Instant Launch (no build)` and `SCOBA Editor` show the dialog too. Operator check. |
| AC-DLG-4 | The dialog looks like a GNOME window and reads well: layout, colours, the spinner, the banner. Operator check. |
| AC-DLG-5 | The dialog window sits under the icon that was clicked in the dock. Operator check. |

## 5. Open points

| ID | Point |
| --- | --- |
| O-DLG-1 | The build prints five step lines. A step is as fine as its script's lines: `Expand the map` is one long step. |
| O-DLG-2 | The time left comes from the last good run. The first run shows none. |
| O-DLG-3 | The error lines of Wine (`err:` channels) are not counted: they show on every good start. |

Implementation lives in
[SPEC-LAUNCH-DIALOG](../specifications/SPEC-LAUNCH-DIALOG.md).
