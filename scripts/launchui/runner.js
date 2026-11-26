// Runs one command for the launch dialog (REQ-LAUNCH-DIALOG): its output,
// the log file its launcher appends to, and the target process. Nothing
// here blocks the main loop for long, and nothing here draws.

import Gio from 'gi://Gio';
import GLib from 'gi://GLib';

const TAIL_MS = 150;
const TARGET_MS = 1000;
const DRAIN_MS = 500;    // after the command ends, wait this long for its last output
const KILL_MS = 3000;    // after TERM, wait this long, then KILL
const TAIL_CHUNK = 262144;
const NEWLINE = 10;

const decoder = new TextDecoder('utf-8');

export class Runner {
    // argv: the command, run in cwd, in a session of its own.
    // tailPath: the log file to follow from its size at the start.
    // processPattern: `pgrep -f` pattern of the target process.
    // onLine(source, text), onExit(code), onTarget(), onProblem(text).
    constructor(options) {
        this.options = options;
        this.proc = null;
        this.exitCode = null;
        this.exitReported = false;
        this.pipeOpen = false;
        this.tailOffset = 0;
        this.tailRest = new Uint8Array(0);
        this.tailProblem = false;
        this.baseline = new Set();
        this.targetBusy = false;
        this.targetFound = false;
        this.detached = false;
        this.timers = {tail: 0, target: 0, drain: 0, kill: 0};
    }

    // Throws when the command cannot be started.
    start() {
        this.tailOffset = this._tailSize();
        this.baseline = this._pidsNow();
        const launcher = new Gio.SubprocessLauncher({
            flags: Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_MERGE,
        });
        launcher.set_cwd(this.options.cwd);
        // setsid: a session and a process group of its own. The group can be
        // stopped as one, and the game outlives the dialog.
        this.proc = launcher.spawnv(['setsid', ...this.options.argv]);
        this.pipeOpen = true;
        this.stream = new Gio.DataInputStream({base_stream: this.proc.get_stdout_pipe(), close_base_stream: true});
        this._readNext();
        this.proc.wait_async(null, (proc, result) => this._onWait(proc, result));
        this.timers.tail = GLib.timeout_add(GLib.PRIORITY_DEFAULT, TAIL_MS, () => {
            this._readTail();
            return GLib.SOURCE_CONTINUE;
        });
    }

    get running() {
        return this.proc !== null && this.exitCode === null;
    }

    _readNext() {
        this.stream.read_line_async(GLib.PRIORITY_DEFAULT, null, (stream, result) => {
            let bytes = null;
            try {
                [bytes] = stream.read_line_finish(result);
            } catch (error) {
                if (!this.detached)
                    this.options.onProblem(`cannot read the command output: ${error.message}`);
            }
            if (this.detached)
                return;
            if (bytes === null) {
                this.pipeOpen = false;
                this._reportExit();
                return;
            }
            this.options.onLine('pipe', decoder.decode(bytes).replace(/\r$/, ''));
            this._readNext();
        });
    }

    _onWait(proc, result) {
        try {
            proc.wait_finish(result);
        } catch (error) {
            if (!this.detached)
                this.options.onProblem(`cannot wait for the command: ${error.message}`);
        }
        // Known after a detach too: a pending KILL must not go to an ended command.
        this.exitCode = proc.get_if_exited() ? proc.get_exit_status() : 128 + proc.get_term_sig();
        if (this.detached) {
            this._clear('kill');
            return;
        }
        this.timers.drain = GLib.timeout_add(GLib.PRIORITY_DEFAULT, DRAIN_MS, () => {
            this.timers.drain = 0;
            this.pipeOpen = false;
            this._reportExit();
            return GLib.SOURCE_REMOVE;
        });
        this._reportExit();
    }

    // The exit is reported after the last line of the pipe and of the log file.
    _reportExit() {
        if (this.exitCode === null || this.pipeOpen || this.exitReported)
            return;
        this.exitReported = true;
        this._clear('drain');
        this._clear('kill');
        this._readTail();
        if (this.tailRest.length > 0) {
            // A last line with no line end is still a line.
            const rest = this.tailRest;
            this.tailRest = new Uint8Array(0);
            this.options.onLine('file', decoder.decode(rest).replace(/\r$/, ''));
        }
        this.options.onExit(this.exitCode);
    }

    _tailSize() {
        const file = Gio.File.new_for_path(this.options.tailPath);
        try {
            return file.query_info('standard::size', Gio.FileQueryInfoFlags.NONE, null).get_size();
        } catch (error) {
            if (error.matches(Gio.IOErrorEnum, Gio.IOErrorEnum.NOT_FOUND))
                return 0;
            throw error;
        }
    }

