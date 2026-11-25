// The animation menu: a right click on a unit opens a menu of its
// animations, the playing one marked. A click plays one once, then the
// unit goes back to its own animation; with "loop" checked it becomes the
// unit's own and loops. An instance whose owner has textures has the skin
// row (SPEC-VIEWER 17.4, core/skins.ts). The menu stays open until Escape
// or a click elsewhere.

import { NEW_SKIN, ORIGINAL_SKIN, skinLabel } from '../../../shared/textures';
import type { SceneService, StatusService } from '../../core/context';
import type { Skins } from '../../core/skins';
import type { Item, MenuState } from '../../core/types';
import { find, make } from '../../core/dom';
import { ConfirmDialog } from '../../ui/components/dialog';
import { PENCIL, SKIN, TRASH } from '../../ui/icons';

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

export interface MenuDeps {
  readonly scene: SceneService;
  readonly skins: Pick<Skins, 'choices' | 'set' | 'owner' | 'bake' | 'tools'>;
  readonly status: StatusService;
}

/** The bake button's verb: baking Original unbakes. */
const bakeText = (item: Item): string => (item.skin === ORIGINAL_SKIN ? 'Unbake Skin' : 'Bake Skin');

/** The icons of a row of the skin list: Original has none (R-VIEW-126). */
const iconsOf = (name: string): ('edit' | 'trash')[] => (name === ORIGINAL_SKIN ? [] : ['edit', 'trash']);

/** Why the bake button cannot be used now; empty: it can (R-VIEW-127). */
function bakeBlock(skins: MenuDeps['skins'], item: Item): string {
  if (item.skin === NEW_SKIN) return 'New Skin is not saved: save it first, then bake it';
  if (item.skin === ORIGINAL_SKIN && !skins.owner(item)?.bake) return 'nothing is baked';
  return '';
}

/** Show the bake button as it is now. */
function showBakeButton(button: HTMLButtonElement, skins: MenuDeps['skins'], item: Item): void {
  const block = bakeBlock(skins, item);
  button.textContent = bakeText(item);
  button.disabled = block !== '';
  button.title = block || (item.skin === ORIGINAL_SKIN ? 'remove the bake of this owner in this dataset' : 'bake the chosen skin for this owner in this dataset');
}

/** The baked skin of the item's owner, or null. */
const bakedSkin = (skins: MenuDeps['skins'], item: Item): string | null => skins.owner(item)?.bake?.skin ?? null;

/** Show the bake on the badge: bread and the skin's name; hidden without a bake. */
function showBake(badge: HTMLElement, skin: string | null): void {
  badge.hidden = skin === null;
  badge.textContent = skin === null ? '' : `🍞 ${skin}`;
  badge.title = skin === null ? '' : `baked for this owner in this dataset: ${skin}`;
}

