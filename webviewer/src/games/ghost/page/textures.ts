// The Ghost texture window: what a model draws with, in a movable window
// over the view (SPEC-VIEWER-GHOST 8). It opens on a double-click on a
// gallery row, an instance row or an instance in the view. One card per
// material the model's groups use: its shader, how it is drawn or why
// not, its texture file, and that texture decoded in the page (colour,
// and alpha when the alpha is not one value).

import type { GameContext, WindowPlace } from '../../../page/core/context';
import { decodeDds, type DecodedTexture } from '../../../page/core/ddsdecode';
import { make, messageOf } from '../../../page/core/dom';
import type { Item } from '../../../page/core/types';
import { nodLooks, type NodLook } from '../../../formats/nod/looks';
import { GHOST } from './game';

const MARGIN = 16;
const TOP = 48; // below the view tools
const SIZE = [760, 620] as const;

/** One card of the window: a material and the groups that use it. */
export interface MaterialCard {
  material: string;
  shader: string;
  kind: string | null;
  undrawn: string | null;
  twoSided: boolean;
  groups: number[];
  triangles: number;
  texture: string | null;
  /** The decoded texture; null when there is none or it failed (then `failed` says why). */
  decoded: Omit<DecodedTexture, 'planes'> & { planes: string[] } | null;
  failed: string | null;
}

export interface GhostTextureWindow {
  openTexturesFor(category: string, id: string): Promise<void>;
  openTexturesOf(item: Item): Promise<void>;
  /** For the tests: open, whose textures, the state of the read, the cards. */
  ghostTextureWindow(): { open: boolean; file: string | null; dataset: string | null; state: string; cards: MaterialCard[] };
}

/** The groups' looks, one card per material, in the order the groups first use it. */
function cardsOf(looks: readonly NodLook[]): MaterialCard[] {
  const cards = new Map<string, MaterialCard>();
  for (const look of looks) {
    const card = cards.get(look.material);
    if (card) {
      card.groups.push(look.group);
      card.triangles += look.triangles;
      continue;
    }
    cards.set(look.material, { material: look.material, shader: look.shader, kind: look.kind, undrawn: look.undrawn, twoSided: look.twoSided, groups: [look.group], triangles: look.triangles, texture: look.texture, decoded: null, failed: null });
  }
  return [...cards.values()];
}

/** How a card's material is drawn, in words. */
function drawnAs(card: MaterialCard): string {
  if (card.kind !== null) return `drawn ${card.kind}${card.twoSided ? ', both sides' : ''}`;
  return card.undrawn !== null ? `not drawn: ${card.undrawn.slice(card.material.length + 2)}` : 'not drawn (hidden by its shader)';
}

export function installGhostTextures(context: GameContext): GhostTextureWindow {
  const { ui, render, api } = context;
  const list = make('div', { id: 'ghost-texture-list' });
  const win = ui.floatingWindow({ id: 'ghost-texture-window', title: 'textures' });
  win.body.append(list);
  list.tabIndex = -1;
  list.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') win.close();
  });
  let shown: { file: string; dataset: string } | null = null;
  let cards: MaterialCard[] = [];
  /** 'none', 'loading', 'done', or 'failed: <why>'. */
  let state = 'none';
  /** Counts the opens, so a slow read for an earlier one is dropped. */
  let turn = 0;
  let urls: string[] = [];

  function firstPlace(): WindowPlace {
    const left = render.visibleRect().left + MARGIN;
    return { left, top: TOP, width: Math.min(SIZE[0], innerWidth - left - MARGIN), height: Math.min(SIZE[1], innerHeight - TOP - MARGIN) };
  }

  function cardNode(card: MaterialCard, images: DecodedTexture | null): HTMLElement {
    const facts = [card.shader ? `shader ${card.shader}` : 'no shader', drawnAs(card), `groups ${card.groups.join(', ')} · ${card.triangles} triangles`, card.texture ?? 'no texture file'];
    if (images) facts.push(`${images.format} · ${images.size[0]}×${images.size[1]}`);
    if (card.failed) facts.push(`texture not read: ${card.failed}`);
    const pictures = images ? images.planes.map((p) => make('figure', { className: p.plane }, [make('img', { src: p.image, alt: `${card.material} ${p.plane}` }), make('figcaption', { textContent: p.plane })])) : [];
    const node = make('section', { className: `card${card.kind === null ? ' undrawn' : ''}` }, [make('div', { className: 'name', textContent: card.material }), ...facts.map((f) => make('div', { className: 'fact', textContent: f })), make('div', { className: 'pictures' }, pictures)]);
    node.dataset.material = card.material;
    return node;
  }

  async function openTextures(file: string, dataset: string, name: string): Promise<void> {
    win.title.textContent = `textures · ${name}`;
    win.open(firstPlace());
    if (shown && shown.file === file && shown.dataset === dataset && state === 'done') return;
    shown = { file, dataset };
    const mine = ++turn;
    for (const url of urls) URL.revokeObjectURL(url);
    urls = [];
    cards = [];
    list.replaceChildren(make('div', { className: 'fact', textContent: 'reading…' }));
    state = 'loading';
    try {
      const model = await render.loadModel(api.modelUrl(file, dataset, GHOST), api.pathSolver(dataset, GHOST));
      if (!model) throw new Error(`cannot load ${file}`);
      const found = cardsOf(nodLooks(model));
      const nodes: HTMLElement[] = [];
      for (const card of found) {
        let images: DecodedTexture | null = null;
        if (card.texture !== null) {
          await decodeDds(String(api.pathSolver(dataset, GHOST)(card.texture)), card.texture, urls).then(
            (decoded) => {
              images = decoded;
              card.decoded = { ...decoded, planes: decoded.planes.map((p) => p.plane) };
            },
            (error: unknown) => {
              card.failed = messageOf(error);
            },
          );
        }
        if (mine !== turn) return;
        nodes.push(cardNode(card, images));
      }
      cards = found;
      list.replaceChildren(...nodes);
      state = 'done';
    } catch (error) {
      if (mine === turn) {
        state = `failed: ${messageOf(error)}`;
        list.replaceChildren(make('div', { className: 'fact', textContent: state }));
      }
      throw error;
    }
  }

  async function openTexturesFor(category: string, id: string): Promise<void> {
    const dataset = api.requireDataset(api.currentDataset(GHOST), GHOST);
    const record = await api.record(category, id, dataset, GHOST);
    if (!record.file) throw new Error(`${record.name} has no model file`);
    return openTextures(record.file, dataset, record.name);
  }

  function openTexturesOf(item: Item): Promise<void> {
    const name = item.source ? item.source.record.name : (item.path.split('/').pop() ?? item.path);
    return openTextures(item.path, item.dataset, name);
  }

  return {
    openTexturesFor,
    openTexturesOf,
    ghostTextureWindow: () => ({ open: win.isOpen, file: shown ? shown.file : null, dataset: shown ? shown.dataset : null, state, cards: cards.map((c) => ({ ...c, groups: [...c.groups] })) }),
  };
}
