# REQ-BUILD-ENTRYPOINT

Status: binding
Scope: every build, test, staging, launch, and dock-icon path.

## Rules

| ID | Requirement |
| --- | --- |
| R-EP-1 | `scripts/playtest.sh` MUST be the single entrypoint for every build, test, launch, and dock-icon run. |
| R-EP-2 | The entrypoint MUST rebuild `out/SCOBA256.SC2Map` from `src/` before doing anything else. |
| R-EP-3 | The entrypoint MUST fail if the fresh rebuild fails. |
| R-EP-4 | The entrypoint MUST NOT reuse an existing `out/SCOBA256.SC2Map`. |
| R-EP-5 | Every test build script MUST delegate to the entrypoint unless the entrypoint set `SC2_PLAYTEST_ACTIVE=1`. |
| R-EP-6 | Every test run script MUST delegate to the entrypoint unless the entrypoint set `SC2_PLAYTEST_ACTIVE=1`. |
| R-EP-7 | Every launch script MUST delegate to the entrypoint unless the entrypoint set `SC2_PLAYTEST_ACTIVE=1`. |
| R-EP-8 | The GNOME desktop entry MUST execute the entrypoint, not `launch-scoba.sh`. |
| R-EP-9 | The project Makefile MUST expose build, launch, and per-profile test targets that call the entrypoint. |
| R-EP-10 | The entrypoint MUST support `build`, `launch`, `combat`, `aim`, `motion`, and `controls`. |
| R-EP-11 | The entrypoint MUST print the build stamp and profile map hash before launch or test. |
| R-EP-12 | The entrypoint MUST reject an unknown action or profile. |
| R-EP-13 | The entrypoint MUST be reentrant-safe and MUST NOT recurse through wrapper scripts. |
| R-EP-14 | Direct calls to low-level scripts MUST still rebuild fresh through the entrypoint. |
| R-EP-15 | Test output directories MUST use the freshly built profile map. |
| R-EP-16 | The entrypoint MUST resolve and export an absolute `UV_BIN` for child build and launch scripts. |
| R-EP-17 | The desktop entry MUST set the project root as its `Path`. |
| R-EP-18 | The dock installer MUST validate the desktop entry before reporting success. |

## Acceptance criteria

| ID | Criterion |
| --- | --- |
| AC-EP-1 | `scripts/playtest.sh build` rebuilds and validates the map. |
| AC-EP-2 | `scripts/playtest.sh launch` rebuilds before staging and launch. |
| AC-EP-3 | `scripts/playtest.sh aim` rebuilds, builds the aim map, and runs the aim profile. |
| AC-EP-4 | `scripts/build-aim-test-map.py` rebuilds before building the aim map. |
| AC-EP-5 | `scripts/run-aim-test.py` rebuilds before running the aim profile. |
| AC-EP-6 | `scripts/launch-scoba.sh` rebuilds before staging and launch. |
| AC-EP-7 | The `scoba.desktop` Exec line invokes `scripts/playtest.sh launch`. |
| AC-EP-8 | `make aim`, `make motion`, `make controls`, and `make combat` invoke the entrypoint. |
| AC-EP-9 | A stale `out/SCOBA256.SC2Map` is never used for tests or launches. |
| AC-EP-10 | The dock entry builds and launches with only an absolute `UV_BIN` and no `uv` on `PATH`. |
| AC-EP-11 | `desktop-file-validate` accepts the installed desktop entry. |