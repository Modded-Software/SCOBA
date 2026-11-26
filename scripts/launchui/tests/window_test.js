// Tests of the dialog's buttons: the real window and real processes, with
// each button's `clicked` sent by the test. Run on a display nobody sees
// (gtk4-broadwayd). How the dialog looks is an operator check.
//
// usage: gjs -m window_test.js <empty work folder>

import Adw from 'gi://Adw?version=1';
import Gio from 'gi://Gio';
import GLib from 'gi://GLib';
import Gtk from 'gi://Gtk?version=4.0';
import System from 'system';

import {LaunchWindow} from '../window.js';
import {equal, ok, pattern, pids, run, sleep, stopAll, test, until} from './harness.js';

const WORK = System.programArgs[0];
const TOKEN = `scobawindow${GLib.get_monotonic_time()}`;
const TS = '2026-11-26 15:28:14 ';
let serial = 0;
let application = null;

function name(tag) {
    serial += 1;
    return `${TOKEN}${tag}${serial}`;
}

// A dialog on a project folder whose playtest.sh is `text`. @ROOT@ is the folder.
function open(text, actionId, processName) {
    serial += 1;
    const root = GLib.build_filenamev([WORK, `root${serial}`]);
    GLib.mkdir_with_parents(GLib.build_filenamev([root, 'scripts']), 0o755);
    GLib.file_set_contents(GLib.build_filenamev([root, 'scripts', 'playtest.sh']),
        `#!/usr/bin/env bash\nset -euo pipefail\n${text.replaceAll('@ROOT@', root)}\n`);
    const win = new LaunchWindow(application, {root, actionId, processPattern: pattern(processName), reportPath: null});
    win.present();
    return win;
}

// Leave nothing behind: the window through its own buttons, the processes by pid.
function shut(win, ...processNames) {
    if (!win.closing && win.tracker.cancellable)
        win.view.main.emit('clicked');
    if (!win.closing)
        win.view.main.emit('clicked');
    for (const processName of processNames)
        stopAll(processName);
}

function buttons(win) {
    return {retry: win.view.retry.visible, lastBuild: win.view.lastBuild.visible, main: win.view.main.label};
}

function findButton(widget, label) {
    if (widget instanceof Gtk.Button && widget.label === label)
        return widget;
    for (let child = widget.get_first_child(); child !== null; child = child.get_next_sibling()) {
        const found = findButton(child, label);
        if (found !== null)
            return found;
    }
    return null;
}

// Click a button of the open "Stop the build?" question.
function answer(win, label) {
    const found = findButton(win.view.stopDialog, label);
    if (found === null)
        throw new Error(`the question has no ${label} button`);
    found.emit('clicked');
}

function clipboardText(win) {
    return new Promise((resolve, reject) => {
        win.view.window.get_clipboard().read_text_async(null, (clipboard, result) => {
            try {
                resolve(clipboard.read_text_finish(result));
            } catch (error) {
                reject(error);
            }
        });
    });
}

const BUILD = child => `echo "expanding map"\n(exec -a ${child} sleep 60) &\nwait`;

test('Cancel stops the build and what it started; the dialog stays, Close closes it', async () => {
    const child = name('build');
    const win = open(BUILD(child), 'launch', child);
    try {
        await until(() => win.tracker.current.id === 'expand' && pids(child).length === 1, 5000, 'the build runs');
        equal(buttons(win), {retry: false, lastBuild: false, main: 'Cancel'}, 'buttons while it builds');
        win.view.main.emit('clicked');
        await until(() => pids(child).length === 0, 5000, 'the build is stopped');
        equal(win.tracker.status, 'cancelled', 'status');
        equal(win.view.status.label, 'Cancelled: Expand the map', 'headline');
        equal(buttons(win), {retry: true, lastBuild: false, main: 'Close'}, 'buttons after');
        await sleep(3000);
        equal(win.closing, false, 'negative: it does not close by itself');
        win.view.main.emit('clicked');
        equal(win.closing, true, 'Close closes');
    } finally {
        shut(win, child);
    }
});

test('Retry runs the action again with a new log', async () => {
    const text = 'if [ -f "@ROOT@/again" ]; then echo "second run"; exit 4; fi\n: > "@ROOT@/again"\necho "first run"\nexit 3';
    const win = open(text, 'launch-built', name('none'));
    try {
        await until(() => win.tracker.status === 'failed', 5000, 'the first run');
        equal(win.tracker.exitCode, 3, 'first exit code');
        equal(buttons(win), {retry: true, lastBuild: false, main: 'Close'}, 'buttons after the first run');
        win.view.retry.emit('clicked');
        equal(win.tracker.status, 'running', 'runs again');
        equal(buttons(win).retry, false, 'no Retry while it runs');
        await until(() => win.tracker.status === 'failed', 5000, 'the second run');
        equal(win.tracker.exitCode, 4, 'second exit code');
        const log = win.view.logText();
        ok(log.includes('second run\n'), 'the new log');
        ok(!log.includes('first run'), 'negative: the old log is gone');
        equal(win.closing, false, 'still open');
    } finally {
        shut(win);
    }
});

test('Launch Last Build is offered after a failed build step, and runs launch-built', async () => {
    const text = 'echo "arg=$1"\nif [ "$1" = "launch" ]; then\n  echo "expanding map"\n  echo "ERROR: broken" >&2\n  exit 1\nfi\nexit 5';
    const win = open(text, 'launch', name('none'));
    try {
        await until(() => win.tracker.status === 'failed', 5000, 'the build fails');
        equal(win.tracker.current.id, 'expand', 'failed step');
        equal(buttons(win), {retry: true, lastBuild: true, main: 'Close'}, 'buttons after the build');
        win.view.lastBuild.emit('clicked');
        equal(win.action.id, 'launch-built', 'the action');
        await until(() => win.tracker.status === 'failed', 5000, 'the launch ends');
        equal(win.tracker.exitCode, 5, 'exit code of launch-built');
        ok(win.view.logText().includes('$ bash scripts/playtest.sh launch-built\narg=launch-built\n'), 'the command');
        // Negative: no build failed here, so there is no build to step around.
        equal(buttons(win), {retry: true, lastBuild: false, main: 'Close'}, 'buttons after the launch');
    } finally {
        shut(win);
    }
});

