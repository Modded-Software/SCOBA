// Tests of runner.js with real processes. No window.
// Usage: gjs -m runner_test.js <empty work folder>

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import System from 'system';

import {Runner} from '../runner.js';
import {equal, ok, pattern, pids, run, sleep, stopAll, test, until} from './harness.js';

const WORK = System.programArgs[0];
// Each process a test starts carries this in its name.
const TOKEN = `scobarunner${GLib.get_monotonic_time()}`;
let serial = 0;

function name(tag) {
    serial += 1;
    return `${TOKEN}${tag}${serial}`;
}

function script(text) {
    serial += 1;
    const path = GLib.build_filenamev([WORK, `command${serial}.sh`]);
    GLib.file_set_contents(path, `#!/usr/bin/env bash\nset -euo pipefail\n${text}\n`);
    return path;
}

// A runner on one scripted command, with everything it reports kept.
function make(text, processName) {
    serial += 1;
    const seen = {events: [], exit: null, targets: 0, problems: []};
    const tailPath = GLib.build_filenamev([WORK, `tail${serial}.log`]);
    const runner = new Runner({
        argv: ['bash', script(text.replaceAll('@LOG@', tailPath))],
        cwd: WORK,
        tailPath,
        processPattern: pattern(processName),
        onLine: (source, line) => seen.events.push(`${source}:${line}`),
        onExit: code => {
            seen.events.push(`exit:${code}`);
            seen.exit = code;
        },
        onTarget: () => {
            seen.targets += 1;
        },
        onProblem: problem => seen.problems.push(problem),
    });
    return {runner, seen, tailPath};
}

test('output, log file and exit code, in order', async () => {
    const {runner, seen, tailPath} = make('echo one\necho two >&2\nexec >>"@LOG@" 2>&1\necho three\nprintf "four\\r\\nfive"\nexit 3', name('none'));
    // Negative: what the file held before the run is not reported.
    GLib.file_set_contents(tailPath, 'written before the run\n');
    runner.start();
    await until(() => seen.exit !== null, 5000, 'exit');
    equal(seen.events, ['pipe:one', 'pipe:two', 'file:three', 'file:four', 'file:five', 'exit:3'], 'events');
    equal(seen.problems, [], 'problems');
    ok(!runner.running, 'not running');
});

test('negative: no log file is no problem', async () => {
    const {runner, seen} = make('echo only', name('none'));
    runner.start();
    await until(() => seen.exit !== null, 5000, 'exit');
    equal(seen.events, ['pipe:only', 'exit:0'], 'events');
    equal(seen.problems, [], 'problems');
});

test('a new target process is seen once; cancel stops the command', async () => {
    const target = name('target');
    const {runner, seen} = make(`exec -a ${target} sleep 30`, target);
    runner.start();
    runner.setTargetPolling(true);
    await until(() => seen.targets > 0, 5000, 'target');
    await sleep(1500);
    equal(seen.targets, 1, 'reported once');
    equal(pids(target).length, 1, 'the target runs');
    runner.cancel();
    await until(() => seen.exit !== null, 5000, 'exit');
    equal(seen.exit, 143, 'ended by TERM');
    equal(pids(target), [], 'the target is gone');
});

test('negative: a target that ran before the start is not reported', async () => {
    const target = name('target');
    const old = Gio.Subprocess.new(['bash', script(`exec -a ${target} sleep 30`)], Gio.SubprocessFlags.NONE);
    await until(() => pids(target).length === 1, 5000, 'the old target');
    const {runner, seen} = make('sleep 3', target);
    runner.start();
    runner.setTargetPolling(true);
    await until(() => seen.exit !== null, 8000, 'exit');
    equal(seen.targets, 0, 'not reported');
    equal(seen.exit, 0, 'exit');
    old.force_exit();
    await until(() => pids(target).length === 0, 5000, 'cleanup');
});

test('negative: the target is not looked for until asked', async () => {
    const target = name('target');
    const {runner, seen} = make(`exec -a ${target} sleep 30`, target);
    runner.start();
    await until(() => pids(target).length === 1, 5000, 'the target');
    await sleep(1500);
    equal(seen.targets, 0, 'not reported');
    runner.cancel();
    await until(() => seen.exit !== null, 5000, 'exit');
});

test('cancel stops what the command started too', async () => {
    const child = name('child');
    const {runner, seen} = make(`(exec -a ${child} sleep 30) &\necho started\nwait`, child);
    runner.start();
    await until(() => pids(child).length === 1, 5000, 'the child');
    runner.cancel();
    await until(() => seen.exit !== null, 5000, 'exit');
    await until(() => pids(child).length === 0, 5000, 'the child is gone');
    equal(seen.events[0], 'pipe:started', 'output');
});

test('cancel: a command that ignores TERM is killed', async () => {
    const stubborn = name('stubborn');
    const {runner, seen} = make(`trap '' TERM\necho armed\nexec -a ${stubborn} sleep 30`, stubborn);
    runner.start();
    await until(() => seen.events.includes('pipe:armed'), 5000, 'armed');
    await until(() => pids(stubborn).length === 1, 5000, 'the process');
    runner.cancel();
    await until(() => seen.exit !== null, 8000, 'exit');
    equal(seen.exit, 137, 'ended by KILL');
    equal(pids(stubborn), [], 'gone');
});

test('cancel, then detach: a command that ignores TERM is still killed', async () => {
    const stubborn = name('stubborn');
    const {runner, seen} = make(`trap '' TERM\necho armed\nexec -a ${stubborn} sleep 30`, stubborn);
    runner.start();
    await until(() => seen.events.includes('pipe:armed'), 5000, 'armed');
    await until(() => pids(stubborn).length === 1, 5000, 'the process');
    runner.cancel();
    runner.detach();
    await sleep(1000);
    const alive = pids(stubborn).length;
    let killed = true;
    try {
        await until(() => pids(stubborn).length === 0, 8000, 'killed');
    } catch (error) {
        killed = false;
        stopAll(stubborn);   // a failed test leaves no process behind
    }
    equal(alive, 1, 'TERM alone does not end it');
    ok(killed, 'killed after the wait');
    equal(seen.exit, null, 'nothing reported after detach');
});

test('detach: the command runs on and nothing more is reported', async () => {
    const target = name('target');
    const {runner, seen} = make(`echo before\nexec >>"@LOG@" 2>&1\necho after\nexec -a ${target} sleep 30`, target);
    runner.start();
    await until(() => seen.events.includes('file:after'), 5000, 'the log line');
    runner.detach();
    const count = seen.events.length;
    await sleep(1200);
    equal(pids(target).length, 1, 'still runs');
    equal(seen.events.length, count, 'nothing reported');
    equal(seen.targets, 0, 'no target reported');
    stopAll(target);
    await until(() => pids(target).length === 0, 5000, 'cleanup');
});

test('negative: a command that cannot start throws', () => {
    const {runner} = make('echo never', name('none'));
    runner.options.cwd = GLib.build_filenamev([WORK, 'no-such-folder']);
    let message = '';
    try {
        runner.start();
    } catch (error) {
        message = error.message;
    }
    ok(message !== '', 'threw');
    ok(!runner.running, 'not running');
});

if (WORK === undefined || !GLib.file_test(WORK, GLib.FileTest.IS_DIR)) {
    printerr('usage: gjs -m runner_test.js <empty work folder>');
    System.exit(2);
}
run();
