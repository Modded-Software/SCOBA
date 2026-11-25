// The skin editor (SPEC-VIEWER 17.6): a floating window on one owner and
// one skin. Left, the owner's textures; right, the tiles of the chosen one
// (core/tiles.ts, the same as the texture window's): In game, the original,
// each variant, the open requests, and Upscale Texture. A click on a tile
// picks it and changes nothing else (R-VIEW-133). The picks are kept per
// texture; Save to Skin… asks the target and shows each change
// (actions.ts), Revert Changes drops them. The header has Save New Skin As…
// and Discard New Skin for New Skin, Rename Skin and Delete Skin for a saved
// skin; each asks first. Every change goes through core/skins.ts, so each
// instance that shows the skin follows without a reload.

import { NEW_SKIN, ORIGINAL, ORIGINAL_SKIN, skinLabel, textureRoutes, type OwnerState, type TexturesHead, type TextureState } from '../../../shared/textures';
import type { FeatureContext } from '../../core/context';
import { make, messageOf } from '../../core/dom';
import type { Item } from '../../core/types';
import { createPreviews } from '../../core/previews';
import { inGameOf, textureTiles, type TileState } from '../../core/tiles';
import type { SkinActions } from './actions';

export interface EditorState {
  open: boolean;
  owner: string | null;
  skin: string | null;
  /** The header's buttons. */
  buttons: string[];
  /** The header buttons that are red (R-VIEW-136). */
  danger: string[];
  /** Why Delete Skin is disabled; empty: it is not. */
  deleteBlocked: string;
  /** Whether there is a name box or a Copy button (there is none, R-VIEW-118). */
  nameBox: boolean;
  textures: string[];
  selected: string | null;
  tiles: TileState[];
  /** The picks that differ from the skin, by asset (R-VIEW-133). */
  picks: Record<string, string>;
  /** The draft bar's text and whether it shows. */
  draft: { shown: boolean; text: string };
  error: string;
}

export interface SkinEditor {
  open(item: Item, skin: string): Promise<void>;
  state(): EditorState;
}

