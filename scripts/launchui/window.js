// The launch dialog (REQ-LAUNCH-DIALOG): runs one action, shows its steps,
// its progress and its log, and stays open when the run shows an error.

import GLib from 'gi://GLib';

import {ACTIONS, formatSeconds} from './actions.js';
import {Runner} from './runner.js';
import {LogFile, readTimes, stateDir, timesOf, writeTimes} from './store.js';
import {Tracker} from './tracker.js';
import {View} from './view.js';

const FLUSH_MS = 60;        // log lines reach the view this often
const FLUSH_ITEMS = 2000;   // and at most this many at a time
const TICK_MS = 250;
const CLOSE_MS = 2500;      // a clean start closes the dialog after this
const CLOSE_RETRY_MS = 100; // a close the window did not take is asked again this often
const TAIL_AFTER_MS = 3000; // the log file is followed this long after the end
const STOP_WAIT_MS = 5000;  // a stopped command gets this long to end

function now() {
    return GLib.get_monotonic_time() / 1000000;
}

export class LaunchWindow {
    // options: root, actionId, processPattern (or null), reportPath (or null).
    constructor(application, options) {
        this.options = options;
        this.view = new View(application);
        this.queue = [];
        this.runner = null;
        this.tracker = null;
        this.logFile = null;
        this.settled = false;
        this.closing = false;
        this.timers = {flush: 0, tick: 0, close: 0, tail: 0, stop: 0};

        this.view.copy.connect('clicked', () => {
            this.view.window.get_clipboard().set(this.view.logText());
            this.view.toast('Log copied');
        });
        this.view.retry.connect('clicked', () => this.start(this.action.id));
        this.view.lastBuild.connect('clicked', () => this.start('launch-built'));
        this.view.main.connect('clicked', () => {
            if (this.tracker.cancellable)
                this._stop(false);
            else
                this._close();
        });
        this.view.window.connect('close-request', () => this._onCloseRequest());
        this.timers.flush = GLib.timeout_add(GLib.PRIORITY_DEFAULT, FLUSH_MS, () => {
            this._flush();
            return GLib.SOURCE_CONTINUE;
        });
        this.timers.tick = GLib.timeout_add(GLib.PRIORITY_DEFAULT, TICK_MS, () => {
            this._refresh();
            return GLib.SOURCE_CONTINUE;
        });
        this.start(options.actionId);
    }

    present() {
        this.view.window.present();
    }

    // Begin a run of one action. Also the Retry and Launch Last Build buttons.
    start(actionId) {
        if (this.runner !== null)
            this.runner.detach();
        if (this.logFile !== null)
            this.logFile.close();
        for (const name of ['close', 'tail', 'stop'])
            this._clear(name);
        this.action = ACTIONS[actionId];
        this.queue = [];
        this.settled = false;
        this.dir = stateDir();
        GLib.mkdir_with_parents(this.dir, 0o755);
        const {times, problem} = readTimes(this.dir);
        this.times = times;
        this.tracker = new Tracker(this.action, timesOf(times, actionId), now());

        const view = this.view;
        view.title.subtitle = this.action.title;
        view.clearLog();
        view.setSteps(this.tracker.steps);
        view.setBanner('');
        view.setDetail('');
        view.retry.visible = false;
        view.lastBuild.visible = false;
        view.progress.remove_css_class('error');

        const command = this.action.command.join(' ');
        this._say(`$ ${command}`);
        if (problem !== null)
            this._say(`warning: ${problem}`);
        try {
            this.logFile = new LogFile(this.dir, actionId);
            view.path.label = this.logFile.path;
        } catch (error) {
            this.logFile = null;
            view.path.label = '';
            this._say(`warning: this log is not saved: ${error.message}`);
        }
        this.runner = new Runner({
            argv: this.action.command,
            cwd: this.options.root,
            tailPath: GLib.build_filenamev([this.dir, this.action.tail]),
            processPattern: this.options.processPattern === null ? this.action.process : this.options.processPattern,
            onLine: (source, text) => this.queue.push({source, text}),
            onExit: code => this.queue.push({exit: code}),
            onTarget: () => this.queue.push({target: true}),
            onProblem: text => this._say(`warning: ${text}`),
        });
        try {
            this.runner.start();
        } catch (error) {
            this._say(`ERROR: cannot start ${command}: ${error.message}`);
            this.queue.push({exit: 127});
        }
        this._refresh();
    }

