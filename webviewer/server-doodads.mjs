// The doodad catalog of the viewer server: doodads.json (tools/build_doodads.py)
// joined with the model files the server can serve.

import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

const assetKey = (m3) => m3.toLowerCase().replaceAll('/', '\\');

/**
 * The servable files of a model, one per variation. A model with
 * VariationCount n is stored as name_00.m3 .. name_(n-1).m3; one without
 * variations as name.m3 (some as name_00.m3 only).
 */
function variationFiles(assets, m3, count) {
  const key = assetKey(m3);
  const numbered = [];
  for (let i = 0; i < Math.max(count, 1); i++) {
    const file = assets.get(key.replace(/\.m3$/, `_${String(i).padStart(2, '0')}.m3`));
    if (file) numbered.push(file);
  }
  const plain = assets.get(key);
  if (count > 1) return numbered.length ? numbered : plain ? [plain] : [];
  return plain ? [plain] : numbered;
}

/** Lower is better: the whole name, a name that starts with the query, a word that does, the id. */
function rank(doodad, query) {
  const name = doodad.name.toLowerCase();
  if (name === query) return 0;
  if (name.startsWith(query)) return 1;
  if (name.split(/\s+/).some((word) => word.startsWith(query))) return 2;
  if (doodad.id.toLowerCase().startsWith(query)) return 3;
  return 4;
}

/**
 * Load the catalog. `assets`: in-model asset path -> servable path.
 * A doodad that draws nothing in game (model "Invisible", or no model
 * file) is listed with its editor model and `editorOnly: true`; one with
 * no file at all is left out and counted in `withoutFile`.
 */
export async function loadDoodads(catalogDir, assets) {
  const full = join(catalogDir, 'doodads.json');
  let text;
  try {
    text = await readFile(full, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') throw new Error(`doodad catalog missing: ${full}. Run "make viewer-catalog".`);
    throw error;
  }
  const byId = new Map();
  let withoutFile = 0;
  for (const record of JSON.parse(text).doodads) {
    let files = record.m3 && !record.invisible ? variationFiles(assets, record.m3, record.variationCount) : [];
    let editorOnly = false;
    if (!files.length && record.editorM3) {
      files = variationFiles(assets, record.editorM3, 1);
      editorOnly = files.length > 0;
    }
    if (!files.length) {
      withoutFile++;
      continue;
    }
    byId.set(record.id, { ...record, doodad: true, files, file: files[0], variations: files.length, editorOnly, text: `${record.name} ${record.id}`.toLowerCase() });
  }
  const list = [...byId.values()].sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
  const count = (valuesOf) => {
    const seen = new Map();
    for (const doodad of list) for (const value of valuesOf(doodad)) seen.set(value, (seen.get(value) || 0) + 1);
    return [...seen.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([value]) => value);
  };
  const facets = { types: count((d) => [d.type]), tilesets: count((d) => d.tilesets) };

  /** One page of the doodads that match: every query word, the type, and a terrain set that lists it. */
  function search(query, type, tileset, offset, limit) {
    const textQuery = query.toLowerCase().trim();
    const words = textQuery.split(/\s+/).filter(Boolean);
    let hits = list.filter((d) => (!type || d.type === type) && (!tileset || d.tilesets.includes(tileset)) && words.every((word) => d.text.includes(word)));
    if (words.length) {
      // The map's own doodads first among equals.
      const order = (d) => rank(d, textQuery) * 2 + (d.inMap ? 0 : 1);
      hits = hits.map((d) => [order(d), d]).sort((a, b) => a[0] - b[0]).map(([, d]) => d);
    }
    const brief = ({ id, name, type, inMap, variations, editorOnly }) => ({ id, name, type, inMap, variations, editorOnly });
    return { total: hits.length, items: hits.slice(offset, offset + limit).map(brief) };
  }

  /** The full record, without the search text; null when there is none. */
  function get(id) {
    const doodad = byId.get(id);
    if (!doodad) return null;
    const { text: _text, ...record } = doodad;
    return record;
  }

  return { size: byId.size, withoutFile, facets, search, get };
}
