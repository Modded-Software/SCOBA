// Files of the launch dialog (REQ-LAUNCH-DIALOG): the folder the launchers
// log to, the step times of the last good runs, and the log of this run.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const TIMES_FILE = 'dialog-times.json';
const decoder = new TextDecoder('utf-8');
const encoder = new TextEncoder();

// The same folder scripts/launch-scoba.sh and scripts/launch-editor.sh log to.
export function stateDir() {
    const base = GLib.getenv('XDG_STATE_HOME') || GLib.build_filenamev([GLib.get_home_dir(), '.local', 'state']);
    return GLib.build_filenamev([base, 'scoba']);
}

// {times, problem}. times: action id -> step id -> seconds. A file that
// cannot be read gives no times and names the problem.
export function readTimes(dir) {
    const path = GLib.build_filenamev([dir, TIMES_FILE]);
    if (!GLib.file_test(path, GLib.FileTest.EXISTS))
        return {times: {}, problem: null};
    try {
        const [, bytes] = GLib.file_get_contents(path);
        const data = JSON.parse(decoder.decode(bytes));
        if (data === null || typeof data !== 'object' || Array.isArray(data))
            throw new Error('not a JSON object');
        return {times: data, problem: null};
    } catch (error) {
        return {times: {}, problem: `cannot read ${path}: ${error.message}`};
    }
}

// The measured seconds of one action, from what readTimes gave.
export function timesOf(times, actionId) {
    const own = times[actionId];
    return own !== null && typeof own === 'object' && !Array.isArray(own) ? own : {};
}

// Throws when the file cannot be written.
export function writeTimes(dir, times, actionId, seconds) {
    const path = GLib.build_filenamev([dir, TIMES_FILE]);
    const data = {...times, [actionId]: {...timesOf(times, actionId), ...seconds}};
    GLib.file_set_contents(path, `${JSON.stringify(data, null, 2)}\n`);
    return data;
}

// The log of one run, replaced by the next run of the same action.
export class LogFile {
    // Throws when the file cannot be made.
    constructor(dir, actionId) {
        this.path = GLib.build_filenamev([dir, `dialog-${actionId}.log`]);
        this.stream = Gio.File.new_for_path(this.path).replace(null, false, Gio.FileCreateFlags.NONE, null);
    }

    // Throws when the file cannot be written.
    write(text) {
        if (this.stream !== null)
            this.stream.write_all(encoder.encode(text), null);
    }

    close() {
        if (this.stream === null)
            return;
        const stream = this.stream;
        this.stream = null;
        stream.close(null);
    }
}