    // A line of the dialog's own, in the log like any other.
    _say(text) {
        this.queue.push({source: 'dialog', text});
    }

    // Lines, the exit and the target go through one queue: their order holds.
    _flush() {
        if (this.queue.length === 0)
            return;
        const items = this.queue.splice(0, FLUSH_ITEMS);
        const time = now();
        const segments = [];
        let saved = '';
        for (const item of items) {
            if ('exit' in item) {
                this.tracker.childExited(item.exit, time);
            } else if ('target' in item) {
                this.tracker.targetSeen(time);
            } else {
                const kind = this.tracker.feed(item.source, item.text, time);
                const last = segments[segments.length - 1];
                if (last !== undefined && last.kind === kind)
                    last.text += `${item.text}\n`;
                else
                    segments.push({kind, text: `${item.text}\n`});
                saved += `${item.text}\n`;
            }
        }
        this.view.appendLog(segments);
        this._save(saved);
        this._refresh();
    }

    _save(text) {
        if (this.logFile === null || text === '')
            return;
        try {
            this.logFile.write(text);
        } catch (error) {
            const path = this.logFile.path;
            this.logFile = null;
            this._say(`warning: the log is no longer saved to ${path}: ${error.message}`);
        }
    }

    _refresh() {
        const tracker = this.tracker;
        const view = this.view;
        const time = now();
        tracker.tick(time);
        if (!tracker.cancellable)
            view.dismissStop();
        this.runner.setTargetPolling(tracker.wantsTarget);
        tracker.steps.forEach((step, index) => view.setStep(index, step.state, tracker.stepElapsed(step, time)));
        const {fraction, remaining} = tracker.progress(time);
        view.progress.fraction = fraction;
        if (tracker.status !== 'running') {
            if (!this.settled)
                this._settle();
            return;
        }
        const left = remaining === null ? '' : `, about ${formatSeconds(remaining)} left`;
        view.status.label = tracker.current.name;
        view.progressText.label = `Step ${tracker.index + 1} of ${tracker.steps.length}, ${formatSeconds(tracker.elapsed(time))} so far${left}`;
        view.main.label = tracker.cancellable ? 'Cancel' : 'Hide';
        view.setDetail(tracker.cancellable ? '' : 'This window can be closed. The start goes on.');
    }

    // The run ended: say how, offer what helps, close only after a clean start.
    _settle() {
        this.settled = true;
        const tracker = this.tracker;
        const view = this.view;
        const summary = tracker.summary();
        const total = formatSeconds(tracker.elapsed(now()));
        view.status.label = summary.headline;
        view.setDetail([summary.detail, ...summary.hints].filter(text => text !== '').join('\n'));
        view.main.label = 'Close';
        view.retry.visible = tracker.status === 'failed' || tracker.status === 'cancelled';
        view.lastBuild.visible = tracker.status === 'failed' && tracker.current.build;
        this.timers.tail = GLib.timeout_add(GLib.PRIORITY_DEFAULT, TAIL_AFTER_MS, () => {
            this.timers.tail = 0;
            this.runner.stopTail();
            return GLib.SOURCE_REMOVE;
        });
        if (tracker.status === 'done') {
            this._saveTimes();
            view.progressText.label = tracker.holdOpen ? `Started in ${total}` : `Started in ${total}. Closing.`;
            if (tracker.holdOpen) {
                const count = tracker.errorLines.length;
                view.setBanner(`Started, but the log shows ${count} error ${count === 1 ? 'line' : 'lines'}.`);
            } else {
                this.timers.close = GLib.timeout_add(GLib.PRIORITY_DEFAULT, CLOSE_MS, () => {
                    this.timers.close = 0;
                    this._close();
                    return GLib.SOURCE_REMOVE;
                });
            }
        } else if (tracker.status === 'failed') {
            view.progress.add_css_class('error');
            view.progressText.label = `Stopped after ${total}`;
            view.setBanner(`${summary.headline}. The log has the details.`);
            view.window.present();
        } else {
            view.progressText.label = `Cancelled after ${total}`;
        }
        this._report();
    }

