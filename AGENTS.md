# Agent Guidelines

## Testing strategy

Every behavior change is proven by an in-game test before it is reported as
working. A test proves a claim only when a program can decide pass or fail.

### What the agent writes and runs

1. **Unit tests.** One Galaxy function, called directly inside the running
   game, with its result written to a bank. Example: `gf_PncAttack` with an
   out-of-range target issues no order.
2. **Integration tests.** One player-level scenario inside the running game:
   set the toggles, spawn units, issue the command, wait, record engine state.
   Example: Attack `single`, three commands, three shots, three equal damage
   steps.
3. **Host tests.** Python `unittest` for the tooling under
   `scripts/testkit/tests/`.

### What the agent must not write

- No test whose pass or fail depends on someone looking at the screen.
- No screenshot comparison as proof of gameplay behavior.
- No claim about animation, effects, sound, cursor, or UI appearance from a
  test. Those are operator checks. List them as "operator check" in the
  report and do not mark them done.

### What can be verified programmatically

Read these from Galaxy and write them to the bank:

- unit position, facing, life, owner, alive state;
- current order and its target (`UnitOrderHasAbil`, `UnitOrder`);
- behaviors and unit state flags (`UnitBehaviorCount`, `UnitTestState`);
- cooldowns and command state (`UnitGetCooldown`, `UnitCheckAbilCmdState`);
- effect and attack events, as counters;
- script state: UI target, toggles, key and mouse flags, mode;
- camera yaw, pitch, distance, target.

### How a test is built

- Harness Galaxy lives in `scripts/testkit/galaxy/`. Assertions live in
  `scripts/testkit/profiles/<profile>.py`. Register the profile in
  `scripts/testkit/profiles/registry.py`.
- The harness is injected into a copy of the built map. It never ships in
  `src/SCOBA.SC2Map`.
- Each scenario is one bank section: reset, arrange, act, wait in game time,
  snapshot. Use `gf_DbgReset`, `gf_DbgSpawnOne`, `gf_DbgSnap`.
- Reset every toggle, order, target, and position at the start of each
  scenario. Scenarios must not depend on each other.
- Assert on engine state, not on script flags alone. A flag says what the
  script intended. Life, orders, and position say what the engine did.
- Every requirement gets at least one negative case: the thing that must not
  happen is measured and asserted absent.
- Timing: assert with windows wider than one weapon period. Never assert an
  exact millisecond.
- A test that probes an unconfirmed engine assumption records the raw values
  too, so a failure shows what the engine actually did.

### How tests are run

- `scripts/playtest.sh <profile>` is the only entrypoint. It rebuilds the
  map, builds the profile map, launches the game, and checks the bank.
- `scripts/playtest.sh build` rebuilds and validates without launching.
- Tests must be fast. While iterating, run one scenario group:
  `scripts/playtest.sh combat <group>`, about one minute. Run the full suite
  once before reporting.
- A test exits when its last scenario is done. Start a run detached, then
  wait on its process. Never wait a fixed time for a run.
- Real mouse input during a run makes it invalid. The suite fails it.
- A run stops any running StarCraft II process. Check for one first. Do not
  stop a session the operator is using without asking.
- A run passes only with `failures: 0`, no `ScriptError.txt`, and a build
  stamp that matches the fresh build.
- Read `out/test-runs/<profile>/<run>/summary.txt` before reporting. Quote
  the failing checks. Do not summarize a run that was not read.

### Reporting

- "Verified" means a programmatic in-game test passed in a run named in the
  report.
- "Implemented, not verified" means the code exists and no such test passed.
- "Operator check" means only a person can judge it.
- Never report a requirement as working from code reading alone.

## Build

- Every map modification lives in a deterministic script under `scripts/` or
  in `src/SCOBA.SC2Map`. Never hand-edit `out/`.
- `out/SCOBA256.SC2Map` is rebuilt from `src/SCOBA.SC2Map` on every run.

## Docs

- Requirements: `docs/requirements/`. Specifications: `docs/specifications/`.
- Keep them in sync with the code in the same change.
