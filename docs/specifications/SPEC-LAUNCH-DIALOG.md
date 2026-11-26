# SPEC-LAUNCH-DIALOG: Launch Dialog of the Dock Icons

**Date:** 2026-11-26
**Requirements:** [REQ-LAUNCH-DIALOG](../requirements/REQ-LAUNCH-DIALOG.md)

## 1. Requirement state

States: `[built]` = code exists, no test passed; `[host]` = a host test
passed on 2026-11-26 (section 5 names the run); `[operator]` = only a
person can judge it.

The host tests run the real dialog on a display nobody sees, against
scripted commands. They do not build the map and do not start StarCraft II.
No test here clicked a dock icon.

| ID | State | Backed by |
| --- | --- | --- |
| R-DLG-1 | [host] [operator] | What the installers write: `test_install_dock_icon` `test_every_exec_line_goes_through_the_launch_dialog` (both entries, the entry and its action, no `playtest.sh` on an Exec line), `test_the_entry_opens_the_editor_through_the_launch_dialog`. Reinstalled on this machine (section 6). The click: AC-DLG-1, AC-DLG-3 |
| R-DLG-2 | [host] | `test_launch_dialog` `test_the_command_runs_in_the_root_with_the_environment_of_the_entry`: the command sees the window width and the frame generation switch of the dialog's environment, and runs in the project folder |
| R-DLG-3 | [host] [operator] | `tracker_test.js`: steps in order, a marker in the wrong source moves nothing, a missed marker closes the steps between. `markers_test.js`: each step line and each advice message is one the scripts print. `test_clean_start_closes_and_the_game_runs_on`: 8 steps, all done. How the rows look: AC-DLG-4 |
| R-DLG-4 | [host] | `tracker_test.js` `progress: never back, time left only with measured steps`. Dialog tests: fraction 1.0 after a clean start, below 1.0 after a failure; `dialog-times.json` written after a clean start |
| R-DLG-5 | [host] [operator] | `runner_test.js` `output, log file and exit code, in order` (lines from before the run are not reported). `tracker_test.js` `classify`. Dialog tests read the shown log. The colours: AC-DLG-4 |
| R-DLG-6 | [host] | `test_failed_build_stays_open_with_the_error`: the path and the saved text. `test_a_long_log_is_shown_in_time_trimmed_and_saved_whole`: 30 003 lines saved, at most 6000 shown, the last lines kept |
| R-DLG-7 | [host] | `runner_test.js`: a new target is seen once; one that ran before the start is not. `tracker_test.js`: code 0 and no target fails after 60 s |
| R-DLG-8 | [host] | Still open 4.5 s after the end: failed build, start with an error line, editor error, missing tool. `window_test.js`: still open 3 s after Cancel. `test_clean_start_closes_and_the_game_runs_on`: the dialog ends with code 0 by itself. `tracker_test.js`: warnings alone do not keep it open |
| R-DLG-9 | [host] | `test_failed_build_stays_open_with_the_error` (headline, error line with exit code, advice), `test_editor_error_in_its_log_file_is_shown`, `test_a_tool_that_is_not_there_fails_with_the_shell_message` |
| R-DLG-10 | [host] | `window_test.js`: `Copy Log`, `Retry` (second run, old log gone), `Launch Last Build` (runs `launch-built`; not offered after a launch failure) |
| R-DLG-11 | [host] | `window_test.js` `Cancel stops the build and what it started`. `runner_test.js`: the child of the command is stopped too; a command that ignores TERM is killed; also after a detach |
| R-DLG-12 | [host] | `window_test.js`: the question shows, `Keep Running` keeps the build, a later close asks again; `Stop` stops the build and the window closes |
| R-DLG-13 | [host] | `window_test.js`: `Hide` closes and the launcher runs on; a question left open is taken away at the hand-over, its `Stop` stops nothing, the dialog still closes. `test_clean_start_closes_and_the_game_runs_on`: the target runs after the dialog ended |
| R-DLG-14 | [host] [operator] | `test_a_long_log_is_shown_in_time_trimmed_and_saved_whole`: the end of 30 000 lines shows within 20 s. Whether the window answers a click during the flood: operator |
| R-DLG-15 | [host] | `test_install_dock_icon`: both installers fail before writing an entry. `test_deps`: `launch-dialog` is OK, or OPTIONAL with the reason. `make deps-check` on this machine: `OK launch-dialog gjs 18002, GTK 4.14.5, libadwaita 1.5.0` |
| R-DLG-16 | [host] | `test_launch_dialog` `test_check_loads_the_toolkit` |
| AC-DLG-1, 3, 4, 5 | [operator] | Not checked |

## 2. Facts

| ID | Fact | Source |
| --- | --- | --- |
| F1 | This machine has gjs 1.80.2, GTK 4.14.5, libadwaita 1.5.0. libadwaita 1.5 has no `Adw.Spinner`; the step rows use `Gtk.Spinner`. | `scripts/launch-dialog.sh --check` |
| F2 | `gtk4-broadwayd` gives a GTK 4 display with no screen. A window there reports visible and mapped. | `test_launch_dialog` `DialogTest` |
| F3 | The launchers send their output to a log file (`exec >>`), away from the command's pipe. The dialog reads both. | `scripts/launch-scoba.sh`, `scripts/launch-editor.sh`, `markers_test.js` |
| F4 | While an `Adw.AlertDialog` is open on a window, libadwaita takes a close of that window for the dialog. The window's `close-request` handlers do not run. This holds while the dialog goes away too. | probe 2026-11-26; `window_test.js` failed on it before the fix |
| F5 | In the agent's shell a script runs as `/proc/self/fd/N`. `$0` is not its path there. Tests name `SC2_PROJECT_ROOT`, as the entries do. | `test_launch_dialog`, `test_install_dock_icon` red runs 2026-11-26 |
| F6 | The same shell answers a script that does not exist with `BLOCKED` and code 1, not bash's 127. The missing tool case is tested with a script that exists. | red run 2026-11-26 |