    _saveTimes() {
        try {
            this.times = writeTimes(this.dir, this.times, this.action.id, this.tracker.durations());
        } catch (error) {
            this._say(`warning: the step times are not saved: ${error.message}`);
        }
    }

    // Stop the command. With close, the window closes once the command ended.
    _stop(close) {
        this.tracker.cancel(now());
        this.runner.cancel();
        this._refresh();
        if (!close)
            return;
        this.view.window.sensitive = false;
        const end = now() + STOP_WAIT_MS / 1000;
        this.timers.stop = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 100, () => {
            if (this.runner.running && now() < end)
                return GLib.SOURCE_CONTINUE;
            this.timers.stop = 0;
            this._close();
            return GLib.SOURCE_REMOVE;
        });
    }

    // Close the window of a run that is not stoppable any more. An open
    // "Stop the build?" question takes a close for itself, also while it
    // goes away: ask until the window took the close.
    _close() {
        this._clear('close');
        this.view.window.close();
        if (this.closing)
            return;
        this.timers.close = GLib.timeout_add(GLib.PRIORITY_DEFAULT, CLOSE_RETRY_MS, () => {
            if (!this.tracker.cancellable)
                this.view.window.close();
            if (!this.closing && !this.tracker.cancellable)
                return GLib.SOURCE_CONTINUE;
            this.timers.close = 0;
            return GLib.SOURCE_REMOVE;
        });
    }

    // true keeps the window open.
    _onCloseRequest() {
        if (this.tracker.cancellable) {
            this.view.confirmStop(this.tracker.current.name, () => {
                // An answer that comes after the hand-over stops nothing: the
                // command is the game by then.
                if (this.tracker.cancellable)
                    this._stop(true);
            });
            return true;
        }
        this.closing = true;
        this._flush();
        for (const name of Object.keys(this.timers))
            this._clear(name);
        this.runner.detach();
        this._report();
        if (this.logFile !== null)
            this.logFile.close();
        return false;
    }

    _clear(name) {
        if (this.timers[name] !== 0) {
            GLib.source_remove(this.timers[name]);
            this.timers[name] = 0;
        }
    }

    // The state of the dialog as a file, for a caller that cannot see it.
    _report() {
        if (this.options.reportPath === null)
            return;
        const tracker = this.tracker;
        const view = this.view;
        const summary = tracker.summary();
        const data = {
            action: this.action.id,
            status: tracker.status,
            reason: tracker.reason,
            exitCode: tracker.exitCode,
            step: tracker.current.id,
            steps: tracker.steps.map(step => ({id: step.id, state: step.state})),
            errorLines: tracker.errorLines,
            warnings: tracker.warnings,
            lines: tracker.lines,
            headline: view.status.label,
            detail: view.detail.visible ? view.detail.label : '',
            hints: summary.hints,
            banner: view.banner.revealed ? view.banner.title : '',
            buttons: {retry: view.retry.visible, lastBuild: view.lastBuild.visible, main: view.main.label},
            logFile: view.path.label,
            logText: view.logText(),
            fraction: view.progress.fraction,
            windowVisible: view.window.visible,
            closing: this.closing,
        };
        GLib.file_set_contents(this.options.reportPath, `${JSON.stringify(data, null, 2)}\n`);
    }
}
