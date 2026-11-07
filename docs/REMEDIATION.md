# SCOBA Command Card Remediation

Status: planning  
Companion audit: `docs/AUDIT.md`  
Goal: restore repository integrity, then replace the toggle/combat subsystem with one deterministic state model.

## Non-negotiable invariants

1. Auto-attack OFF never attacks.
2. Auto-attack ON attacks automatically within weapon range.
3. Chase Stand never leaves position to attack.
4. Chase Walk chases and attacks.
5. Player movement orders always win.
6. Button state always matches actual state.
7. Cooldown shown 1:1 with real weapon cooldown.
8. No polling loops whose only purpose is state display or state repair.
9. No hidden behavior used as a flag unless it is the only state source.
10. Rebuild is reproducible, idempotent, and reversible.

## Strategy

Use a controlled rewrite, not incremental patching.

Reason:
- Current failure is architectural, not localized.
- Every past fix added another controller.
- The audit found duplicated state, duplicated Kerrigan abilities, deleted code, and corrupted line endings.

Execution order is bottom-up. Restore repo first, then data, then script, then UI.

## Phase 0 - Freeze and safety

- [ ] R0.1 Record current `out/SCOBA256.SC2Map` hash.
- [ ] R0.2 Record current source hashes.
- [ ] R0.3 Save a full working-tree diff to `/tmp` for reference.
- [ ] R0.4 Confirm no unrelated user edits will be lost.
- [ ] R0.5 Create a git branch or stash point before edits.

Exit:
- Current state is reproducible and recoverable.

## Phase 1 - Repository integrity

Covers: A01, A02, A03, A04, A24, A25, A26, A27, A28, A29, A30, A31

- [ ] R1.1 Restore CRLF endings on all originally-CRLF files.
- [ ] R1.2 Reapply only intentional changes on top of restored endings.
- [ ] R1.3 Restore deleted end-of-MapInit `UnitClearSelection` loop.
- [ ] R1.4 Restore `UnitClearSelection` in `gf_ShowTarget` unless a documented replacement exists.
- [ ] R1.5 Decide `gt_DisableClickMove`: restore init or delete function and document why.
- [ ] R1.6 Revert `scripts/expand_map.py` anchor to explicit stable anchor, or add an idempotent guard.
- [ ] R1.7 Decide tracking policy for `tools/stormex`, `scripts/sc2res*`, `scripts/sc2-check-logs*`.
- [ ] R1.8 Document Pillow dependency or remove it.
- [ ] R1.9 Update `AGENTS.md` with command-card subsystem and audit links.
- [ ] R1.10 Unify launch path so `scripts/launch-scoba.sh` performs log checks.
- [ ] R1.11 Fix XML indentation regressions.

Exit:
- `git diff --ignore-space-at-eol` shows only intentional functional changes.
- `git diff --stat` is proportional to real change size.
- Build and launch work.

## Phase 2 - Single toggle state model

Covers: A06, A07, A08, A09, A10, A13, A14, A15

Chosen model:
- Ability toggle behavior is the only persistent state.
- Galaxy reads behavior presence only.
- No boolean mirror arrays.
- No `c_unitAbilStageAll`.
- No MapInit command-order seeding.

- [ ] R2.1 Remove duplicate Kerrigan `AbilArray` entries.
- [ ] R2.2 Decide default states and set them data-side.
- [ ] R2.3 Remove `gv_sCOBAAutoAttack` and `gv_sCOBARmbStand`.
- [ ] R2.4 Remove all four toggle command triggers.
- [ ] R2.5 Remove toggle init calls from `gt_MapInit_Func` and their prototypes.
- [ ] R2.6 Remove MapInit `SCOBARightClickToggle` order seeding.
- [ ] R2.7 Add one behavior-change trigger if event support is confirmed.
- [ ] R2.8 If no reliable behavior event exists, read behavior only at decision points.
- [ ] R2.9 Verify button On/Off rendering against behavior presence.
- [ ] R2.10 Document the exact command indices and flags used.

Exit:
- Toggle click changes behavior exactly once.
- No stage-All registration.
- Button state matches behavior presence.

## Phase 3 - Combat controller

Covers: A12, A16, A18, A19, A20, A21, A22

- [ ] R3.1 Restore `DefaultAcquireLevel` to the value required by design.
- [ ] R3.2 Decide engine acquisition vs scripted acquisition. Use one.
- [ ] R3.3 Remove 0.5s combat poll if event-driven control is viable.
- [ ] R3.4 Define explicit order priority: user order > walk chase > stand hold.
- [ ] R3.5 Clear auto target on mode change, user order, and target death.
- [ ] R3.6 Stand: issue hold once on entry, not every tick.
- [ ] R3.7 Walk: issue attack only when target is valid and in chase radius.
- [ ] R3.8 Remove duplicate manual attack path or merge it into one controller.
- [ ] R3.9 Make radii data-driven or named constants in one place.
- [ ] R3.10 Remove test Zergling spawns from production init or move to a test setup.

