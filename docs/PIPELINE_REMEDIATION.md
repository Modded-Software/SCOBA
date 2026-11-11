# SCOBA Build Pipeline Remediation

Status: implementing  
Companion audit: `docs/PIPELINE_AUDIT.md`

## Goal

Make every launch provably run the freshly built map.

## Invariants

1. Build output is atomic.
2. XML is well-formed before staging.
3. Galaxy is compile-checked before gameplay testing.
4. Every build has a unique stamp.
5. Old game process is stopped before staging.
6. SC2 map cache is cleared before staging.
7. Staged map is byte-verified against `out/`.
8. Runtime stamp proves the game loaded the new map.
9. Logs fail on script, catalog, UI, cache, and map-load errors.
10. Gameplay tests run only after the stamp matches.

## Phase 0 - Canonical entrypoints

- [ ] R0.1 Add `scripts/build.sh`.
- [ ] R0.2 Add `scripts/validate-map.py`.
- [ ] R0.3 Add `scripts/kill-sc2.py`.
- [ ] R0.4 Document all three in `AGENTS.md` and `README.md`.
- [ ] R0.5 Remove or redirect `/tmp` build helpers.
- [ ] R0.6 Add `scripts/playtest.sh` as the single build, test, launch, and dock-icon entrypoint.
- [ ] R0.7 Make every wrapper delegate through `scripts/playtest.sh` unless `SC2_PLAYTEST_ACTIVE=1`.
- [ ] R0.8 Add `make map-build`, `make map-launch`, `make combat`, `make aim`, `make motion`, and `make controls`.
- [ ] R0.9 Make the GNOME desktop Exec call `scripts/playtest.sh launch`.

Exit:
- One build command.
- One validation command.
- One process-stop command.
- One test and launch command that always rebuilds fresh first.

## Phase 1 - Atomic build

- [ ] R1.1 Build into `out/.build-tmp`.
- [ ] R1.2 Run every transform inside the temp directory.
- [ ] R1.3 Validate the temp directory.
- [ ] R1.4 Replace `out/SCOBA256.SC2Map` only after success.
- [ ] R1.5 Add a lock file to prevent concurrent builds.

Exit:
- Interrupted build leaves the previous output intact.
- Concurrent builds fail safely.

## Phase 2 - Normalization and validation

- [ ] R2.1 Normalize output line endings.
- [ ] R2.2 Parse every XML file with ElementTree.
- [ ] R2.3 Check required files exist.
- [ ] R2.4 Check terrain dimensions are 257.
- [ ] R2.5 Check pathing grid is 256.
- [ ] R2.6 Check minimap dimensions are 256.
- [ ] R2.7 Check custom ability, behavior, and button IDs exist.
- [ ] R2.8 Check command-card references resolve.

Exit:
- Malformed XML and missing references fail before staging.

## Phase 3 - Build stamp

- [ ] R3.1 Generate a stamp from source hash and UTC time.
- [ ] R3.2 Write `BuildStamp.txt` into the output map.
- [ ] R3.3 Inject the stamp into a Galaxy constant.
- [ ] R3.4 Write the stamp to a bank at map init or first tick.
- [ ] R3.5 Verify the stamp after launch.

Exit:
- Every running map reports its build stamp.
- Stale execution is detected immediately.

## Phase 4 - Safe staging

- [ ] R4.1 Stop SC2 before staging.
- [ ] R4.2 Clear the SC2 map cache.
- [ ] R4.3 Stage a clean copy.
- [ ] R4.4 Verify staged files match `out/`.
- [ ] R4.5 Refuse to launch if verification fails.

Exit:
- No stale process, cache, or partial copy can survive.

## Phase 5 - Launch and log verification

- [ ] R5.1 Replace fixed sleep with map-load polling.
- [ ] R5.2 Check the process is alive.
- [ ] R5.3 Check the runtime stamp.
- [ ] R5.4 Fail on `ScriptError`.
- [ ] R5.5 Fail on `TextError`.
- [ ] R5.6 Fail on map-load and cache errors.
- [ ] R5.7 Ignore logs older than the launch.

Exit:
- Launch passes only when the new map is demonstrably running.

## Phase 6 - Gameplay regression testing

