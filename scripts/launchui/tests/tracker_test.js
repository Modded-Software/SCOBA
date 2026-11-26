// Tests of actions.js and tracker.js. No process, no window.

import {ACTIONS, classify, formatSeconds, hintsFor} from '../actions.js';
import {TARGET_GRACE, Tracker} from '../tracker.js';
import {equal, ok, run, test} from './harness.js';

const TS = '2026-11-26 15:28:14 ';
const BUILD = ['expanding map', 'normalizing line endings', 'writing build stamp', 'validating map'];
const GAME = [`${TS}gpu: game pci-0000_09_00_0`, `${TS}stamp: a6bed90c74f4`, `${TS}launching SCOBA.SC2Map`];

function states(tracker) {
    return tracker.steps.map(step => step.state);
}

// A launch run fed up to the last step. Each line is one second later.
function launchToLastStep(history) {
    const tracker = new Tracker(ACTIONS['launch'], history, 0);
    let now = 0;
    for (const line of BUILD)
        tracker.feed('pipe', line, now += 1);
    for (const line of GAME)
        tracker.feed('file', line, now += 1);
    return {tracker, now};
}

test('classify: error, warning and plain lines', () => {
    equal(classify('ERROR: another build is running'), 'error', 'bash fail');
    equal(classify('2026-11-26 15:28:14 ERROR: map not found: x'), 'error', 'launcher fail');
    equal(classify('Traceback (most recent call last):'), 'error', 'traceback');
    equal(classify('FAILED (failures=3)'), 'error', 'unittest');
    equal(classify('error: Failed to spawn: `python`'), 'error', 'uv');
    equal(classify('warning: `VIRTUAL_ENV=x` does not match'), 'warning', 'uv warning');
    equal(classify('ProtonFixes[737576] WARN: Skipping fix execution.'), 'warning', 'proton');
    // Negative: wine's own channel names and words that only hold the letters.
    equal(classify('0124:err:winediag:nodrv_CreateWindow'), 'plain', 'wine err');
    equal(classify('terrors of the ERRORS table'), 'plain', 'inside a word');
    equal(classify('expanding map'), 'plain', 'marker');
});

test('launch: every step in order, done when the target shows', () => {
    const {tracker, now} = launchToLastStep({});
    equal(states(tracker), ['done', 'done', 'done', 'done', 'done', 'done', 'done', 'running'], 'before the target');
    equal(tracker.status, 'running', 'status');
    ok(tracker.wantsTarget, 'looks for the target in the last step');
    ok(!tracker.cancellable, 'the last step cannot be cancelled');
    tracker.targetSeen(now + 10);
    equal(tracker.status, 'done', 'status');
    equal(states(tracker).every(state => state === 'done'), true, 'all done');
    equal(tracker.holdOpen, false, 'a clean start closes');
    equal(tracker.progress(now + 10), {fraction: 1, remaining: 0}, 'progress');
    equal(tracker.durations().start, 10, 'the last step took 10 s');
    equal(tracker.summary().headline, 'StarCraft II started', 'headline');
});

test('negative: a marker in the wrong source does not move the steps', () => {
    const tracker = new Tracker(ACTIONS['launch'], {}, 0);
    tracker.feed('file', 'expanding map', 1);
    tracker.feed('pipe', GAME[2], 2);
    equal(tracker.index, 0, 'still the first step');
    ok(!tracker.wantsTarget, 'does not look for the target');
    tracker.targetSeen(3);
    equal(tracker.status, 'running', 'a target before the last step does not end the run');
});

test('a marker past a missed one closes the steps between', () => {
    const tracker = new Tracker(ACTIONS['launch'], {}, 0);
    equal(tracker.feed('pipe', 'validating map', 5), 'step', 'kind');
    equal(states(tracker).slice(0, 5), ['done', 'done', 'done', 'done', 'running'], 'states');
});

