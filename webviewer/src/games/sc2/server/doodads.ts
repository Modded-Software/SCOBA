// The doodad catalog of one dataset: doodads.json (tools/build_doodads.py)
// joined with the model files the server can serve.

import type { Page } from '../../../shared/records';
import { assetKey, byCount, maybeText, num, rank, readCatalog, sortBy, text, texts, type AssetLookup, type CatalogRecord } from './catalog';

interface Doodad {
  readonly id: string;
  readonly name: string;
  readonly type: string;
  readonly tilesets: readonly string[];
  readonly fields: CatalogRecord;
  readonly files: readonly string[];
  readonly editorOnly: boolean;
  readonly text: string;
}

export interface DoodadFacets {
  types: string[];
  tilesets: string[];
}

export interface Doodads {
  readonly size: number;
  readonly withoutFile: number;
  readonly facets: DoodadFacets;
  /** One page of the doodads that match: every query word, the type, and a terrain set that lists it. */
  search(query: string, type: string, tileset: string, offset: number, limit: number): Page<Record<string, unknown>>;
  /** The full record; null when there is none. */
  get(id: string): Record<string, unknown> | null;
}

/**
 * The servable files of a model, one per variation. A model with
 * VariationCount n is stored as name_00.m3 .. name_(n-1).m3; one without
 * variations as name.m3 (some as name_00.m3 only).
 */
function variationFiles(assets: AssetLookup, m3: string, count: number): string[] {
  const key = assetKey(m3);
  const numbered: string[] = [];
  for (let i = 0; i < Math.max(count, 1); i++) {
    const file = assets.get(key.replace(/\.m3$/, `_${String(i).padStart(2, '0')}.m3`));
    if (file) numbered.push(file);
  }
  const plain = assets.get(key);
  if (count > 1) return numbered.length ? numbered : plain ? [plain] : [];
  return plain ? [plain] : numbered;
}

/**
 * Load the catalog. A doodad that draws nothing in game (model
 * "Invisible", or no model file) is listed with its editor model and
 * `editorOnly: true`; one with no file at all is left out and counted in
 * `withoutFile`.
 */
export async function loadDoodads(catalogDir: string, assets: AssetLookup): Promise<Doodads> {
  const byId = new Map<string, Doodad>();
  let withoutFile = 0;
  for (const fields of await readCatalog(catalogDir, 'doodads.json', 'doodads', 'doodad')) {
    const where = `doodads.json ${String(fields['id'])}`;
    const m3 = maybeText(fields, 'm3', where);
    const editorM3 = maybeText(fields, 'editorM3', where);
    // No VariationCount: one model file.
    const count = fields['variationCount'] === undefined ? 1 : num(fields, 'variationCount', where);
    let files = m3 && !fields['invisible'] ? variationFiles(assets, m3, count) : [];
    let editorOnly = false;
    if (!files.length && editorM3) {
      files = variationFiles(assets, editorM3, 1);
      editorOnly = files.length > 0;
    }
    if (!files.length) {
      withoutFile++;
      continue;
    }
    const id = text(fields, 'id', where);
    const name = text(fields, 'name', where);
    byId.set(id, { id, name, type: text(fields, 'type', where), tilesets: texts(fields, 'tilesets', where), fields, files, editorOnly, text: `${name} ${id}`.toLowerCase() });
  }
  const list = [...byId.values()].sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
  const byName = (a: string, b: string): number => a.localeCompare(b);
  const facets = { types: byCount(list, (d) => [d.type], byName), tilesets: byCount(list, (d) => d.tilesets, byName) };

  function search(query: string, type: string, tileset: string, offset: number, limit: number): Page<Record<string, unknown>> {
    const textQuery = query.toLowerCase().trim();
    const words = textQuery.split(/\s+/).filter(Boolean);
    let hits = list.filter((d) => (!type || d.type === type) && (!tileset || d.tilesets.includes(tileset)) && words.every((word) => d.text.includes(word)));
    // The map's own doodads first among equals.
    if (words.length) hits = sortBy(hits, (d) => rank(d, textQuery) * 2 + (d.fields['inMap'] ? 0 : 1));
    const brief = (d: Doodad): Record<string, unknown> => ({ id: d.id, name: d.name, type: d.type, inMap: d.fields['inMap'], variations: d.files.length, editorOnly: d.editorOnly });
    return { total: hits.length, items: hits.slice(offset, offset + limit).map(brief) };
  }

  function get(id: string): Record<string, unknown> | null {
    const d = byId.get(id);
    return d ? { ...d.fields, doodad: true, files: d.files, file: d.files[0], variations: d.files.length, editorOnly: d.editorOnly } : null;
  }

  return { size: byId.size, withoutFile, facets, search, get };
}