test('closing during a build asks first; Keep Running keeps it; a later close asks again', async () => {
    const child = name('build');
    const win = open(BUILD(child), 'launch', child);
    try {
        await until(() => win.tracker.current.id === 'expand' && pids(child).length === 1, 5000, 'the build runs');
        win.view.window.close();
        ok(win.view.stopDialog !== null, 'the question shows');
        equal(win.view.stopDialog.heading, 'Stop the build?', 'heading');
        equal(win.closing, false, 'negative: not closed without an answer');
        answer(win, 'Keep Running');
        equal(win.view.stopDialog, null, 'the question is answered');
        await sleep(1000);
        equal([win.tracker.status, win.closing, pids(child).length], ['running', false, 1], 'kept running');
        // The question takes a close for itself while it goes away: close until asked.
        await until(() => {
            win.view.window.close();
            return win.view.stopDialog !== null;
        }, 8000, 'the question shows again');
        equal([win.tracker.status, win.closing, pids(child).length], ['running', false, 1], 'still running');
        answer(win, 'Keep Running');
    } finally {
        shut(win, child);
    }
});

test('closing during a build: Stop stops it and closes the window', async () => {
    const child = name('build');
    const win = open(BUILD(child), 'launch', child);
    try {
        await until(() => win.tracker.current.id === 'expand' && pids(child).length === 1, 5000, 'the build runs');
        win.view.window.close();
        ok(win.view.stopDialog !== null, 'the question shows');
        answer(win, 'Stop');
        equal(win.tracker.status, 'cancelled', 'stopped');
        await until(() => pids(child).length === 0, 5000, 'the build is gone');
        // The window closes although the question is still going away.
        await until(() => win.closing, 8000, 'closed after the stop');
    } finally {
        shut(win, child);
    }
});

test('a question left open: it goes with the build, its Stop stops nothing, the dialog still closes', async () => {
    const target = name('target');
    const text = 'echo "expanding map"\nsleep 2\necho "normalizing line endings"\necho "writing build stamp"\necho "validating map"\n' +
        `exec >>"$XDG_STATE_HOME/scoba/launcher.log" 2>&1\necho "${TS}gpu: game x"\necho "${TS}stamp: y"\n` +
        `echo "${TS}launching SCOBA.SC2Map"\nexec -a ${target} sleep 60`;
    const win = open(text, 'launch', target);
    try {
        await until(() => win.tracker.current.id === 'expand', 5000, 'the build runs');
        win.view.window.close();
        const question = win.view.stopDialog;
        ok(question !== null, 'the question shows');
        await until(() => win.tracker.status === 'done', 10000, 'the game starts');
        equal(win.view.stopDialog, null, 'the question is taken away');
        findButton(question, 'Stop').emit('clicked');
        await sleep(500);
        equal([win.tracker.status, pids(target).length], ['done', 1], 'negative: a late Stop does not stop the game');
        await until(() => win.closing, 8000, 'closes after the clean start');
        equal(pids(target).length, 1, 'the game runs on');
    } finally {
        shut(win, target);
    }
});

test('after the hand-over the button is Hide: it closes the dialog, the start goes on', async () => {
    const worker = name('launcher');
    const text = `exec >>"$XDG_STATE_HOME/scoba/launcher.log" 2>&1\necho "${TS}gpu: game x"\necho "${TS}stamp: y"\n` +
        `echo "${TS}launching SCOBA.SC2Map"\nexec -a ${worker} sleep 60`;
    // The target never shows: the run stays in its last step.
    const win = open(text, 'launch-built', name('target'));
    try {
        await until(() => win.tracker.current.id === 'start' && pids(worker).length === 1, 5000, 'the last step');
        equal(win.tracker.cancellable, false, 'not cancellable');
        equal(buttons(win), {retry: false, lastBuild: false, main: 'Hide'}, 'buttons');
        win.view.main.emit('clicked');
        equal(win.closing, true, 'closed with no question');
        equal(win.view.stopDialog, null, 'no question');
        await sleep(1000);
        equal(pids(worker).length, 1, 'negative: the launcher is not stopped');
    } finally {
        shut(win, worker);
    }
});

test('Copy Log puts the shown log on the clipboard', async () => {
    const win = open('echo "one line"\necho "ERROR: another" >&2\nexit 1', 'launch-built', name('none'));
    try {
        await until(() => win.tracker.status === 'failed', 5000, 'the run');
        win.view.copy.emit('clicked');
        const text = await clipboardText(win);
        equal(text, win.view.logText(), 'the clipboard');
        ok(text.includes('$ bash scripts/playtest.sh launch-built\none line\nERROR: another\n'), 'the lines');
    } finally {
        shut(win);
    }
});

if (WORK === undefined || !GLib.file_test(WORK, GLib.FileTest.IS_DIR)) {
    printerr('usage: gjs -m window_test.js <empty work folder>');
    System.exit(2);
}
GLib.setenv('XDG_STATE_HOME', GLib.build_filenamev([WORK, 'state']), true);
application = new Adw.Application({application_id: 'org.scoba.LauncherTest', flags: Gio.ApplicationFlags.NON_UNIQUE});
application.connect('activate', () => {
    application.hold();
    run();
});
application.run([System.programInvocationName]);
