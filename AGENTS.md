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

### Screenshots

- The agent may look at screenshots for scenery only: terrain, water,
  doodads and other placed props (operator 2026-11-20).
- Not for anything else. Gameplay behavior, animation, effects, sound,
  cursor and UI stay as above.
- A screenshot never decides pass or fail. Report what was seen as "seen in
  screenshots", with the run and the file names. It is not "verified".

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
- Read `$SC2_TEST_RUNS/<profile>/<run>/summary.txt` before reporting. Quote
  the failing checks. Do not summarize a run that was not read.

### Reporting

- "Verified" means a programmatic in-game test passed in a run named in the
  report.
- "Implemented, not verified" means the code exists and no such test passed.
- "Operator check" means only a person can judge it.
- Never report a requirement as working from code reading alone.

## Build

- Every map modification lives in a deterministic script under `scripts/` or
  in `src/SCOBA.SC2Map`. Never hand-edit `$SC2_OUT`.
- The built map (`$SC2_BUILT_MAP`) is rebuilt from `src/SCOBA.SC2Map` on
  every run.

## Paths

- The repository holds source only. Its disk is encrypted; heavy writes
  there freeze the desktop. Spec: `docs/specifications/SPEC-PATHS.md`.
- `env/paths.conf` names the places. `scripts/paths.sh` derives and exports
  every path and refuses a work folder on the repository's disk.
- Run project code only through `make` or `scripts/playtest.sh`. They
  source `scripts/paths.sh`. A tool started any other way stops with an
  error. Measuring tools have make targets (`make help`).
- Python reads a path with `workpaths.path("NAME")`, when it runs. Never at
  import. Never a stand-in path, a `"/tmp"`, a repo `out`/`build`, or the prefix
  layout. `scripts/testkit/tests/test_workpaths.py` fails on each of them.
- Agent scratch files go to `$SC2_WORK/scratch`, not `/tmp`.

## Model viewer service

- The operator's viewer is a systemd user service, set up by Ansible. It
  serves port 4517. Manage it only through the `Makefile` targets in the
  repo root. Never start, stop or kill its `node` process by hand.
- `make viewer-restart`: rebuild from the checkout and restart.
- `make viewer-status`: the service and its health answer.
- `make viewer-logs` (`LINES=n`): its last log lines.
- `make viewer-provision` (`RESTART=1`): install or update the service.
- `make viewer-start` / `make viewer-stop` / `make viewer-unprovision`.
- `make viewer-serve` (`PORT=n`): a foreground server beside the service.
- The service hot reloads (`webviewer/src/tools/dev.ts`). A change under
  `webviewer/src/` or `webviewer/ref/mdx-m3-viewer/src/` rebuilds. A
  `build/server.js` with new content restarts the server. That covers a
  test run's build too. The page files are read from disk on each browser
  load. A failed build keeps the old server; see `make viewer-logs`.
- A change to `dev.ts` itself, `scripts/start.sh` or the unit needs
  `make viewer-provision RESTART=1`, then `make viewer-status`.
- Test runs use port 4518. A killed run can leave its server there; clean
  it up. Never touch the service on 4517 except through the targets.

## Commit hook exemptions

- The hooks run from `/opt/workspace-ci`. That is the CI deployment. Never
  target it or the CI repo (`WORKSPACE-VM/config`). Both are out of scope.
- SC2 exemptions live in this repo: `config/banned_words_exceptions_v5.yaml`
  (banned words), `config/file_length_limits.yaml`,
  `quality_exceptions.yaml`, and the rest listed in
  `/opt/workspace-ci/config/exemption_files.yaml`.
- These files are root-owned. The hook rejects them otherwise. The agent
  never edits them. The agent writes a script under `$SC2_WORK/scratch/` that
  calls `workspace-yaml-edit add <file> exceptions ...`, checks it with
  `--dry-run`, and the operator runs it as root.
- One entry = one rule id + one anchored exact path:
  `rule` (id from `/opt/workspace-ci/config/banned_words.yaml`, e.g.
  `bskeleton-b`), `path` (`^dir/file\.ext$`), `rationale` (why this file
  needs the word, ending "Not X code."), `owner: sc2`, `review_date`,
  `removal` (the condition that ends the need).
- Values must not contain `: `. YAML would parse them as a mapping.
- Exempt only words that are external names (upstream API, model data, HTML
  attributes). Reword the agent's own prose instead.

## Docs

- Requirements: `docs/requirements/`. Specifications: `docs/specifications/`.
- Keep them in sync with the code in the same change.
