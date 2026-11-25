// The tiles of one texture (SPEC-VIEWER 17.6.1): the same in the skin editor
// and in the texture window (R-VIEW-131, R-VIEW-132). In game first: the
// file the game shows after a build; then the original, each variant, the
// open requests, and Upscale Texture last (R-VIEW-129). A tile with a number
// off the ok band has an info mark with a tooltip (R-VIEW-135). What a click
// does is the window's (R-VIEW-133).

import { bandOf, isUsable, ORIGINAL, type Band, type OwnerState, type TexturesHead, type TextureNumber, type TextureState, type TextureVariant } from '../../shared/textures';
import { make } from './dom';

/** The id of the first tile. */
export const IN_GAME_TILE = 'in-game';
/** The first line of every tooltip of an info mark (R-VIEW-135). */
export const BAND_LEGEND = 'Amber: near a limit. Red: misses a limit.';
/** The amber line of In game when the package does not hold the bake. */
export const NOT_PACKAGED = 'not in the package yet: build the map';

export type TileKind = 'in-game' | 'original' | 'variant' | 'request' | 'upscale';

/** One tile as the tests read it. */
export interface TileState {
  id: string;
  kind: TileKind;
  /** The variant it shows; for a request, its recipe; for Upscale, empty. */
  variant: string;
  /** It has the blue outline. */
  highlighted: boolean;
  band: Band | null;
  /** The text of its info mark; empty: it has none. */
  info: string;
  /** Its amber line; empty: none. */
  note: string;
}

/** What the game shows for one texture after a build (R-VIEW-131). */
export interface InGame {
  variant: string;
  baked: boolean;
  /** The package holds it as it is. */
  held: boolean;
}

/**
 * In game: the owner's `shows` (its bake, else the bake below, else the original); without an owner,
 * the texture's own bake (a ground texture), else the original. It names no skin.
 */
export function inGameOf(asset: string, state: TextureState | undefined, owner: Pick<OwnerState, 'shows' | 'held' | 'bake' | 'below'> | null): InGame {
  if (owner) {
    const variant = owner.shows[asset] ?? ORIGINAL;
    const baked = owner.bake !== null || owner.below.some((one) => one.bake !== null);
    return { variant, baked, held: owner.held };
  }
  const bake = state?.bake ?? null;
  return { variant: bake ?? ORIGINAL, baked: bake !== null, held: state?.packaged?.held ?? false };
}

export interface TilesInput {
  asset: string;
  state: TextureState | undefined;
  head: TexturesHead;
  inGame: InGame;
  /** The original's size, as "w x h"; empty: not known here. */
  originalSize: string;
  /** The picture of a variant (`original` too); null: none. */
  preview(variant: string): HTMLElement | null;
  /** The variants with the blue outline. */
  highlighted(variant: string): boolean;
  /** A click on a tile that shows a variant. */
  click(variant: string, event: MouseEvent): void;
  /** The Upscale Texture tile; null: none. */
  upscale: (() => void) | null;
}

const rounded = (value: number | null): string => (value === null ? 'none' : String(Math.round(value * 100) / 100));

/** The lines of an info mark: what is off, each with its number, bound and what a miss means. */
function offLines(numbers: readonly TextureNumber[], head: TexturesHead): string[] {
  return numbers
    .filter((number) => number.band !== 'ok')
    .map((number) => `${number.band === 'problem' ? 'Red' : 'Amber'}: ${number.limit} ${rounded(number.value)} against ${number.bound}. ${head.limits.find((one) => one.limit === number.limit)?.info ?? ''}`.trim());
}

/** The info mark "i": the arrow cursor, a tooltip on hover (R-VIEW-135). */
function infoMark(lines: readonly string[]): HTMLElement {
  const tip = make('div', { className: 'tile-tip' }, [make('div', { className: 'tile-legend', textContent: BAND_LEGEND }), ...lines.map((line) => make('div', { textContent: line }))]);
  return make('span', { className: 'tile-info' }, ['i', tip]);
}

function numbersLine(numbers: readonly TextureNumber[]): HTMLElement {
  return make(
    'div',
    { className: 'tile-numbers' },
    numbers.flatMap((number, at) => {
      const one = make('span', { className: `number band-${number.band}`, textContent: `${number.limit} ${rounded(number.value)}`, title: `${number.limit}: ${rounded(number.value)} against ${number.bound}` });
      one.dataset['band'] = number.band;
      return at ? [' · ', one] : [one];
    }),
  );
}

