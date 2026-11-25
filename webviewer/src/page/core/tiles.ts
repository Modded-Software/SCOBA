// The tiles of one texture in the texture window (SPEC-VIEWER 17.6.1,
// R-VIEW-131, R-VIEW-132). In game first: the file the game shows after a
// build; then the original, each variant, the open requests, and Upscale
// Texture last (R-VIEW-129). A tile with a number off the ok band has an
// info mark with a tooltip (R-VIEW-135). A click picks (R-VIEW-133); the
// "Include in preview" box puts the tile in the picture (R-VIEW-130). A
// request tile shows its stage, a bar and its time; a failed one offers Ask
// Again and Open Log (R-VIEW-145, 146). A variant tile has a red trash
// (R-VIEW-147).

import type { EditStateName } from '../../shared/edits';
import { bandOf, isUsable, ORIGINAL, shownOrder, type Band, type OwnerState, type TextureRequest, type TexturesHead, type TextureNumber, type TextureState, type TextureVariant } from '../../shared/textures';
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
  /** Its "Include in preview" box is checked; null: the tile has none. */
  included: boolean | null;
  /** Its Edit Texture button: why it is disabled (empty: it is not), and its dot; null: the tile has none. */
  edit: { disabled: string; dot: 'edited' | 'other' | null } | null;
  /** A request tile's progress (R-VIEW-145): its line and its bar's fill, 0 to 1; null: no request tile. */
  progress: { line: string; fraction: number } | null;
  /** A request tile's buttons, by their text (R-VIEW-146). */
  actions: string[];
  /** Its trash: why it is disabled (empty: it is not); null: the tile has none (R-VIEW-147). */
  trash: { disabled: string } | null;
}

/** The fields of a tile that is no request and has no trash yet. */
const plain = (): Pick<TileState, 'progress' | 'actions' | 'trash'> => ({ progress: null, actions: [], trash: null });

/** What a request tile does (R-VIEW-146). */
export interface TileRequests {
  /** Ask for the request's own variant again, with no dialog. */
  retry(recipe: string, variant: string): void;
  /** That call is out: the button waits. */
  asking(recipe: string): boolean;
  /** The URL of the request's log. */
  log(recipe: string): string;
}

/** The trash of each variant tile (R-VIEW-147). */
export interface TileRemoval {
  /** Why the variant cannot be removed now; empty: it can. */
  refusal(variant: string): string;
  /** A click on an enabled trash: the caller asks first. */
  remove(variant: string): void;
}

const STAGE: Record<TextureRequest['state'], string> = { queued: 'Queued', upscaling: 'Upscaling', encoding: 'Encoding', failed: 'Failed' };

/**
 * How far a request is (SPEC-VIEWER 17.6.1): its line and the bar's fill.
 * Steps count equally; within an upscaling step the planes whose job is done count.
 */
export function requestProgress(request: TextureRequest): { line: string; fraction: number } {
  const steps = Math.max(1, request.steps);
  const step = `step ${request.step} of ${request.steps}`;
  if (request.state === 'failed') return { line: `Failed: ${request.reason}`, fraction: 1 };
  if (request.state === 'queued') return { line: `Queued · ${step}`, fraction: (request.step - 1) / steps };
  if (request.state === 'encoding') return { line: `Encoding · ${step}`, fraction: request.step / steps };
  const within = request.planes > 0 ? request.done / request.planes : 0;
  return { line: `${STAGE.upscaling} · ${step} · planes ${request.done} of ${request.planes}`, fraction: (request.step - 1 + within) / steps };
}

/** A time a request has run, as "1 min 05 s", "12 s" or "1 h 02 min". */
export function elapsedText(seconds: number): string {
  const whole = Math.max(0, Math.floor(seconds));
  if (whole < 60) return `${whole} s`;
  if (whole < 3600) return `${Math.floor(whole / 60)} min ${String(whole % 60).padStart(2, '0')} s`;
  return `${Math.floor(whole / 3600)} h ${String(Math.floor((whole % 3600) / 60)).padStart(2, '0')} min`;
}

/** Count the time on every request tile in or below `roots` once more; `now` in seconds since 1970. */
export function tickElapsed(roots: Iterable<ParentNode>, now: number): void {
  for (const root of roots) for (const line of root.querySelectorAll<HTMLElement>('.tile-elapsed[data-since]')) line.textContent = `running ${elapsedText(now - Number(line.dataset['since']))}`;
}

/** The Edit Texture buttons of a texture's tiles (SPEC-PHOTOCRAFT 9.1). */
export interface TileEdits {
  /** Why the texture cannot be edited now; empty: it can. */
  disabled: string;
  /** The state of the session of a variant; null: it has none. */
  session(variant: string): EditStateName | null;
  /** A click on the button of a tile that shows this variant. */
  open(variant: string): void;
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
  click(variant: string): void;
  /**
   * The "Include in preview" box of each tile that shows a variant (R-VIEW-130):
   * whether the variant is in the picture, and a change of the box. Absent: no boxes.
   * The original is always the picture's left side: its box is checked and fixed.
   */
  compare?: { included(variant: string): boolean; include(variant: string, on: boolean): void };
  /** The Edit Texture button of each tile that shows a variant; absent: no buttons (no install, no service). */
  edit?: TileEdits;
  /** Ask Again and Open Log of a failed request; absent: none. */
  requests?: TileRequests;
  /** The trash of each variant tile; absent: none. */
  removal?: TileRemoval;
  /** The Upscale Texture tile; null: none. */
  upscale: (() => void) | null;
}