Exit:
- OFF never attacks.
- ON attacks in range.
- Stand never chases.
- Walk chases.
- User movement always wins.

## Phase 4 - Cooldown UI

Covers: A17

- [ ] R4.1 Remove fake ability cooldown if possible.
- [ ] R4.2 Bind slot 1 to real weapon cooldown via UI frame or supported data field.
- [ ] R4.3 Verify weapon index.
- [ ] R4.4 Verify cooldown duration matches weapon period.
- [ ] R4.5 Ensure cooldown hides or shows correctly when Auto is OFF.

Exit:
- Cooldown sweep matches actual attack timing.
- No desync after mode switches.

## Phase 5 - Selection and order cleanup

Covers: A05, A23

- [ ] R5.1 Remove 0.1s hero reselection poll.
- [ ] R5.2 Replace with selection event handling if needed.
- [ ] R5.3 Confirm selection no longer fights target ring or order mode.
- [ ] R5.4 Move Zergling test spawns to a dedicated test flag or remove.

Exit:
- Manual selection works.
- No background selection churn.

## Phase 6 - Verification

Covers: A32

Automated:
- [ ] R6.1 `python scripts/expand_map.py` succeeds twice.
- [ ] R6.2 Compare hashes after second build.
- [ ] R6.3 Launch and run log checker.
- [ ] R6.4 Add script assertions for default behavior state.
- [ ] R6.5 Add script assertions for cooldown linkage.

Manual test matrix:
- [ ] R6.6 Auto OFF, enemy nearby: no attack.
- [ ] R6.7 Auto ON, enemy nearby: attacks.
- [ ] R6.8 Auto OFF to ON: attacks without reselecting.
- [ ] R6.9 Auto ON to OFF: stops attacking.
- [ ] R6.10 Stand, enemy out of range: does not move.
- [ ] R6.11 Stand, enemy in range: attacks without moving.
- [ ] R6.12 Walk, enemy out of range: chases.
- [ ] R6.13 Walk to Stand mid-chase: stops.
- [ ] R6.14 WASD movement during Stand: moves.
- [ ] R6.15 WASD movement during Walk: moves and does not snap back.
- [ ] R6.16 Cooldown matches attack repetition.
- [ ] R6.17 Button icon matches state after every transition.
- [ ] R6.18 Reload map: defaults correct.

Exit:
- All checks pass.
- No new script errors.
- No new log alerts.

## Audit-to-task map

| Audit | Task |
|---|---|
| A01 | R1.1, R1.2 |
| A02 | R1.3 |
| A03 | R1.4 |
| A04 | R1.5 |
| A05 | R5.1, R5.2, R5.3 |
| A06 | R2.1, R2.7, R2.8 |
| A07 | R2.3, R2.8 |
| A08 | R2.4 |
| A09 | R2.5 |
| A10 | R2.6 |
| A11 | R3.2, R3.4 |
| A12 | R3.1 |
| A13 | R2.1 |
| A14 | R2.9 |
| A15 | R2.9 |
| A16 | R3.3 |
| A17 | R4.1, R4.2, R4.3, R4.4 |
| A18 | R3.6 |
| A19 | R3.7 |
| A20 | R3.8 |
| A21 | R3.5 |
| A22 | R3.9 |
| A23 | R3.10, R5.4 |
| A24 | R1.6 |
| A25 | R1.7 |
| A26 | R1.7 |
| A27 | R1.7, R1.10 |
| A28 | R1.8 |
| A29 | R1.9 |
| A30 | R1.10 |
| A31 | R1.11 |
| A32 | R6.1 - R6.18 |

## Stop conditions

Pause and ask before:

- Deleting or reverting user-authored content outside this feature.
- Removing custom abilities if the user wants to keep the current data approach.
- Deleting test Zergling spawns if they are wanted for gameplay.
- Committing or pushing anything.

## Definition of done

- Repository diffs are minimal and readable.
- One state model.
- One combat controller.
- Real cooldown.
- Manual test matrix passes.
- Build is idempotent.
- Docs match implementation.
## Verified fixes

Date: 2026-11-07

- Toggle handlers now bind after `gv_tPSUNIT` is set.
- `CAbilBehavior` toggles keep their `BehaviorArray`.
- Behavior presence is the only toggle state.
- Duplicate Kerrigan ability entries removed.
- Default Stand is applied at MapInit.
- Auto ON adds and attacks; Auto OFF removes and stops.
- Walk removes Stand; Stand restores Stand.
- Clean test: 3 enemies near hero, 0 remain after Auto ON.
- Hero position unchanged during Stand.
- Runtime stamp and log checks pass.
