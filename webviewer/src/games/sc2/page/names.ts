// The names "add all" gives the SC2 lists as landmarks: a phrase from the
// search and the filters (PageGame.listName).

import { DOODADS, UNITS } from './records';

export interface UnitQuery {
  q: string;
  race: string;
  kind: string;
  family?: string;
}

export interface DoodadQuery {
  q: string;
  type: string;
  tileset: string;
}

// Kinds as a plural noun; any other kind takes an "s".
const PLURAL: Record<string, string> = { Hero: 'Heroes', Other: 'Other Units', Unit: 'Units' };

/**
 * A human readable name for the unit list filters, read like a phrase:
 * race, family, kind (plural), then the search, e.g. 'Terran Campaign
 * Units', 'Zerg Melee Units "drone"', 'Structures (no family)'.
 */
export function filterName(query: UnitQuery): string {
  const words = [];
  if (query.race) words.push(query.race);
  if (query.family) words.push(query.family);
  words.push(query.kind ? (PLURAL[query.kind] ?? `${query.kind}s`) : 'Units');
  if (!query.race && !query.family && !query.kind && !query.q && query.family !== '') words.unshift('All');
  if (query.family === '') words.push('(no family)');
  if (query.q) words.push(`"${query.q}"`);
  return words.join(' ');
}

/**
 * A doodad list's landmark name, read like a phrase: terrain set, type,
 * "Doodads", then the search, e.g. 'Char Environment Doodads "rock"'.
 */
export function doodadFilterName(query: DoodadQuery): string {
  const words = [];
  if (query.tileset) words.push(query.tileset);
  if (query.type) words.push(query.type);
  words.push('Doodads');
  if (!query.tileset && !query.type && !query.q) words.unshift('All');
  if (query.q) words.push(`"${query.q}"`);
  return words.join(' ');
}

/** The landmark name of a list query of a category. */
export function listName(category: string, query: Readonly<Record<string, string>>): string {
  const q = query['q'] ?? '';
  if (category === UNITS) {
    const family = query['family'];
    return filterName({ q, race: query['race'] ?? '', kind: query['kind'] ?? '', ...(family === undefined ? {} : { family }) });
  }
  if (category === DOODADS) return doodadFilterName({ q, type: query['type'] ?? '', tileset: query['tileset'] ?? '' });
  return q ? `${category} "${q}"` : `All ${category}`;
}