export function createMenu({ scene, skins, status }: MenuDeps, byId: (id: number) => Item | null): AnimMenu {
  const bakeQuestion = make('p', { className: 'bake-question' });
  const confirmBake = new ConfirmDialog({ id: 'bake-skin-dialog', title: 'Bake Skin', yesText: 'Bake Skin', content: [bakeQuestion] });
  const confirmUnbake = new ConfirmDialog({ id: 'unbake-skin-dialog', title: 'Unbake Skin', yesText: 'Unbake Skin', content: [make('p', { className: 'bake-question' })] });

  /** Ask, then bake the item's skin for its owner, or unbake it on Original. A refusal shows its reason; nothing changes (R-VIEW-123). */
  async function bake(item: Item): Promise<void> {
    const owner = skins.owner(item);
    if (!owner) return;
    const unbake = item.skin === ORIGINAL_SKIN;
    const dialog = unbake ? confirmUnbake : confirmBake;
    const question = find(dialog.dialog.body, 'p.bake-question', HTMLParagraphElement);
    if (question) question.textContent = unbake ? `Remove the bake of ${owner.title} (${owner.owner}) in ${item.dataset}? It will show its original textures in the game.` : `Bake skin "${item.skin}" of ${owner.title} (${owner.owner}) in ${item.dataset}? The game will show it; it replaces the bake there is now.`;
    if (!(await dialog.ask())) return;
    await skins.bake(item);
    status.setStatus(unbake ? `${owner.title}: unbaked` : `${owner.title}: skin ${item.skin} baked`);
  }

  /** The skin list (R-VIEW-126, 137): a button with a skin icon, the chosen skin and an arrow; its rows below it. */
  function skinList(item: Item, chosen: () => void): HTMLElement {
    const label = make('span', { className: 'skin-label', textContent: skinLabel(item.skin) });
    const button = make('button', { type: 'button', className: 'skin-choice', title: 'Choose the skin this instance shows; it changes no other instance and no bake' }, [make('span', { className: 'skin-icon', innerHTML: SKIN }), label]);
    const list = make('ul', { className: 'skin-list', hidden: true });
    const tools = (): ReturnType<MenuDeps['skins']['tools']> => skins.tools();
    const shown = (): void => {
      label.textContent = skinLabel(item.skin);
      chosen();
    };
    function rows(): HTMLElement[] {
      const baked = bakedSkin(skins, item);
      return skins.choices(item).map((name) => {
        const pick = make('button', { type: 'button', className: `skin-pick${name === item.skin ? ' chosen' : ''}`, textContent: skinLabel(name) });
        pick.addEventListener('click', () => {
          list.hidden = true;
          skins.set(item, name).then(shown).catch(status.reportFailure);
        });
        const icons: HTMLElement[] = [];
        if (iconsOf(name).includes('edit')) {
          const edit = make('button', { type: 'button', className: 'skin-edit', innerHTML: PENCIL, title: `Edit Skin "${skinLabel(name)}"` });
          edit.addEventListener('click', () => {
            list.hidden = true;
            tools()?.edit(item, name);
          });
          icons.push(edit);
        }
        if (iconsOf(name).includes('trash')) {
          // Red (R-VIEW-136); the baked skin cannot be deleted (R-HD-136).
          const trash = make('button', { type: 'button', className: 'skin-trash trash', innerHTML: TRASH, title: name === NEW_SKIN ? 'Discard New Skin' : `Delete Skin "${name}"` });
          if (name === baked) {
            trash.disabled = true;
            trash.title = 'baked: unbake it or bake another skin first';
          }
          trash.addEventListener('click', () => {
            list.hidden = true;
            tools()
              ?.remove(item, name)
              .then((gone) => gone && shown())
              .catch(status.reportFailure);
          });
          icons.push(trash);
        }
        const row = make('li', {}, [pick, ...icons]);
        row.dataset['skin'] = name;
        return row;
      });
    }
    const add = make('button', { type: 'button', className: 'skin-add', textContent: 'Add New Skin…', title: 'Open the skin editor on New Skin' });
    add.addEventListener('click', () => {
      list.hidden = true;
      tools()?.edit(item, NEW_SKIN);
    });
    button.addEventListener('click', () => {
      if (list.hidden) list.replaceChildren(...rows(), make('li', { className: 'skin-add-row' }, [add]));
      list.hidden = !list.hidden;
    });
    return make('div', { className: 'skin-choose' }, [button, list]);
  }

  function skinRow(item: Item): HTMLElement[] {
    if (!skins.choices(item).length) return [];
    const upscale = make('button', { type: 'button', className: 'skin-upscale', textContent: 'Upscale Skin', title: 'Make New Skin: every texture of this owner by one model at one size' });
    upscale.addEventListener('click', () => skins.tools()?.upscale(item));
    const bakeButton = make('button', { type: 'button', className: 'skin-bake' });
    showBakeButton(bakeButton, skins, item);
    const badge = make('span', { className: 'skin-baked' });
    showBake(badge, bakedSkin(skins, item));
    bakeButton.addEventListener('click', () =>
      bake(item)
        .then(() => {
          showBake(badge, bakedSkin(skins, item));
          showBakeButton(bakeButton, skins, item);
        })
        .catch(status.reportFailure),
    );
    const list = skinList(item, () => showBakeButton(bakeButton, skins, item));
    return [make('div', { className: 'skin-row' }, [list, upscale, bakeButton, badge])];
  }
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
    const entries = item.instance.sequences.map((s, i) => {
      const button = make('button', { type: 'button', textContent: s.name });
      button.dataset.sequence = String(i);
      // The menu stays open: the next pick is one click away.
      button.addEventListener('click', () => {
        if (loopChoice) scene.loopSequence(item, i);
        else scene.playOnce(item, i);
        markPlaying();
      });
      return make('li', {}, [button]);
    });
    const title = make('div', { className: 'title', textContent: item.source ? item.source.record.name : (item.path.split('\\').pop() ?? item.path) });
    const loop = make('input', { type: 'checkbox', className: 'loop', checked: loopChoice });
    loop.addEventListener('change', () => {
      loopChoice = loop.checked;
    });
    const loopLabel = make('label', { className: 'loop-choice', title: 'checked: the animation loops; unchecked: it plays once, then idle' }, [loop, 'loop']);
    const choices: HTMLElement[] = [loopLabel, ...skinRow(item)];
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

  /** Show the open menu's controls as the choices are now (changed by Ctrl+L, or by an edit of the scene). */
  function refresh(): void {
    const item = menuItem();
    if (!item || !menu) return;
    const loop = find(menu.node, 'input.loop', HTMLInputElement);
    if (loop) loop.checked = loopChoice;
    const choice = find(menu.node, 'button.skin-choice .skin-label', HTMLSpanElement);
    if (choice) choice.textContent = skinLabel(item.skin);
    const button = find(menu.node, 'button.skin-bake', HTMLButtonElement);
    if (button) showBakeButton(button, skins, item);
    const badge = find(menu.node, 'span.skin-baked', HTMLSpanElement);
    if (badge) showBake(badge, bakedSkin(skins, item));
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
    const item = menuItem();
    const button = find(node, 'button.skin-bake', HTMLButtonElement);
    const badge = find(node, 'span.skin-baked', HTMLSpanElement);
    const names = item && button ? skins.choices(item) : [];
    const choice = find(node, 'button.skin-choice', HTMLButtonElement);
    return {
      item: menu.itemId,
      entries: entryButtons(node).map((b) => b.textContent),
      // The marked entries (exactly one while an animation plays).
      playing: [...node.querySelectorAll('button.playing')].map((b) => b.textContent),
      loop: find(node, 'input.loop', HTMLInputElement)?.checked ?? false,
      skins:
        item && button
          ? {
              value: item.skin,
              label: choice?.textContent ?? '',
              // The choice holds a skin icon (R-VIEW-137). Its arrow and look are an operator check.
              dropdown: Boolean(choice?.querySelector('.skin-icon svg')),
              choices: names,
              rows: [...names.map((name) => ({ name, label: skinLabel(name), icons: iconsOf(name) })), { name: '', label: 'Add New Skin…', icons: [] }],
              bake: button.textContent,
              bakeDisabled: button.disabled,
              badge: badge && !badge.hidden ? badge.textContent : null,
            }
          : null,
    };
  }

  return { item: menuItem, itemId: () => (menu ? menu.itemId : null), open, close, markPlaying, refresh, toggleLoop, loop: () => loopChoice, state };
}
