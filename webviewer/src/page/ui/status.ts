// Status messages: a toast at the top centre of the view (not in a panel),
// and the message log, a dialog a click on the toast opens
// (SPEC-VIEWER 16.1).

import type { Rect, StatusOptions } from '../core/types';
import type { StatusService } from '../core/context';
import { make, messageOf } from '../core/dom';
import { Dialog } from './components/dialog';
import { Toast } from './components/toast';

const STATUS_MS = 5000; // a message stays up this long
const FAILURE_MS = 9000; // a failure stays up longer
const STATUS_MIN_MS = 100; // every message shows at least this long (operator 2026-11-22: 0.1 s)

interface Waiting {
  text: string;
  failure: boolean;
  brief: boolean;
}

export function installStatus(visibleRect: () => Rect): StatusService {
  const statusToast = new Toast({ id: 'status', place: 'top', role: 'status' });
  /** The next step: show the next message, or take the toast down. */
  let statusTimer: ReturnType<typeof setTimeout> | undefined;
  let statusShownAt = 0; // when the shown message went up (performance.now)
  /** Messages waiting for the shown one's STATUS_MIN_MS. */
  const statusQueue: Waiting[] = [];
  /** For the tests: every message put on the toast, in order. */
  const statusLog: string[] = [];

  // The message log: every message given to setStatus since the page
  // loaded, with its clock time, in a dialog a click on the toast opens.
  const logDialog = new Dialog({ id: 'status-log-dialog', title: 'messages' });
  const logList = make('ul', { id: 'status-log', className: 'rows' });
  logDialog.body.append(logList);
  const two = (n: number): string => String(n).padStart(2, '0');
  const clock = (d: Date): string => `${two(d.getHours())}:${two(d.getMinutes())}:${two(d.getSeconds())}.${Math.floor(d.getMilliseconds() / 100)}`;

  function logMessage(text: string, failure: boolean): void {
    const now = new Date();
    const time = make('time', { dateTime: now.toISOString(), textContent: clock(now) });
    const body = make('span', { className: 'text', textContent: text });
    const row = make('li', {}, [time, body]);
    row.classList.toggle('failure', failure);
    // Keep the newest in sight when the log is open at its end.
    const atEnd = logList.scrollTop + logList.clientHeight >= logList.scrollHeight - 2;
    logList.append(row);
    if (atEnd) logList.scrollTop = logList.scrollHeight;
  }

  function openLog(): void {
    logDialog.open();
    logList.scrollTop = logList.scrollHeight;
  }
  /** For the tests: how long the last message was up when the toast went down by itself (ms), or null. */
  let statusLastUpMs: number | null = null;

  /** Put the status toast at the centre of the visible view (again, after a panel opens or closes). */
  function placeStatus(): void {
    if (!statusToast.isUp) return;
    const view = visibleRect();
    statusToast.node.style.left = `${(view.left + view.right) / 2}px`;
  }

  function schedule(ms: number, step: () => void): void {
    clearTimeout(statusTimer);
    statusTimer = setTimeout(step, Math.max(0, ms));
  }

  /** Take the toast down now and forget the waiting messages. */
  function dropStatus(): void {
    clearTimeout(statusTimer);
    statusTimer = undefined;
    statusQueue.length = 0;
    statusToast.hide();
  }

  /**
   * The next step of the toast. Up and shown less than STATUS_MIN_MS: wait.
   * A waiting message: it replaces the shown text in place (the toast does
   * not go down between messages). None: the toast goes down when the shown
   * message's time is over.
   */
  function pumpStatus(): void {
    const shownFor = performance.now() - statusShownAt;
    if (statusToast.isUp && shownFor < STATUS_MIN_MS) {
      schedule(STATUS_MIN_MS - shownFor, pumpStatus);
      return;
    }
    const next = statusQueue.shift();
    if (!next) {
      if (statusToast.isUp) statusLastUpMs = shownFor;
      statusToast.hide();
      statusTimer = undefined;
      return;
    }
    statusToast.node.classList.toggle('failure', next.failure);
    if (statusToast.isUp) statusToast.text.textContent = next.text;
    else {
      const view = visibleRect();
      statusToast.show(next.text, (view.left + view.right) / 2);
    }
    statusShownAt = performance.now();
    statusLog.push(next.text);
    const last = next.brief ? STATUS_MIN_MS : next.failure ? FAILURE_MS : STATUS_MS;
    schedule(statusQueue.length ? STATUS_MIN_MS : last, pumpStatus);
  }

  /**
   * Show a message at the top centre of the view for a few seconds. Each
   * message shows at least STATUS_MIN_MS; a message that comes sooner waits,
   * then replaces the text with the toast still up. No message is dropped.
   * An empty text says the last message is over: it lasts only its
   * STATUS_MIN_MS (waiting or shown), and the toast goes down after it unless
   * another message comes. Every message goes into the message log at once.
   * A click on the toast opens the log and takes the toast down.
   */
  function setStatus(text: string, { failure = false }: StatusOptions = {}): void {
    if (!text) {
      const last = statusQueue[statusQueue.length - 1];
      if (last) last.brief = true;
      else if (statusToast.isUp) schedule(STATUS_MIN_MS - (performance.now() - statusShownAt), pumpStatus);
      return;
    }
    logMessage(text, failure);
    statusQueue.push({ text, failure, brief: false });
    if (!statusToast.isUp || statusQueue.length === 1) pumpStatus();
  }
  statusToast.node.addEventListener('click', () => {
    dropStatus();
    openLog();
  });
  statusToast.node.title = 'click: all messages';

  /**
   * End of the line for a failed user action (add, drop, pick a sky): the
   * action already put the message in the status line; this also logs it.
   */
  function reportFailure(error: unknown): void {
    console.warn('sc2viewer:', error);
    setStatus(messageOf(error), { failure: true });
  }

  const service: StatusService = {
    setStatus,
    reportFailure,
    pending: 0,
    /** Run a load with the pending count up; a failure goes on the status line and on to the caller. */
    async busy<T>(work: () => Promise<T>): Promise<T> {
      service.pending++;
      try {
        return await work();
      } catch (error) {
        setStatus(messageOf(error), { failure: true });
        throw error;
      } finally {
        service.pending--;
      }
    },
    statusState: () => ({ text: statusToast.text.textContent, up: statusToast.isUp, failure: statusToast.node.classList.contains('failure') }),
    statusLog: () => ({ shown: [...statusLog], waiting: statusQueue.length, lastUpMs: statusLastUpMs }),
    placeStatus,
  };
  return service;
}