export function createEditor({ ui, skins, events, status, api }: Pick<FeatureContext, 'ui' | 'skins' | 'events' | 'status' | 'api'>, actions: SkinActions, upscaleTexture: (game: string, dataset: string, asset: string) => Promise<void>): SkinEditor {
  const win = ui.floatingWindow({ id: 'skin-editor', title: 'Skin' });
  const previews = createPreviews();
  const name = make('span', { className: 'skin-name' });
  const save = make('button', { className: 'skin-save-button', textContent: 'Save New Skin As…', title: 'Keep New Skin under a name' });
  const discard = make('button', { className: 'skin-discard danger', textContent: 'Discard New Skin', title: 'Delete New Skin; its instances show Original' });
  const rename = make('button', { className: 'skin-rename', textContent: 'Rename Skin', title: 'Give this skin another name' });
  const remove = make('button', { className: 'skin-delete danger', textContent: 'Delete Skin' });
  const error = make('div', { className: 'skin-error failure' });
  const list = make('div', { className: 'skin-textures' });
  const tiles = make('div', { className: 'skin-tiles' });
  const count = make('span', { className: 'draft-count' });
  const saveTo = make('button', { className: 'primary skin-draft-save', textContent: 'Save to Skin…', title: 'Choose the skin, see each change, then save the picks' });
  const revert = make('button', { className: 'skin-draft-revert', textContent: 'Revert Changes', title: 'Drop the picks; nothing was saved' });
  const bar = make('div', { className: 'skin-draft', hidden: true }, [count, revert, saveTo]);
  const head = make('div', { className: 'skin-head' }, [name, save, discard, rename, remove]);
  win.body.append(head, error, make('div', { className: 'skin-panes' }, [list, make('div', { className: 'skin-right' }, [bar, tiles])]));

  let item: Item | null = null;
  let skin = ORIGINAL_SKIN;
  let owner: OwnerState | null = null;
  let states = new Map<string, TextureState>();
  let headInfo: TexturesHead = { sizes: [], models: [], limits: [] };
  let selected: string | null = null;
  let shownTiles: TileState[] = [];
  /** The picks, by asset: only those that differ from what the skin names (R-VIEW-133). */
  const picks = new Map<string, string>();

  /** What the skin names for a texture; Original names nothing. */
  const named = (asset: string): string => (skin === ORIGINAL_SKIN ? ORIGINAL : (owner?.skins.find((one) => one.name === skin)?.textures[asset] ?? ORIGINAL));

  /** The URL of what a variant id shows: its file, or the original. */
  function urlOf(asset: string, variant: string): string {
    const found = states.get(asset)?.variants.find((one) => one.id === variant);
    if (!item || variant === ORIGINAL || !found) return api.assetUrl('texture', asset, item?.dataset ?? null, item?.game);
    return textureRoutes.file(item.game, item.dataset, asset, found.id, found.sha256);
  }

  /** Run a change; a refusal shows its reason and changes nothing (R-VIEW-123). */
  function run(work: () => Promise<unknown>): void {
    error.textContent = '';
    work().catch((failure: unknown) => (error.textContent = messageOf(failure)));
  }

  /** Pick a variant for a texture: it is outlined; no skin and no instance changes (R-VIEW-133). */
  function pick(asset: string, variant: string): void {
    if (variant === named(asset)) picks.delete(asset);
    else picks.set(asset, variant);
    draw();
  }

  function drawTiles(): void {
    tiles.replaceChildren();
    shownTiles = [];
    if (!owner || !selected || !item) return;
    const asset = selected;
    const chosen = picks.get(asset) ?? named(asset);
    const mine = item;
    const made = textureTiles({
      asset,
      state: states.get(asset),
      head: headInfo,
      inGame: inGameOf(asset, states.get(asset), owner),
      originalSize: '',
      preview: (variant) => previews.node(urlOf(asset, variant), `${asset} ${variant}`),
      highlighted: (variant) => variant === chosen,
      click: (variant) => pick(asset, variant),
      upscale: () => run(() => upscaleTexture(mine.game, mine.dataset, asset)),
    });
    shownTiles = made.tiles;
    tiles.append(...made.nodes);
  }

  function draw(): void {
    name.textContent = owner ? `${owner.title} · ${skinLabel(skin)}` : '';
    win.title.textContent = `Skin · ${name.textContent}`;
    save.hidden = discard.hidden = skin !== NEW_SKIN;
    rename.hidden = remove.hidden = skin === NEW_SKIN || skin === ORIGINAL_SKIN;
    // A bake names the skin it was made from: the baked skin is not deleted (R-HD-136).
    remove.disabled = owner?.bake?.skin === skin;
    remove.title = remove.disabled ? 'baked: unbake it or bake another skin first' : 'Delete this skin; its instances show Original';
    bar.hidden = picks.size === 0;
    count.textContent = `${picks.size} ${picks.size === 1 ? 'change' : 'changes'}, not saved`;
    list.replaceChildren();
    for (const asset of owner?.textures ?? []) {
      const row = make('div', { className: `skin-texture${asset === selected ? ' current' : ''}` }, [previews.node(urlOf(asset, ORIGINAL), asset), make('span', { textContent: asset.split('\\').pop() ?? asset, title: asset })]);
      if (picks.has(asset)) row.append(make('span', { className: 'picked-mark', textContent: '●', title: `picked: ${picks.get(asset) ?? ''}, not saved` }));
      row.dataset['asset'] = asset;
      row.addEventListener('click', () => {
        selected = asset;
        draw();
      });
      list.append(row);
    }
    drawTiles();
  }

  async function read(): Promise<void> {
    const mine = item;
    const ownerId = mine ? skins.ownerOf(mine) : null;
    if (!mine || !ownerId) return;
    const found = await skins.readOwner(mine.game, mine.dataset, ownerId);
    if (item !== mine) return;
    owner = found;
    if (!found) throw new Error(`${ownerId} has no textures in ${mine.dataset}`);
    // New Skin may be offered or not made yet; any other skin must be there.
    if (skin !== ORIGINAL_SKIN && skin !== NEW_SKIN && !found.skins.some((one) => one.name === skin)) throw new Error(`${found.owner} has no skin "${skin}"`);
    const body = await skins.states(mine.game, mine.dataset, found.textures);
    if (item !== mine) return;
    headInfo = body;
    states = new Map(body.textures.map((state) => [state.asset, state]));
    // A pick the skin now names is no change any more.
    for (const [asset, variant] of picks) if (variant === named(asset)) picks.delete(asset);
    if (selected === null || !found.textures.includes(selected)) selected = found.textures[0] ?? null;
    draw();
  }

  async function open(on: Item, wanted: string): Promise<void> {
    if (item !== on) previews.clear();
    item = on;
    skin = wanted;
    selected = null;
    picks.clear();
    error.textContent = '';
    win.open({ left: 80, top: 80, width: 760, height: 560 });
    await read();
  }

  /** A header action runs: its own changes are read once it says which skin it left. */
  let acting = false;
  /** Run a header action, then show the skin it left; null: cancelled, the skin stays. */
  function act(work: (on: Item) => Promise<string | null>): void {
    const mine = item;
    if (!mine) return;
    acting = true;
    run(async () => {
      try {
        const next = await work(mine);
        if (next !== null && next !== skin) {
          skin = next;
          picks.clear();
        }
      } finally {
        acting = false;
      }
      await read();
    });
  }
  save.addEventListener('click', () => act((on) => actions.save(on)));
  discard.addEventListener('click', () => act(async (on) => ((await actions.discard(on)) ? ORIGINAL_SKIN : null)));
  rename.addEventListener('click', () => act((on) => actions.rename(on, skin)));
  remove.addEventListener('click', () => act(async (on) => ((await actions.remove(on, skin)) ? ORIGINAL_SKIN : null)));
  // Save to Skin…: on Original the target is New Skin (R-VIEW-127); saved, the picks are dropped.
  saveTo.addEventListener('click', () =>
    act(async (on) => {
      const ownerId = owner?.owner;
      if (!ownerId) return null;
      const into = await actions.saveTo({ game: on.game, dataset: on.dataset, owner: ownerId, item: on.id, picks: [...picks].map(([asset, variant]) => ({ asset, variant })), target: skin === ORIGINAL_SKIN ? NEW_SKIN : skin });
      if (into !== null) picks.clear();
      return into;
    }),
  );
  revert.addEventListener('click', () => {
    picks.clear();
    draw();
  });

  events.on('textures-changed', ({ game, dataset }) => {
    if (!acting && win.isOpen && item && item.game === game && item.dataset === dataset) read().catch(status.reportFailure);
  });

  function state(): EditorState {
    const header = [save, discard, rename, remove].filter((button) => !button.hidden);
    const nameBox = head.querySelector('input') !== null || [...head.querySelectorAll('button')].some((button) => /copy/i.test(button.textContent));
    return {
      open: win.isOpen,
      owner: owner?.owner ?? null,
      skin: item ? skin : null,
      buttons: header.map((button) => button.textContent),
      danger: header.filter((button) => button.classList.contains('danger')).map((button) => button.textContent),
      deleteBlocked: remove.disabled ? remove.title : '',
      nameBox,
      textures: owner?.textures ?? [],
      selected,
      tiles: [...shownTiles],
      picks: Object.fromEntries(picks),
      draft: { shown: !bar.hidden, text: count.textContent },
      error: error.textContent,
    };
  }

  return { open, state };
}
