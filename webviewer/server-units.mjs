// The unit catalog of one dataset: units.json (tools/build_catalog.py)
// joined with the model files the server can serve.

import { readFile } from 'node:fs/promises';
import { join } from 'node:path';

/** Lower is better: the whole name, then a name that starts with it, then a word that does. */
function rank(unit, query) {
  const name = unit.name.toLowerCase();
  if (name === query) return 0;
  if (name.startsWith(query)) return 1;
  if (name.split(/\s+/).some((word) => word.startsWith(query))) return 2;
  if (unit.id.toLowerCase().startsWith(query)) return 3;
  return 4;
}

/**
 * Load the catalog. `assets.get`: in-model asset path -> servable path.
 * A unit whose model file cannot be served is left out and counted in
 * `withoutFile`.
 */
export async function loadUnits(catalogDir, assets) {
  const full = join(catalogDir, 'units.json');
  let text;
  try {
    text = await readFile(full, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') throw new Error(`unit catalog missing: ${full}. Run "make viewer-catalog".`);
    throw error;
  }
  /** The servable path of a unit's model: the file itself, or its first variation. */
  const modelFile = (m3) => {
    const key = m3.toLowerCase().replaceAll('/', '\\');
    return assets.get(key) ?? assets.get(key.replace(/\.m3$/, '_00.m3')) ?? null;
  };
  const byId = new Map();
  /** Icon and portrait file names the catalog uses. Nothing else is served from icons/. */
  const icons = new Set();
  let withoutFile = 0;
  for (const record of JSON.parse(text).units) {
    const file = modelFile(record.m3);
    if (!file) {
      withoutFile++;
      continue;
    }
    const unit = { ...record, file, text: `${record.name} ${record.id}`.toLowerCase() };
    byId.set(unit.id, unit);
    for (const name of [unit.icon, unit.portrait]) if (name) icons.add(name);
  }
  const list = [...byId.values()].sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
  const count = (field) => {
    const seen = new Map();
    for (const unit of list) seen.set(unit[field], (seen.get(unit[field]) || 0) + 1);
    return [...seen.entries()].sort((a, b) => b[1] - a[1]).map(([value]) => value);
  };
  // Family: the EditorCategories ObjectFamily (Melee, Campaign, Storymode, ...); '' when the unit has none.
  const facets = { races: count('race'), kinds: count('kind'), families: count('family') };

  /** `family` null: any family; a string (also '', no family): that family only. */
  function search(query, race, kind, family, offset, limit) {
    const textQuery = query.toLowerCase().trim();
    const words = textQuery.split(/\s+/).filter(Boolean);
    let hits = list.filter((unit) => (!race || unit.race === race) && (!kind || unit.kind === kind) && (family === null || unit.family === family) && words.every((word) => unit.text.includes(word)));
    if (words.length) {
      // The map's own units first among equals, then melee units, then the rest.
      const order = (unit) => rank(unit, textQuery) * 4 + (unit.inMap ? 0 : unit.family === 'Melee' ? 1 : 2);
      hits = hits.map((unit) => [order(unit), unit]).sort((a, b) => a[0] - b[0]).map(([, unit]) => unit);
    }
    const brief = ({ id, name, race, kind, family, icon, inMap, skybox }) => ({ id, name, race, kind, family, icon, inMap, skybox });
    return { total: hits.length, items: hits.slice(offset, offset + limit).map(brief) };
  }

  /** The full record, without the search text; null when there is none. */
  function get(id) {
    const unit = byId.get(id);
    if (!unit) return null;
    const { text: _text, ...record } = unit;
    return record;
  }

  return { size: byId.size, withoutFile, facets, icons, search, get, values: () => byId.values() };
}