/** The tiles of one texture, in order, and their state for the tests. */
export function textureTiles(input: TilesInput): { nodes: HTMLElement[]; tiles: TileState[] } {
  const nodes: HTMLElement[] = [];
  const tiles: TileState[] = [];
  const variants = input.state?.variants ?? [];
  const sizeOf = (variant: string): string => (variant === ORIGINAL ? input.originalSize : String(variants.find((one) => one.id === variant)?.size ?? ''));

  function add(made: TileState, label: string, lines: readonly (string | Node)[], extra: { preview?: HTMLElement | null; className?: string; numbers?: readonly TextureNumber[]; off?: readonly string[] } = {}): HTMLElement {
    const node = make('div', { className: `skin-tile ${made.kind}${made.highlighted ? ' highlighted' : ''}${made.band ? ` band-${made.band}` : ''}${extra.className ? ` ${extra.className}` : ''}` }, [
      extra.preview === undefined ? make('span', { className: 'tex-preview none' }) : (extra.preview ?? make('span', { className: 'tex-preview none' })),
      make('div', { className: 'tile-id', textContent: label }),
      ...lines.map((line) => (typeof line === 'string' ? make('div', { className: 'tile-size', textContent: line }) : line)),
    ]);
    if (extra.numbers?.length) node.append(numbersLine(extra.numbers));
    if (made.note) node.append(make('div', { className: 'tile-note', textContent: made.note }));
    if (extra.off?.length) node.append(infoMark(extra.off));
    node.dataset['tile'] = made.id;
    node.dataset['variant'] = made.variant;
    nodes.push(node);
    tiles.push(made);
    return node;
  }
  const clickable = (node: HTMLElement, variant: string): void => node.addEventListener('click', (event) => input.click(variant, event));

  // In game (R-VIEW-131): what the game holds; no skin name.
  const game = input.inGame;
  const note = game.baked && !game.held ? NOT_PACKAGED : '';
  const sized = sizeOf(game.variant);
  clickable(
    add({ id: IN_GAME_TILE, kind: 'in-game', variant: game.variant, highlighted: input.highlighted(game.variant), band: null, info: '', note }, 'In game', [`${game.variant}${sized ? ` · ${sized}` : ''}`, game.baked ? 'baked' : 'not baked'], { preview: input.preview(game.variant) }),
    game.variant,
  );
  clickable(add({ id: ORIGINAL, kind: 'original', variant: ORIGINAL, highlighted: input.highlighted(ORIGINAL), band: null, info: '', note: '' }, 'Original', [input.originalSize], { preview: input.preview(ORIGINAL) }), ORIGINAL);
  for (const variant of variants) clickable(variantTile(variant), variant.id);

  function variantTile(variant: TextureVariant): HTMLElement {
    const band = bandOf(variant);
    const off = offLines(variant.numbers, input.head);
    const from = `from ${variant.input} · ${Object.values(variant.models).filter((model): model is string => model !== null).join(', ') || 'kept'}`;
    const flags = `${variant.size}${variant.stale ? ' · stale' : ''}${isUsable(variant) ? '' : ' · blocked'}`;
    const className = `${variant.stale ? 'stale' : ''}${isUsable(variant) ? '' : ' blocked'}`.trim();
    return add({ id: variant.id, kind: 'variant', variant: variant.id, highlighted: input.highlighted(variant.id), band, info: off.join('\n'), note: '' }, variant.id, [flags, from], { preview: input.preview(variant.id), numbers: variant.numbers, off, className });
  }

  for (const [recipe, request] of Object.entries(input.state?.requests ?? {})) {
    const line = request.state === 'failed' ? `failed: ${request.reason}` : `${request.state}, step ${request.step} of ${request.steps}`;
    const node = add({ id: recipe, kind: 'request', variant: recipe, highlighted: false, band: null, info: request.reason, note: '' }, recipe, [line], { className: request.state === 'failed' ? 'failure' : '' });
    node.dataset['recipe'] = recipe;
  }

  // Upscale Texture: a tile as large as a preview tile (R-VIEW-129).
  const upscale = input.upscale;
  if (upscale) {
    const button = make('button', { type: 'button', className: 'skin-tile upscale skin-tile-upscale', title: 'Make a variant of this texture: an input, a model and a size' }, [make('span', { className: 'tile-plus', textContent: '+' }), make('div', { className: 'tile-id', textContent: 'Upscale Texture' })]);
    button.addEventListener('click', () => upscale());
    nodes.push(button);
    tiles.push({ id: 'upscale', kind: 'upscale', variant: '', highlighted: false, band: null, info: '', note: '' });
  }
  return { nodes, tiles };
}