## 3. Design

### 3.1 Files

| File | Holds |
| --- | --- |
| `scripts/launch-dialog.sh` | The entry point of the entries: finds the project folder and `gjs`, starts `main.js`. `--check` loads the toolkit and opens nothing |
| `scripts/launchui/main.js` | Arguments, the application, one window per start |
| `scripts/launchui/actions.js` | The three actions: command, launcher log, target, steps with their lines. Error and warning patterns. Advice per known failure |
| `scripts/launchui/tracker.js` | The state of one run. No toolkit, no clock of its own |
| `scripts/launchui/runner.js` | The command, its output, the launcher log, the target process, stopping |
| `scripts/launchui/store.js` | The state folder, the step times, the saved log |
| `scripts/launchui/view.js` | The widgets |
| `scripts/launchui/window.js` | Ties them: one queue for lines, exit and target, so their order holds |

### 3.2 Actions and steps

| Action | Command | Launcher log | Target process |
| --- | --- | --- | --- |
| `launch` | `bash scripts/playtest.sh launch` | `launcher.log` | `SC2_x64.exe` |
| `launch-built` | `bash scripts/playtest.sh launch-built` | `launcher.log` | `SC2_x64.exe` |
| `editor` | `bash scripts/launch-editor.sh` | `editor.log` | `SC2Editor_x64.exe` |

Steps of `launch`. The first step begins with the command. The others begin
with their line.

| Step | Line | Where | Before the hand-over |
| --- | --- | --- | --- |
| Prepare the build | | | yes |
| Expand the map | `expanding map` | output | yes |
| Normalize line endings | `normalizing line endings` | output | yes |
| Write the stamp and the manifest | `writing build stamp` | output | yes |
| Validate the map | `validating map` | output | yes |
| Stage the map in StarCraft II | `<time> gpu: ` | launcher log | yes |
| Write the clip metrics | `<time> stamp: ` | launcher log | yes |
| Start StarCraft II | `<time> launching ` | launcher log | no |

`launch-built` has `Check the built map` and the last three. `editor` has
`Check the map and the editor` and `Start the editor` (`<time> command: `).

The hand-over is the start of the last step, or the end of the command
with code 0.

### 3.3 The run

- The command runs under `setsid`: a session and a process group of its
  own. The group is stopped as one. The target is in it and outlives the
  dialog.
- The launcher log is read from its size at the start of the run.
- The target is looked for with `pgrep -f`, once a second, from the last
  step on. Processes that ran before the start do not count.
- The end:
  - a new target process: done;
  - a code other than 0: failed, at once;
  - code 0 and no target in 60 s: failed;
  - Cancel, or Stop in the question: cancelled.
- A clean start closes the dialog 2.5 s later.
- Stopping sends TERM to the group, and KILL 3 s later if the command still
  runs.
- A close is asked every 100 ms until the window took it (F4).

### 3.4 Files it writes

In `~/.local/state/scoba/`, or under `XDG_STATE_HOME`:

- `dialog-<action>.log`: the log of the last run of that action;
- `dialog-times.json`: seconds per step of the last clean start, per
  action. The progress bar and the time left use them.

### 3.5 Arguments of `main.js`

- `--root <folder> --action <launch|launch-built|editor>`: what the entry
  point passes.
- `--process <pattern>`: another target pattern. `--report <file>`: the
  state of the dialog as JSON, written when the run ends and when the
  window closes. Both are for the host tests.
- `--check`: print the toolkit versions.

### 3.6 Entries

`scripts/install-dock-icon.sh` and `scripts/install-editor-dock-icon.sh`
write `Exec=env <environment> bash "<root>/scripts/launch-dialog.sh"
<action>`. The environment is the one the entries had. Both run
`launch-dialog.sh --check` first and fail when it fails.

## 4. Defects the tests found

| Defect | Test that failed | Fix |
| --- | --- | --- |
| `Retry` within 3 s of `Cancel` dropped the pending KILL: a command that ignores TERM ran on | `runner_test.js` `cancel, then detach` | A detach keeps the KILL timer; the exit is recorded after a detach |
| After `Stop` in the question the window stayed, greyed out (F4) | `window_test.js` `Stop stops it and closes the window` | The close is asked until the window took it |
| A question left open past the hand-over: its `Stop` sent TERM to the started game | `window_test.js` `a question left open` | The question is taken away at the hand-over; a late answer stops nothing |

## 5. Tests

```sh
make host-test ARGS="testkit.tests.test_launch_dialog testkit.tests.test_install_dock_icon testkit.tests.deps.test_deps"
```

- `test_launch_dialog` runs `tracker_test.js` (18), `runner_test.js` (10),
  `markers_test.js` (8) and `window_test.js` (8), and seven runs of the
  whole dialog through `--report`.
- Run of 2026-11-26: 50 tests, OK. No test process was left.
- `make host-tests` was not run: it rebuilds the map first, and the build
  stops in the HD texture step (two Barracks bakes).

## 6. Not done

- The entries on this machine were reinstalled on 2026-11-26 16:11. All
  five Exec lines start `launch-dialog.sh`. No click on them was tested.
- No real build and no real launch ran through the dialog.
- Operator checks: AC-DLG-1, AC-DLG-3, AC-DLG-4, AC-DLG-5.
