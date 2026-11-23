// The animation menu: a right click on a unit opens a menu of its
// animations, the playing one marked. A click plays one once, then the
// unit goes back to its own animation; with "loop" checked it becomes the
// unit's own and loops. The menu stays open until Escape or a click elsewhere.

import { app, type Item, type MenuState } from '../../core/app';
import { find, make } from '../../core/dom';

export interface AnimMenu {
  /** The item whose menu is open, or null. */
  item(): Item | null;
  itemId(): number | null;
  open(item: Item, clientX: number, clientY: number): void;
  close(): void;
  markPlaying(): void;
  refresh(): void;
  toggleLoop(): boolean;
  loop(): boolean;
  state(): MenuState | null;
}

export function createMenu(byId: (id: number) => Item | null): AnimMenu {
  let menu: { node: HTMLElement; itemId: number } | null = null;
  const menuItem = (): Item | null => (menu ? byId(menu.itemId) : null);
  // Loop the chosen animation (it becomes the unit's own), or play it once
  // and go back to idle. Kept from one menu to the next.
  let loopChoice = false;

  function close(): void {
    if (menu) menu.node.remove();
    menu = null;
  }

  const entryButtons = (node: HTMLElement): HTMLButtonElement[] => [...node.querySelectorAll('button[data-sequence]')].filter((b): b is HTMLButtonElement => b instanceof HTMLButtonElement);

  /** Mark the menu entry of the animation the unit plays now. */
  function markPlaying(): void {
    const item = menuItem();
    if (!item || !menu) return;
    const now = String(item.instance.sequence);
    for (const button of entryButtons(menu.node)) button.classList.toggle('playing', button.dataset.sequence === now);
  }

  function open(item: Item, clientX: number, clientY: number): void {
    close();
    const entries = item.model.sequences.map((s, i) => {
      const button = make('button', { type: 'button', textContent: s.name });
      button.dataset.sequence = String(i);
      // The menu stays open: the next pick is one click away.
      button.addEventListener('click', () => {
        if (loopChoice) app().loopSequence(item, i);
        else app().playOnce(item, i);
        markPlaying();
      });
      return make('li', {}, [button]);
    });
    const title = make('div', { className: 'title', textContent: item.unit ? item.unit.name : (item.path.split('\\').pop() ?? item.path) });
    const loop = make('input', { type: 'checkbox', className: 'loop', checked: loopChoice });
    loop.addEventListener('change', () => {
      loopChoice = loop.checked;
    });
    const loopLabel = make('label', { className: 'loop-choice', title: 'checked: the animation loops; unchecked: it plays once, then idle' }, [loop, 'loop']);
    const choices = [loopLabel];
    // A model with both texture sets: the HD one on or off (features/hd).
    if (item.hdLayers) {
      const hd = make('input', { type: 'checkbox', className: 'hd', checked: item.hd });
      hd.addEventListener('change', () => app().setHd(item, hd.checked).catch(app().reportFailure));
      choices.push(make('label', { className: 'loop-choice hd-choice', title: 'checked: the upscaled HD textures; unchecked: the standard ones (Ctrl+H)' }, [hd, 'hd']));
    }
    const body = entries.length ? make('ul', {}, entries) : make('div', { className: 'empty', textContent: 'no animations' });
    const node = make('div', { id: 'anim-menu', className: 'anim-menu' }, [title, ...choices, body]);
    document.body.append(node);
    // Inside the window: flip to the left or up when it would overflow.
    const w = node.offsetWidth;
    const h = node.offsetHeight;
    node.style.left = `${clientX + w > innerWidth ? Math.max(0, clientX - w) : clientX}px`;
    node.style.top = `${clientY + h > innerHeight ? Math.max(0, innerHeight - h) : clientY}px`;
    menu = { node, itemId: item.id };
    markPlaying();
  }

  /** Show the open menu's checkboxes as the choices are now (changed by a key, features/hd). */
  function refresh(): void {
    const item = menuItem();
    if (!item || !menu) return;
    const loop = find(menu.node, 'input.loop', HTMLInputElement);
    if (loop) loop.checked = loopChoice;
    const hd = find(menu.node, 'input.hd', HTMLInputElement);
    if (hd) hd.checked = item.hd;
  }

  /** Switch the "loop" choice (Ctrl+L). Returns the new choice. */
  function toggleLoop(): boolean {
    loopChoice = !loopChoice;
    refresh();
    return loopChoice;
  }

  window.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') close();
  });
  window.addEventListener(
    'mousedown',
    (e) => {
      if (menu && !(e.target instanceof Node && menu.node.contains(e.target))) close();
    },
    true,
  );

  function state(): MenuState | null {
    if (!menu) return null;
    const node = menu.node;
    const hd = find(node, 'input.hd', HTMLInputElement);
    return {
      item: menu.itemId,
      entries: entryButtons(node).map((b) => b.textContent),
      // The marked entries (exactly one while an animation plays).
      playing: [...node.querySelectorAll('button.playing')].map((b) => b.textContent),
      loop: find(node, 'input.loop', HTMLInputElement)?.checked ?? false,
      // The "hd" checkbox, when the menu has one (a model with both texture sets).
      hd: hd ? hd.checked : undefined,
    };
  }

  return { item: menuItem, itemId: () => (menu ? menu.itemId : null), open, close, markPlaying, refresh, toggleLoop, loop: () => loopChoice, state };
}
