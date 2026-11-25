// A row of the texture page's list (SPEC-VIEWER 17.3): the thumbnail, the
// name, and the badges PICKED, HD, EDIT, PKG, and FAILED or QUEUED. main.ts
// decides which entries are listed and what a click on a row shows.

import { make } from '../core/dom';
import type { TextureState } from '../../shared/textures';
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
}

/** A badge; `title`: what its hover says, when it says something. */
const badge = (name: string, text: string, title?: string): HTMLElement => make('span', { className: `badge ${name}`, textContent: text, ...(title === undefined ? {} : { title }) });

/** The row of one entry. */
export function listRow(item: Listed, { index, current, state, picked }: RowFacts): HTMLElement {
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
  const row = make('div', { className: `row${current ? ' current' : ''}`, title: state?.users.join(', ') ?? '' }, [make('img', { decoding: 'async', alt: '', src: item.image }), text]);
  row.dataset['index'] = String(index);
  return row;
}