test('build fails: failed, kept open, error line and advice', () => {
    const tracker = new Tracker(ACTIONS['launch'], {}, 0);
    tracker.feed('pipe', 'expanding map', 1);
    equal(tracker.feed('pipe', 'ERROR: another build is running', 2), 'error', 'kind');
    tracker.childExited(1, 3);
    equal(tracker.status, 'failed', 'status');
    equal(tracker.reason, 'exit', 'reason');
    equal(states(tracker).slice(0, 3), ['done', 'failed', 'pending'], 'states');
    equal(tracker.holdOpen, true, 'kept open');
    const summary = tracker.summary();
    equal(summary.headline, 'Failed: Expand the map', 'headline');
    equal(summary.detail, 'ERROR: another build is running (exit code 1)', 'detail');
    equal(summary.hints, [
        'Another build is running. Wait for it to end, then retry.',
        'The last built map still launches: Launch Last Build.',
    ], 'hints');
    // Negative: nothing after the failure changes it.
    tracker.targetSeen(4);
    tracker.feed('pipe', 'validating map', 5);
    tracker.tick(500);
    equal(tracker.status, 'failed', 'still failed');
    equal(tracker.index, 1, 'still at the failed step');
});

test('build fails with no error word: the last line is shown', () => {
    const tracker = new Tracker(ACTIONS['launch'], {}, 0);
    tracker.feed('pipe', 'expanding map', 1);
    tracker.feed('pipe', 'hd textures: 2 baked textures of scoba cannot be packaged:', 2);
    tracker.feed('pipe', 'glow_red1.dds: coarse_rmse 1.635 against 1.5; run: scripts/hd_textures.py unbake', 2);
    tracker.feed('pipe', '', 2);
    tracker.childExited(1, 3);
    const summary = tracker.summary();
    equal(summary.detail, 'glow_red1.dds: coarse_rmse 1.635 against 1.5; run: scripts/hd_textures.py unbake (exit code 1)', 'detail');
    equal(summary.hints[0], 'HD texture bakes block the build. The log names each texture and the command that fixes it.', 'hint');
});

test('a traceback: the message line is shown, not the header', () => {
    const tracker = new Tracker(ACTIONS['launch'], {}, 0);
    tracker.feed('pipe', 'Traceback (most recent call last):', 1);
    tracker.feed('pipe', 'SystemExit: source not found: src', 1);
    tracker.childExited(1, 2);
    equal(tracker.summary().detail, 'SystemExit: source not found: src (exit code 1)', 'detail');
    equal(tracker.errorLines.length, 1, 'the header counts as the error line');
});

test('the command ends with 0 and no target shows: failed after the grace time', () => {
    const {tracker, now} = launchToLastStep({});
    tracker.childExited(0, now);
    tracker.tick(now + TARGET_GRACE - 1);
    equal(tracker.status, 'running', 'inside the grace time');
    tracker.tick(now + TARGET_GRACE);
    equal(tracker.status, 'failed', 'after the grace time');
    equal(tracker.reason, 'target-missing', 'reason');
    equal(tracker.summary().headline, 'StarCraft II did not start', 'headline');
});

test('the command ends with 0 before the last step: the target is still looked for', () => {
    const tracker = new Tracker(ACTIONS['launch-built'], {}, 0);
    tracker.childExited(0, 1);
    ok(tracker.wantsTarget, 'looks for the target');
    ok(!tracker.cancellable, 'nothing left to cancel');
    tracker.targetSeen(2);
    equal(tracker.status, 'done', 'status');
});

test('started with an error line in the log: kept open', () => {
    const {tracker, now} = launchToLastStep({});
    tracker.feed('file', `${TS}ERROR: could not configure Variables.txt`, now);
    tracker.targetSeen(now + 1);
    equal(tracker.status, 'done', 'status');
    equal(tracker.holdOpen, true, 'kept open');
    ok(tracker.summary().detail.startsWith('The log shows 1 error line: '), 'detail');
});

test('negative: warnings alone do not keep it open', () => {
    const {tracker, now} = launchToLastStep({});
    tracker.feed('file', 'ProtonFixes[1] WARN: Skipping fix execution.', now);
    tracker.targetSeen(now + 1);
    equal(tracker.warnings, 1, 'warnings');
    equal(tracker.holdOpen, false, 'closes');
});

