// A small test harness for the launch dialog's logic. Run with `gjs -m`.
// It prints one line per test and ends with 1 when a test failed.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import System from 'system';

const tests = [];

// A `pgrep -f` pattern for a process name. The bracket form does not match
// the command line that holds the pattern.
export function pattern(processName) {
    return `${processName.slice(0, 5)}[${processName[5]}]${processName.slice(6)}`;
}

export function pids(processName) {
    const proc = Gio.Subprocess.new(['pgrep', '-f', '--', pattern(processName)], Gio.SubprocessFlags.STDOUT_PIPE);
    const [, output] = proc.communicate_utf8(null, null);
    return output.split('\n').filter(pid => pid !== '');
}

// End the processes of one test, each by its pid.
export function stopAll(processName) {
    for (const pid of pids(processName))
        Gio.Subprocess.new(['kill', '-KILL', '--', pid], Gio.SubprocessFlags.NONE).wait(null);
}

export function test(name, body) {
    tests.push({name, body});
}

export function equal(got, want, what) {
    const g = JSON.stringify(got);
    const w = JSON.stringify(want);
    if (g !== w)
        throw new Error(`${what}: got ${g}, want ${w}`);
}

export function ok(condition, what) {
    if (!condition)
        throw new Error(`${what}: not true`);
}

export function sleep(ms) {
    return new Promise(resolve => {
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
            resolve();
            return GLib.SOURCE_REMOVE;
        });
    });
}

// Wait until check() is true. Throws after limitMs.
export async function until(check, limitMs, what) {
    const end = GLib.get_monotonic_time() + limitMs * 1000;
    while (!check()) {
        if (GLib.get_monotonic_time() > end)
            throw new Error(`${what}: not within ${limitMs} ms`);
        await sleep(25);
    }
}

async function runAll() {
    let failures = 0;
    for (const {name, body} of tests) {
        try {
            await body();
            print(`ok ${name}`);
        } catch (error) {
            failures += 1;
            print(`FAIL ${name}: ${error.message}`);
        }
    }
    print(`tests: ${tests.length} failures: ${failures}`);
    return failures;
}

// Runs the tests on a main loop, then ends the process with the result.
export function run() {
    const loop = new GLib.MainLoop(null, false);
    let failures = 1;
    runAll().then(count => {
        failures = count;
        loop.quit();
    }, error => {
        print(`FAIL harness: ${error.message}`);
        loop.quit();
    });
    loop.run();
    System.exit(failures === 0 ? 0 : 1);
}
