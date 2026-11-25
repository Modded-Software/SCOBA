// When a press on the view becomes a drag (SPEC-VIEWER 16.3, R-VIEW-142).
// A slow press: at the first move at least DRAG_SLOP pixels from the press
// point and at least DRAG_HOLD_MS after the press. A fast press: at the
// first move at least FAST_SLOP pixels from the press point, at any time.
// Before that it is a click, and nothing moves. features/controls,
// features/pick and features/select all decide by this one rule.

/** Pixels the pointer must travel from the press point. */
export const DRAG_SLOP = 2;
/** Milliseconds a press must be held before a short travel is a drag. */
export const DRAG_HOLD_MS = 150;
/** Pixels of travel that make a drag at once: a fast move is never a click. */
export const FAST_SLOP = 12;

/** One press: where and when, and whether it became a drag. */
export interface Press {
  readonly x: number;
  readonly y: number;
  /** The press's event time (`timeStamp`, ms). */
  readonly time: number;
  dragging: boolean;
  /** It became a drag by a fast move (FAST_SLOP before DRAG_HOLD_MS): it acts from the press point. */
  fast: boolean;
}

export function pressAt(e: MouseEvent): Press {
  return { x: e.clientX, y: e.clientY, time: e.timeStamp, dragging: false, fast: false };
}

/** Whether the press is a drag after this move. Once a drag, it stays one. */
export function dragsAt(press: Press, e: MouseEvent): boolean {
  if (press.dragging) return true;
  const travel = Math.hypot(e.clientX - press.x, e.clientY - press.y);
  const held = e.timeStamp - press.time >= DRAG_HOLD_MS;
  if (travel >= FAST_SLOP && !held) press.fast = true;
  press.dragging = travel >= FAST_SLOP || (travel >= DRAG_SLOP && held);
  return press.dragging;
}