const rounded = (value: number | null): string => (value === null ? 'none' : String(Math.round(value * 100) / 100));

/** The lines of an info mark: what is off, each with its number, bound and what a miss means. */
function offLines(numbers: readonly TextureNumber[], head: TexturesHead): string[] {
  return numbers
    .filter((number) => number.band === 'near' || number.band === 'problem')
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
  const variants = shownOrder(input.state?.variants ?? []);
  const sizeOf = (variant: string): string => (variant === ORIGINAL ? input.originalSize : String(variants.find((one) => one.id === variant)?.size ?? ''));

  function add(made: TileState, label: string, lines: readonly (string | Node)[], extra: { preview?: HTMLElement | null; className?: string; numbers?: readonly TextureNumber[]; off?: readonly string[] } = {}): HTMLElement {
    // The thumbnail holds the info mark at its top right corner.
    const thumb = make('div', { className: 'tile-thumb' }, [extra.preview ?? make('span', { className: 'tex-preview none' })]);
    if (extra.off?.length) thumb.append(infoMark(extra.off));
    const node = make('div', { className: `skin-tile ${made.kind}${made.highlighted ? ' highlighted' : ''}${made.band ? ` band-${made.band}` : ''}${extra.className ? ` ${extra.className}` : ''}` }, [
      thumb,
      make('div', { className: 'tile-id', textContent: label }),
      ...lines.map((line) => (typeof line === 'string' ? make('div', { className: 'tile-size', textContent: line }) : line)),
    ]);
    if (extra.numbers?.length) node.append(numbersLine(extra.numbers));
    if (made.note) node.append(make('div', { className: 'tile-note', textContent: made.note }));
    node.dataset['tile'] = made.id;
    node.dataset['variant'] = made.variant;
    nodes.push(node);
    tiles.push(made);
    return node;
  }
  /** The pencil at the bottom left of a tile's preview. A click on it is not a click on the tile: nothing is picked (R-PC-23). */
  function editButton(edit: TileEdits, variant: string): { button: HTMLElement; dot: 'edited' | 'other' | null } {
    const session = edit.session(variant);
    const dot = session === null ? null : session === 'edited' ? 'edited' : 'other';
    const button = make('button', { type: 'button', className: `tile-edit${edit.disabled ? ' off' : ''}`, title: edit.disabled ? `Edit Texture: ${edit.disabled}` : 'Edit Texture' }, ['✎']);
    button.setAttribute('aria-disabled', String(Boolean(edit.disabled)));
    if (dot) button.append(make('span', { className: `tile-edit-dot ${dot}`, title: `an edit session: ${session}` }));
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      if (!edit.disabled) edit.open(variant);
    });
    return { button, dot };
  }
  /** The red trash at the bottom right of a variant's preview. A click on it picks nothing. */
  function trashButton(removal: TileRemoval, variant: string, disabled: string): HTMLElement {
    const button = make('button', { type: 'button', className: `tile-trash danger${disabled ? ' off' : ''}`, title: disabled ? `Delete Variant: ${disabled}` : 'Delete Variant' }, ['🗑']);
    button.setAttribute('aria-disabled', String(Boolean(disabled)));
    button.addEventListener('click', (event) => {
      event.stopPropagation();
      if (!disabled) removal.remove(variant);
    });
    return button;
  }
  /** A tile that shows a variant: a click picks it; its box puts it in the picture or takes it out. */
  function clickable(node: HTMLElement, variant: string): void {
    node.addEventListener('click', () => input.click(variant));
    const compare = input.compare;
    const made = tiles[tiles.length - 1];
    if (made && input.edit) {
      const { button, dot } = editButton(input.edit, variant);
      node.querySelector('.tile-thumb')?.append(button);
      made.edit = { disabled: input.edit.disabled, dot };
    }
    if (made?.kind === 'variant' && input.removal) {
      const disabled = input.removal.refusal(variant);
      node.querySelector('.tile-thumb')?.append(trashButton(input.removal, variant, disabled));
      made.trash = { disabled };
    }
    if (!compare || !made) return;
    const fixed = variant === ORIGINAL;
    const box = make('input', { type: 'checkbox', className: 'tile-include', checked: fixed || compare.included(variant), disabled: fixed });
    box.addEventListener('change', () => compare.include(variant, box.checked));
    const label = make('label', { className: 'tile-include-row', title: fixed ? 'The original is always the left side of the picture' : 'Show this variant in the picture beside the original' }, [box, 'Include in preview']);
    // The box is not a click on the tile: it does not pick.
    label.addEventListener('click', (event) => event.stopPropagation());
    // First in the tile, above the preview.
    node.prepend(label);
    made.included = box.checked;
  }

  // In game (R-VIEW-131): what the game holds; no skin name.
  const game = input.inGame;
  const note = game.baked && !game.held ? NOT_PACKAGED : '';
  const sized = sizeOf(game.variant);
  clickable(
    add({ id: IN_GAME_TILE, kind: 'in-game', variant: game.variant, highlighted: input.highlighted(game.variant), band: null, info: '', note, included: null, edit: null, ...plain() }, 'In game', [`${game.variant}${sized ? ` · ${sized}` : ''}`, game.baked ? 'baked' : 'not baked'], { preview: input.preview(game.variant) }),
    game.variant,
  );
  clickable(add({ id: ORIGINAL, kind: 'original', variant: ORIGINAL, highlighted: input.highlighted(ORIGINAL), band: null, info: '', note: '', included: null, edit: null, ...plain() }, 'Original', [input.originalSize], { preview: input.preview(ORIGINAL) }), ORIGINAL);
  for (const variant of variants) clickable(variantTile(variant), variant.id);

  function variantTile(variant: TextureVariant): HTMLElement {
    const band = bandOf(variant);
    const off = offLines(variant.numbers, input.head);
    const from = `from ${variant.input} · ${Object.values(variant.models).filter((model): model is string => model !== null).join(', ') || 'kept'}`;
    const flags = `${variant.size}${variant.stale ? ' · stale' : ''}${isUsable(variant) ? '' : ' · blocked'}`;
    const className = `${variant.stale ? 'stale' : ''}${isUsable(variant) ? '' : ' blocked'}`.trim();
    return add({ id: variant.id, kind: 'variant', variant: variant.id, highlighted: input.highlighted(variant.id), band, info: off.join('\n'), note: '', included: null, edit: null, ...plain() }, variant.id, [flags, from], { preview: input.preview(variant.id), numbers: variant.numbers, off, className });
  }

  // Each open request: its stage, a bar, its time, and for a failure Ask Again and Open Log (R-VIEW-145, 146).
  for (const [recipe, request] of Object.entries(input.state?.requests ?? {})) {
    const progress = requestProgress(request);
    const failed = request.state === 'failed';
    const fill = make('span', { className: 'tile-progress-fill' });
    fill.style.width = `${Math.round(progress.fraction * 100)}%`;
    const bar = make('div', { className: `tile-progress${failed ? ' failed' : ' running'}`, title: progress.line }, [fill]);
    bar.setAttribute('role', 'progressbar');
    bar.setAttribute('aria-valuemin', '0');
    bar.setAttribute('aria-valuemax', '100');
    bar.setAttribute('aria-valuenow', String(Math.round(progress.fraction * 100)));
    const lines: Node[] = [make('div', { className: 'tile-stage', textContent: progress.line, title: progress.line }), bar];
    if (!failed && request.since !== null) {
      const time = make('div', { className: 'tile-elapsed' });
      time.dataset['since'] = String(request.since);
      lines.push(time);
    }
    const actions: string[] = [];
    const tools = input.requests;
    if (failed && tools) {
      const row = make('div', { className: 'tile-actions' });
      if (request.variant) {
        const asking = tools.asking(recipe);
        const again = make('button', { type: 'button', className: 'tile-retry', textContent: asking ? 'Asking…' : 'Ask Again', disabled: asking, title: `Ask for ${request.variant} again, with the same input, model and size` });
        again.addEventListener('click', () => tools.retry(recipe, request.variant));
        row.append(again);
        actions.push('Ask Again');
      }
      row.append(make('a', { className: 'tile-log', textContent: 'Open Log', href: tools.log(recipe), target: '_blank', rel: 'noopener', title: 'The log of this request, in a new tab' }));
      actions.push('Open Log');
      lines.push(row);
    }
    const node = add({ id: recipe, kind: 'request', variant: recipe, highlighted: false, band: null, info: request.reason, note: '', included: null, edit: null, progress, actions, trash: null }, recipe, lines, { className: failed ? 'failure' : '' });
    node.dataset['recipe'] = recipe;
    node.dataset['state'] = request.state;
  }
  tickElapsed(nodes, Date.now() / 1000);

  // Upscale Texture: a tile as large as a preview tile (R-VIEW-129).
  const upscale = input.upscale;
  if (upscale) {
    const button = make('button', { type: 'button', className: 'skin-tile upscale skin-tile-upscale', title: 'Make a variant of this texture: an input, a model and a size' }, [make('span', { className: 'tile-plus', textContent: '+' }), make('div', { className: 'tile-id', textContent: 'Upscale Texture' })]);
    button.addEventListener('click', () => upscale());
    nodes.push(button);
    tiles.push({ id: 'upscale', kind: 'upscale', variant: '', highlighted: false, band: null, info: '', note: '', included: null, edit: null, ...plain() });
  }
  return { nodes, tiles };
}
