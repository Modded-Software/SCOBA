// Units under the mouse, and clicks on them. The selection, the hover and
// the hit tests are the selection service (core/selection.ts).
// - mouse-over: the unit brightens, a feathered green glow runs around its
//   outline (core/render/outline.ts, drawn by the frame) and a thin ring shows under it;
// - every selected unit stays brightened as under the mouse, without the glow;
// - left click: selects the unit under the mouse (green ring); a click on
//   the ground or the sky deselects, a click on another unit selects that;
//   the instances panel marks the selected unit's row (and a row click
//   selects its unit);
// - shift + left click: adds the unit under the mouse to the selection, or
//   takes it out; on the ground it keeps the selection. Every selected
//   unit has a ring. (The select rectangle and Delete are in features/select.)
// - ctrl + left hold, with units selected: they turn to face the ground
//   point under the mouse (features/controls);
// - alt + left hold on a unit: drags the unit over the ground (features/controls);
// - right click on a unit: the animation menu (menu.ts); Ctrl+L switches its "loop" choice;
// - double-click on a unit: what its game opens for it (openItem).
// A press that moves more than CLICK_SLOP pixels is a drag (camera), not a click.

import type { Feature } from '../../core/context';
import { radius } from '../../core/geometry';
import type { Ring } from '../../core/render/ground';
import type { Item, PickState, Vec2 } from '../../core/types';
import { createMenu } from './menu';

const CLICK_SLOP = 4; // px
const SELECT_RING: Pick<Ring, 'width' | 'color'> = { width: 0.07, color: [0.2, 1.0, 0.25] };
const HOVER_RING: Pick<Ring, 'width' | 'color'> = { width: 0.035, color: [0.75, 1.0, 0.75] };
const BUTTON = { left: 0, right: 2 };

export const pickFeature: Feature = {
  id: 'pick',
  install(context) {
    const { render, scene, selection, games, status, events, testApi } = context;
    const { canvas, ground } = render;
    const { items } = scene;

    let mouse: Vec2 | null = null; // last [clientX, clientY] over the canvas
    let press: { button: number; x: number; y: number; ctrl: boolean; shift: boolean; moved: boolean } | null = null;

    const byId = (id: number | null): Item | null => items.find((item) => item.id === id) ?? null;
    const ring = (item: Item | null, look: Pick<Ring, 'width' | 'color'>): Ring | null => (item ? { x: item.x, y: item.y, radius: radius(item), ...look } : null);

    const menu = createMenu(context, byId);

    /** Each frame, before drawing: what is under the mouse, highlights and rings. */
    function updatePick(): void {
      const under = mouse && !menu.item() ? selection.itemAt(mouse[0], mouse[1]) : null;
      const hovered = under ? under.id : null;
      selection.setHovered(hovered);
      const last = selection.selectedId();
      const chosen = selection.selectedIds();
      // Lit: the unit under the mouse and every selected one. The outline glow is the hovered one's only (frame.ts).
      for (const item of items) item.instance.highlight = item.id === hovered || chosen.includes(item.id) ? 1 : 0;
      // Rings: [the one selected last, mouse-over, the other selected ones...].
      const others: Ring[] = [];
      for (const id of chosen) {
        const r = id !== last ? ring(byId(id), SELECT_RING) : null;
        if (r) others.push(r);
      }
      ground.rings = [ring(byId(last), SELECT_RING), hovered !== null && !chosen.includes(hovered) ? ring(byId(hovered), HOVER_RING) : null, ...others];
      // After endOneShots: a one-shot that ended shows as idle again.
      menu.markPlaying();
    }

    events.on('frame', updatePick);
    events.on('selection-changed', updatePick);
    events.on('items-removed', ({ ids, all }) => {
      const open = menu.itemId();
      if (all || (open !== null && ids.includes(open))) menu.close();
      updatePick();
    });
    // A game setting changed (SC2 Ctrl+H): the open menu shows it.
    events.on('item-swapped', () => menu.refresh());
    events.on('scene-edited', () => menu.refresh());

    // ---- mouse ----

    canvas.addEventListener('mousemove', (e) => {
      mouse = [e.clientX, e.clientY];
    });
    canvas.addEventListener('mouseleave', () => {
      mouse = null;
    });
    canvas.addEventListener('mousedown', (e) => {
      press = { button: e.button, x: e.clientX, y: e.clientY, ctrl: e.ctrlKey, shift: e.shiftKey, moved: false };
    });
    window.addEventListener('mousemove', (e) => {
      if (press && Math.hypot(e.clientX - press.x, e.clientY - press.y) > CLICK_SLOP) press.moved = true;
    });
    window.addEventListener('mouseup', (e) => {
      const p = press;
      press = null;
      if (!p || p.moved || p.button !== e.button) return;
      if (p.button === BUTTON.left) {
        // Ctrl + left with a selection turns the unit; it keeps the selection.
        if (p.ctrl && selection.selectedId() !== null) return;
        const item = selection.itemAt(e.clientX, e.clientY);
        // Shift: add the unit or take it out; on the ground, keep the selection.
        if (p.shift) {
          if (item) selection.toggleSelected(item.id);
        } else selection.select(item ? item.id : null);
      } else if (p.button === BUTTON.right) {
        const item = selection.itemAt(e.clientX, e.clientY);
        if (item) menu.open(item, e.clientX, e.clientY);
      }
    });
    // A double-click on an instance opens what its game shows for it (SC2: the texture window).
    canvas.addEventListener('dblclick', (e) => {
      const item = selection.itemAt(e.clientX, e.clientY);
      if (item) games.partsOf(item.game).openItem(item).catch(status.reportFailure);
    });

    // ---- keys ----

    window.addEventListener('keydown', (e) => {
      if (!e.ctrlKey || e.altKey || e.metaKey || e.shiftKey || e.key.toLowerCase() !== 'l') return;
      // The viewer owns Ctrl+L everywhere on the page: the browser's address bar
      // never opens, with or without a selection, in a text field too (operator 2026-11-22).
      e.preventDefault();
      // A field being edited: the key is consumed and does nothing.
      if (selection.editingText(e.target)) return;
      if (!selection.hasSelection()) {
        status.setStatus('Ctrl+L: select an instance first');
        return;
      }
      status.setStatus(`loop ${menu.toggleLoop() ? 'on' : 'off'}`);
    });

    /** For the tests: ids under the mouse and selected, and the open menu. */
    const pickState = (): PickState => ({
      hovered: selection.hovered()?.id ?? null,
      selected: selection.selectedId(),
      selection: selection.selectedIds().sort((a, b) => a - b),
      // The select rectangle while it is dragged (features/select), in page pixels.
      rect: selection.rect(),
      menu: menu.state(),
      // The "loop" choice, menu open or not.
      loop: menu.loop(),
    });
    testApi.viewer({ pickState });
    testApi.statePart('pick', pickState);
  },
};