- [ ] R6.1 Verify default Stand.
- [ ] R6.2 Verify Stand does not chase.
- [ ] R6.3 Verify Walk chases.
- [ ] R6.4 Verify Auto OFF does not attack.
- [ ] R6.5 Verify Auto ON attacks.
- [ ] R6.6 Verify user movement wins.
- [ ] R6.7 Verify cooldown matches weapon period.

Exit:
- All invariants pass on a stamped build.

## Phase 7 - Script fixes

- [ ] R7.1 Set spore projectile factor to 1.5.
- [ ] R7.2 Scope projectile scaling to spore units or document global scope.
- [ ] R7.3 Split `SC2_NO_PROPS` and `SC2_NO_SPORES`.
- [ ] R7.4 Make terrain replacements tolerant.
- [ ] R7.5 Replace regex XML edits where practical.
- [ ] R7.6 Make `doodad_occlusion` preserve formatting or accept churn.

Exit:
- Scripts match documentation and fail loudly on unexpected input.

## Phase 8 - Metadata and tooling

- [ ] R8.1 Update `Build.txt`.
- [ ] R8.2 Update `DocumentHeader` or document why not.
- [ ] R8.3 Add a staging manifest.
- [ ] R8.4 Remove stale `out/*_dbg`, `*_hud`, `*_test` or add a clean target.
- [ ] R8.5 Decide tracking for `tools/stormex`, `sc2res`, `sc2-check-logs`.
- [ ] R8.6 Wire `run-map-test.py` into a documented test command.
- [ ] R8.7 Update README and AGENTS.

Exit:
- Docs, metadata, and tools match the actual pipeline.

## Audit-to-task map

| Audit | Task |
|---|---|
| P01 | R3.1 - R3.5, R5.3 |
| P02 | R4.2 |
| P03 | R2.1 - R2.8 |
| P04 | R3.1 - R3.4 |
| P05 | R4.1 |
| P06 | R4.3, R4.4 |
| P07 | R1.1 - R1.4 |
| P08 | R1.5 |
| P09 | R2.1 |
| P10 | R2.1 |
| P11 | R7.4 |
| P12 | R7.5 |
| P13 | R7.6 |
| P14 | R7.3 |
| P15 | R7.1 |
| P16 | R7.2 |
| P17 | R7.3 |
| P18 | R4.1 |
| P19 | R4.3 |
| P20 | R5.1 - R5.3 |
| P21 | R5.1 |
| P22 | R5.3 |
| P23 | R5.7 |
| P24 | R5.4 - R5.6 |
| P25 | R8.6 |
| P26 | R8.6 |
| P27 | R8.1, R8.2 |
| P28 | R8.4 |
| P29 | R0.1 |
| P30 | R0.1 |
| P31 | R8.5 |
| P32 | R3.4, R5.3 |
| P33 | R4.2, R8.7 |
| P34 | R8.3 |
| P35 | R3.5, R5.3 |

## Stop conditions

- Do not test gameplay until the build stamp matches.
- Do not claim a fix without a stamped run.
- Do not remove user-authored map content while fixing the pipeline.

## Definition of done

- `scripts/build.sh` succeeds twice with identical output hashes.
- Validation passes.
- Staging verification passes.
- Cache is cleared.
- Runtime stamp matches.
- Logs are clean.
- Gameplay matrix passes.
- Docs match implementation.
## Verification results

Date: 2026-11-07

Build:
- `scripts/build.sh` succeeds.
- Two consecutive builds produce identical output (`diff -r` clean).
- XML, dimensions, catalogs, script wiring, and stamp validation pass.

Runtime:
- Test map auto-starts with wait-for-key cleared.
- Runtime stamp matches `out/.last-build-stamp`.
- No recent `ScriptError`.
- Default Stand behavior count = 1.
- Auto ON behavior count = 1.
- Auto OFF behavior count = 0.
- Walk removes Stand behavior.
- Stand re-adds Stand behavior.
- 3 enemies near hero; 0 remain after auto ON.
- Hero position unchanged while standing.

Resolved root cause:
- The launch path previously defaulted to `src/SCOBA.SC2Map`.
- The SC2 map cache was not cleared.
- The runtime stamp was not written.
- Toggle handlers were bound before `gv_tPSUNIT` was set.
- `CAbilBehavior` toggles are invalid without a `BehaviorArray`.
- The chase ability needed an initial ON order to expose its OFF command.
