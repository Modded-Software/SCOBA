// When a press on the view becomes a drag (SPEC-VIEWER 16.3, R-VIEW-142).
// A slow press: at the first move at least `slop` pixels from the press
// point and at least `holdMs` after the press. A fast press: at the first
// move at least `fast` pixels from the press point, at any time. Before
// that it is a click, and nothing moves. features/controls, features/pick
// and features/select all decide by this one rule; its numbers are rates
// of the input map (core/input.ts, R-VIEW-154), read at the press.

import type { Rates } from './input';

/** One press: where and when, and whether it became a drag. */
export interface Press {
  readonly x: number;
  readonly y: number;
  /** The press's event time (`timeStamp`, ms). */
  readonly time: number;
  dragging: boolean;
  /** It became a drag by a fast move (`fast` before `holdMs`): it acts from the press point. */
  fast: boolean;
  readonly rule: { readonly slop: number; readonly holdMs: number; readonly fast: number };
}

export function pressAt(e: MouseEvent, rates: Pick<Rates, 'dragSlop' | 'dragHoldMs' | 'fastSlop'>): Press {
  return { x: e.clientX, y: e.clientY, time: e.timeStamp, dragging: false, fast: false, rule: { slop: rates.dragSlop, holdMs: rates.dragHoldMs, fast: rates.fastSlop } };
}

/** Whether the press is a drag after this move. Once a drag, it stays one. */
export function dragsAt(press: Press, e: MouseEvent): boolean {
  if (press.dragging) return true;
  const travel = Math.hypot(e.clientX - press.x, e.clientY - press.y);
  const held = e.timeStamp - press.time >= press.rule.holdMs;
  if (travel >= press.rule.fast && !held) press.fast = true;
  press.dragging = travel >= press.rule.fast || (travel >= press.rule.slop && held);
  return press.dragging;
}