test('negative: an error line after the start does not reopen the question', () => {
    const {tracker, now} = launchToLastStep({});
    tracker.targetSeen(now + 1);
    tracker.feed('file', 'ERROR: late line of the game', now + 2);
    equal(tracker.holdOpen, false, 'closes');
});

test('cancel: only before the last step', () => {
    const tracker = new Tracker(ACTIONS['launch'], {}, 0);
    tracker.feed('pipe', 'expanding map', 1);
    ok(tracker.cancellable, 'a build can be cancelled');
    tracker.cancel(2);
    equal(tracker.status, 'cancelled', 'status');
    equal(tracker.summary().headline, 'Cancelled: Expand the map', 'headline');
    tracker.childExited(143, 3);
    equal(tracker.status, 'cancelled', 'the exit of the stopped command does not make it a failure');
    equal(tracker.summary().hints, [], 'no advice for a cancel');
});

test('progress: never back, time left only with measured steps', () => {
    const tracker = new Tracker(ACTIONS['launch'], {}, 0);
    let before = 0;
    let now = 0;
    for (const line of BUILD) {
        for (let i = 0; i < 300; i += 1) {
            const {fraction, remaining} = tracker.progress(now += 1);
            ok(fraction >= before && fraction < 1, `fraction at ${now}`);
            equal(remaining, null, 'no measured times');
            before = fraction;
        }
        tracker.feed('pipe', line, now);
    }
    const measured = {};
    for (const step of ACTIONS['launch'].steps)
        measured[step.id] = 10;
    const known = new Tracker(ACTIONS['launch'], measured, 0);
    equal(known.progress(0).remaining, 80, 'eight steps of 10 s');
    equal(known.progress(4).remaining, 76, 'four seconds in');
    equal(known.progress(4).fraction, 0.05, 'fraction');
    // A step that runs past its time holds just below its end.
    equal(known.progress(1000).remaining, 70.5, 'held');
});

test('editor: an error in its log file fails the first step', () => {
    const tracker = new Tracker(ACTIONS['editor'], {}, 0);
    ok(!tracker.wantsTarget, 'no target before the command line');
    tracker.feed('file', `${TS}ERROR: unpacked map folder not found, run scripts/playtest.sh build: /x`, 1);
    tracker.childExited(1, 1);
    const summary = tracker.summary();
    equal(summary.headline, 'Failed: Check the map and the editor', 'headline');
    equal(summary.hints, ['There is no built map yet. Build it with the SCOBA icon first.'], 'hints');
});

test('editor: started', () => {
    const tracker = new Tracker(ACTIONS['editor'], {}, 0);
    tracker.feed('file', `${TS}command: /x/SC2Editor_x64.exe -loadfile Z:\\x`, 1);
    ok(tracker.wantsTarget, 'looks for the editor');
    tracker.targetSeen(9);
    equal(tracker.summary().headline, 'The editor started', 'headline');
});

test('hints and time format', () => {
    equal(hintsFor(['nothing known']), [], 'no advice for an unknown line');
    equal(hintsFor(['ERROR: uv not found', 'ERROR: uv not found']), ['uv is missing. Run make deps-check.'], 'once');
    equal([formatSeconds(0), formatSeconds(59.9), formatSeconds(61), formatSeconds(-3)], ['0:00', '0:59', '1:01', '0:00'], 'format');
});

test('every action: steps have markers, the process pattern does not match itself', () => {
    for (const action of Object.values(ACTIONS)) {
        equal(action.steps[0].marker, null, `${action.id}: the first step begins with the command`);
        for (const step of action.steps.slice(1))
            ok(step.marker instanceof RegExp, `${action.id} ${step.id}: marker`);
        ok(!new RegExp(action.process).test(action.process), `${action.id}: pattern`);
        equal(new Set(action.steps.map(step => step.id)).size, action.steps.length, `${action.id}: step ids differ`);
    }
});

run();
