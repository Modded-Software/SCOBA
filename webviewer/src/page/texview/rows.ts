// A row of the texture page's list (SPEC-VIEWER 17.3): the thumbnail with
// the users badge (R-VIEW-160, 161), the name, and the badges PICKED, HD,
// EDIT, PKG, and FAILED or QUEUED. main.ts
// decides which entries are listed and what a click on a row shows.

import { make } from '../core/dom';
import { usersBadge, type TextureState } from '../../shared/textures';
import { hasEdit } from './edits';

/** What a row reads of an entry of the list. */
export interface Listed {
  asset: string | null;
  texture: string;
  plane: string;
  format: string;
  size: readonly [number, number];
  /** The original's picture, in the entry's plane. */
  image: string;
}

/** What the page knows of a row's entry now. */
export interface RowFacts {
  /** The entry's place among all entries. */
  index: number;
  /** It is the entry shown. */
  current: boolean;
  /** Its state from the service; undefined: none read. */
  state: TextureState | undefined;
  /** The variant picked for it and not saved; null: none (R-VIEW-133). */
  picked: string | null;
  /** The owner the window is on; null: none. A bake of another owner turns the users badge amber (R-VIEW-161). */
  owner: string | null;
}

/** The text of a users badge with no count: one model file reads the texture, and another owner bakes it. */
export const BAKED_BY_OTHER = 'baked';

/** The thumbnail, with the users badge on its bottom right corner when the state gives one (R-VIEW-160). */
function thumbnail(item: Listed, state: TextureState | undefined, owner: string | null): HTMLElement {
  const picture = make('img', { decoding: 'async', alt: '', src: item.image });
  const found = state ? usersBadge(state, owner) : null;
  if (!found) return picture;
  const mark = make('span', { className: `users-badge${found.sharedBake ? ' shared-bake' : ''}`, textContent: found.count === null ? BAKED_BY_OTHER : String(found.count), title: found.title });
  return make('span', { className: 'thumb' }, [picture, mark]);
}

/** A badge; `title`: what its hover says, when it says something. */
const badge = (name: string, text: string, title?: string): HTMLElement => make('span', { className: `badge ${name}`, textContent: text, ...(title === undefined ? {} : { title }) });

/** The row of one entry. */
export function listRow(item: Listed, { index, current, state, picked, owner }: RowFacts): HTMLElement {
  const meta = make('div', { className: 'meta' });
  const made = state ? state.variants.map((variant) => variant.id) : [];
  if (picked !== null) meta.append(badge('picked', 'PICKED', `picked: ${picked}, not saved`));
  if (made.length) meta.append(badge('hd', 'HD', made.join(', ')));
  if (item.asset !== null && hasEdit(item.asset)) meta.append(badge('edit', 'EDIT'));
  if (state?.packaged?.held) meta.append(badge('packaged', 'PKG'));
  if (state && Object.values(state.requests).some((request) => request.state === 'failed')) meta.append(badge('failed', 'FAILED'));
  else if (state && Object.keys(state.requests).length) meta.append(badge('running', 'QUEUED'));
  meta.append(`${item.plane} · ${item.size.join('x')} · ${item.format}`);
  const text = make('div', { className: 'text' }, [make('div', { className: 'name', textContent: item.texture }), meta]);
  const row = make('div', { className: `row${current ? ' current' : ''}`, title: state?.users.join(', ') ?? '' }, [thumbnail(item, state, owner), text]);
  row.dataset['index'] = String(index);
  return row;
}
