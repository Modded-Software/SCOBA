// The state of one run of the launch dialog (REQ-LAUNCH-DIALOG). No toolkit,
// no clock of its own: every call takes the time in seconds.

import {classify, hintsFor} from './actions.js';

// After the command ends with code 0, the target process must show this soon.
export const TARGET_GRACE = 60;
const KEPT_LINES = 400;
const KEPT_ERRORS = 200;

export class Tracker {
    // history: step id -> seconds of the last good run of this action.
    constructor(action, history, now) {
        this.action = action;
        this.steps = action.steps.map(step => ({
            id: step.id,
            name: step.name,
            build: step.build,
            state: 'pending',
            started: null,
            ended: null,
            measured: history[step.id] > 0,
            estimate: history[step.id] > 0 ? history[step.id] : step.seconds,
        }));
        this.status = 'running';   // running, done, failed, cancelled
        this.reason = null;        // exit, target-missing
        this.index = 0;
        this.startedAt = now;
        this.endedAt = null;
        this.exitCode = null;
        this.exitedAt = null;
        this.errorLines = [];
        this.warnings = 0;
        this.lines = 0;
        this.recent = [];
        this.lastLine = '';
        this.steps[0].state = 'running';
        this.steps[0].started = now;
    }

    get current() {
        return this.steps[this.index];
    }

    get last() {
        return this.index === this.steps.length - 1;
    }

    // The target process is looked for in the last step, and after the command ended.
    get wantsTarget() {
        return this.status === 'running' && (this.last || this.exitedAt !== null);
    }

    // The command is still the project's own script: stopping it is safe.
    get cancellable() {
        return this.status === 'running' && !this.last && this.exitedAt === null;
    }

    // The dialog closes by itself only after a clean start.
    get holdOpen() {
        return this.status !== 'done' || this.errorLines.length > 0;
    }

    // One log line. Returns 'error', 'warning', 'step' or 'plain'.
    feed(source, line, now) {
        this.lines += 1;
        const kind = classify(line);
        if (this.status !== 'running')
            return kind;
        if (line.trim() !== '') {
            this.lastLine = line;
            this.recent.push(line);
            if (this.recent.length > KEPT_LINES)
                this.recent.shift();
        }
        if (kind === 'error' && this.errorLines.length < KEPT_ERRORS)
            this.errorLines.push(line);
        if (kind === 'warning')
            this.warnings += 1;
        const spec = this.action.steps;
        for (let i = this.steps.length - 1; i > this.index; i -= 1) {
            if (spec[i].source === source && spec[i].marker.test(line)) {
                this._advance(i, now);
                return kind === 'plain' ? 'step' : kind;
            }
        }
        return kind;
    }

    _advance(index, now) {
        for (let i = this.index; i < index; i += 1) {
            const step = this.steps[i];
            step.state = 'done';
            step.started = step.started === null ? now : step.started;
            step.ended = now;
        }
        this.index = index;
        this.current.state = 'running';
        this.current.started = now;
    }

    _fail(reason, now) {
        this.status = 'failed';
        this.reason = reason;
        this.current.state = 'failed';
        this.current.ended = now;
        this.endedAt = now;
    }

    // The command ended. A code other than 0 fails the run at once.
    childExited(code, now) {
        if (this.status !== 'running')
            return;
        this.exitCode = code;
        if (code !== 0)
            this._fail('exit', now);
        else
            this.exitedAt = now;
    }

    // A new target process shows: the run is done.
    targetSeen(now) {
        if (!this.wantsTarget)
            return;
        for (const step of this.steps) {
            step.started = step.started === null ? now : step.started;
            step.ended = step.ended === null ? now : step.ended;
            step.state = 'done';
        }
        this.index = this.steps.length - 1;
        this.status = 'done';
        this.endedAt = now;
    }

    cancel(now) {
        if (this.status !== 'running')
            return;
        this.status = 'cancelled';
        this.current.state = 'cancelled';
        this.current.ended = now;
        this.endedAt = now;
    }

    tick(now) {
        if (this.status === 'running' && this.exitedAt !== null && now - this.exitedAt >= TARGET_GRACE)
            this._fail('target-missing', now);
    }

    elapsed(now) {
        return (this.endedAt === null ? now : this.endedAt) - this.startedAt;
    }

    stepElapsed(step, now) {
        if (step.started === null)
            return null;
        return (step.ended === null ? now : step.ended) - step.started;
    }

    // fraction: 0 to 1, never back. remaining: seconds, or null when a step
    // of this action has no measured time yet.
    progress(now) {
        const total = this.steps.reduce((sum, step) => sum + step.estimate, 0);
        if (this.status === 'done')
            return {fraction: 1, remaining: 0};
        let spent = 0;
        let remaining = 0;
        for (const step of this.steps) {
            if (step.state === 'done') {
                spent += step.estimate;
            } else if (step.state === 'pending') {
                remaining += step.estimate;
            } else {
                const inStep = Math.min(this.stepElapsed(step, now), step.estimate * 0.95);
                spent += inStep;
                remaining += step.estimate - inStep;
            }
        }
        const measured = this.steps.every(step => step.measured);
        return {fraction: Math.min(0.99, spent / total), remaining: measured ? remaining : null};
    }

    // Seconds per step of a good run, for the next run's progress.
    durations() {
        const out = {};
        if (this.status !== 'done')
            return out;
        for (const step of this.steps) {
            const seconds = step.ended - step.started;
            if (seconds > 0)
                out[step.id] = Math.round(seconds * 10) / 10;
        }
        return out;
    }

    // headline, detail and hints for the state the run ended in.
    summary() {
        const target = this.action.target;
        if (this.status === 'running')
            return {headline: this.current.name, detail: '', hints: []};
        if (this.status === 'done') {
            const count = this.errorLines.length;
            const detail = count === 0 ? '' : `The log shows ${count} error ${count === 1 ? 'line' : 'lines'}: ${this.errorLines[0]}`;
            return {headline: `${target} started`, detail, hints: []};
        }
        if (this.status === 'cancelled')
            return {headline: `Cancelled: ${this.current.name}`, detail: '', hints: []};
        const hints = hintsFor(this.recent);
        if (this.current.build)
            hints.push('The last built map still launches: Launch Last Build.');
        if (this.reason === 'target-missing') {
            return {
                headline: `${target} did not start`,
                detail: `The launcher ended, and no new ${target} process showed in ${TARGET_GRACE} s.`,
                hints,
            };
        }
        const errors = this.errorLines.filter(line => !line.startsWith('Traceback'));
        const line = errors.length > 0 ? errors[errors.length - 1] : this.lastLine;
        const detail = line === '' ? `Exit code ${this.exitCode}.` : `${line} (exit code ${this.exitCode})`;
        return {headline: `Failed: ${this.current.name}`, detail, hints};
    }
}