    _readTail() {
        let bytes;
        try {
            const size = this._tailSize();
            if (size < this.tailOffset)
                this.tailOffset = 0;   // the file was replaced
            if (size === this.tailOffset)
                return;
            const stream = Gio.File.new_for_path(this.options.tailPath).read(null);
            stream.seek(this.tailOffset, GLib.SeekType.SET, null);
            bytes = stream.read_bytes(Math.min(size - this.tailOffset, TAIL_CHUNK), null).toArray();
            stream.close(null);
        } catch (error) {
            if (!this.tailProblem)
                this.options.onProblem(`cannot read ${this.options.tailPath}: ${error.message}`);
            this.tailProblem = true;
            return;
        }
        this.tailOffset += bytes.length;
        const data = new Uint8Array(this.tailRest.length + bytes.length);
        data.set(this.tailRest, 0);
        data.set(bytes, this.tailRest.length);
        const cut = data.lastIndexOf(NEWLINE);
        if (cut < 0) {
            this.tailRest = data;
            return;
        }
        this.tailRest = data.slice(cut + 1);
        for (const line of decoder.decode(data.subarray(0, cut)).split('\n'))
            this.options.onLine('file', line.replace(/\r$/, ''));
    }

    _pidsOf(output) {
        return new Set(output.split('\n').filter(pid => pid !== ''));
    }

    // pgrep ends with 1 when nothing matches; above 1 it failed.
    _pidsNow() {
        const proc = Gio.Subprocess.new(['pgrep', '-f', '--', this.options.processPattern], Gio.SubprocessFlags.STDOUT_PIPE);
        const [, output] = proc.communicate_utf8(null, null);
        if (proc.get_exit_status() > 1)
            throw new Error(`pgrep ended with ${proc.get_exit_status()}`);
        return this._pidsOf(output);
    }

    // Look for a target process that was not there at the start.
    setTargetPolling(on) {
        if (!on || this.targetFound) {
            this._clear('target');
            return;
        }
        if (this.timers.target !== 0)
            return;
        this.timers.target = GLib.timeout_add(GLib.PRIORITY_DEFAULT, TARGET_MS, () => {
            this._pollTarget();
            return GLib.SOURCE_CONTINUE;
        });
        this._pollTarget();
    }

    _pollTarget() {
        if (this.targetBusy || this.targetFound)
            return;
        this.targetBusy = true;
        let proc;
        try {
            proc = Gio.Subprocess.new(['pgrep', '-f', '--', this.options.processPattern], Gio.SubprocessFlags.STDOUT_PIPE);
        } catch (error) {
            this.targetBusy = false;
            this._clear('target');
            this.options.onProblem(`cannot look for the target process: ${error.message}`);
            return;
        }
        proc.communicate_utf8_async(null, null, (source, result) => {
            this.targetBusy = false;
            let output = '';
            try {
                [, output] = source.communicate_utf8_finish(result);
            } catch (error) {
                this._clear('target');
                if (!this.detached)
                    this.options.onProblem(`cannot look for the target process: ${error.message}`);
                return;
            }
            if (this.targetFound || this.timers.target === 0)
                return;
            for (const pid of this._pidsOf(output)) {
                if (!this.baseline.has(pid)) {
                    this.targetFound = true;
                    this._clear('target');
                    this.options.onTarget();
                    return;
                }
            }
        });
    }

    _signal(name) {
        const group = `-${this.proc.get_identifier()}`;
        try {
            Gio.Subprocess.new(['kill', `-${name}`, '--', group], Gio.SubprocessFlags.NONE);
        } catch (error) {
            this.options.onProblem(`cannot send ${name} to the command: ${error.message}`);
        }
    }

    // Stop the command and everything it started: TERM, then KILL.
    cancel() {
        if (!this.running)
            return;
        this._signal('TERM');
        this.timers.kill = GLib.timeout_add(GLib.PRIORITY_DEFAULT, KILL_MS, () => {
            this.timers.kill = 0;
            if (this.running)
                this._signal('KILL');
            return GLib.SOURCE_REMOVE;
        });
    }

    stopTail() {
        this._clear('tail');
    }

    // Let go of the command: it runs on, nothing is read or reported any more.
    // A command that was told to stop is still killed when it does not.
    detach() {
        for (const name of Object.keys(this.timers)) {
            if (name !== 'kill')
                this._clear(name);
        }
        this.detached = true;
        this.exitReported = true;
        this.targetFound = true;
    }

    _clear(name) {
        if (this.timers[name] !== 0) {
            GLib.source_remove(this.timers[name]);
            this.timers[name] = 0;
        }
    }
}
