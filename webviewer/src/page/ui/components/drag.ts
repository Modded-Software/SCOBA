// Drag by a title (R-VIEW-138, R-VIEW-141): a left drag on the handle moves
// the node with the pointer. The floating windows and the instance menu use
// it. At least KEEP pixels of the handle stay on the page, so it can always
// be grabbed again.

/** Pixels of the handle that stay on the page. */
export const KEEP = 80;

/** Move `node`'s top left corner to (left, top), as far as `handle` stays reachable. */
export function placeWithin(node: HTMLElement, handle: HTMLElement, left: number, top: number): void {
  const x = Math.min(Math.max(left, KEEP - node.offsetWidth), innerWidth - KEEP);
  const y = Math.min(Math.max(top, 0), innerHeight - handle.offsetHeight);
  node.style.left = `${x}px`;
  node.style.top = `${y}px`;
}

export interface DragOptions {
  /** What moves. */
  node: HTMLElement;
  /** What is grabbed: the title. */
  handle: HTMLElement;
  /** A press on this target does not start a drag (a close button). */
  ignore?: (target: EventTarget | null) => boolean;
}

/** Make `handle` drag `node`. While it drags, `node` has the class "dragging". */
export function draggable({ node, handle, ignore }: DragOptions): void {
  let grab: { x: number; y: number } | null = null; // where in the node the pointer holds it
  handle.classList.add('drag-handle');
  handle.addEventListener('pointerdown', (e) => {
    if (e.button !== 0 || ignore?.(e.target)) return;
    e.preventDefault();
    grab = { x: e.clientX - node.offsetLeft, y: e.clientY - node.offsetTop };
    handle.setPointerCapture(e.pointerId);
    // A frame under the pointer would take it while it passes over.
    node.classList.add('dragging');
  });
  handle.addEventListener('pointermove', (e) => {
    if (grab) placeWithin(node, handle, e.clientX - grab.x, e.clientY - grab.y);
  });
  for (const name of ['pointerup', 'pointercancel'] as const) {
    handle.addEventListener(name, () => {
      grab = null;
      node.classList.remove('dragging');
    });
  }
}
