// The unit catalog of one dataset: units.json (tools/build_catalog.py)
// joined with the model files the server can serve.

import type { Page } from '../../../shared/records';
import { assetKey, byCount, maybeText, rank, readCatalog, sortBy, text, type AssetLookup, type CatalogRecord } from './catalog';

interface Unit {
  readonly id: string;
  readonly name: string;
  readonly race: string;
  readonly kind: string;
  readonly family: string;
  /** In-model path of its model file, as the catalog names it. */
  readonly m3: string;
  /** The catalog record as written. */
  readonly fields: CatalogRecord;
  /** The servable model file. */
  readonly file: string;
  /** Name and id, lower case, for search. */
  readonly text: string;
  /** Its model is a skybox (markSkyboxes, from skyboxes.ts). */
  skybox: boolean;
}

export interface UnitFacets {
  races: string[];
  kinds: string[];
  families: string[];
}

export interface Units {
  readonly size: number;
  readonly withoutFile: number;
  readonly facets: UnitFacets;
  /** Icon and portrait file names the catalog uses. Nothing else is served from icons/. */
  readonly icons: ReadonlySet<string>;
  /** `family` null: any family; a string (also '', no family): that family only. */
  search(query: string, race: string, kind: string, family: string | null, offset: number, limit: number): Page<Record<string, unknown>>;
  /** The full record; null when there is none. */
  get(id: string): Record<string, unknown> | null;
  /** Mark the units whose model is a skybox. */
  markSkyboxes(isSkybox: (key: string) => boolean): void;
}

/**
 * Load the catalog. A unit whose model file cannot be served is left out
 * and counted in `withoutFile`.
 */
export async function loadUnits(catalogDir: string, assets: AssetLookup): Promise<Units> {
  /**
   * The servable path of a unit's model. The game's naming rule: the file the
   * unit names; a model with variations is stored as name_00.m3, name_01.m3,
   * ..., so a unit naming name.m3 with no such file shows name_00.m3.
   * Neither: null (the unit is left out and counted).
   */
  const modelFile = (m3: string): string | null => {
    const key = assetKey(m3);
    const named = assets.get(key);
    if (named !== undefined) return named;
    const firstVariation = assets.get(key.replace(/\.m3$/, '_00.m3'));
    return firstVariation === undefined ? null : firstVariation;
  };
  const byId = new Map<string, Unit>();
  const icons = new Set<string>();
  let withoutFile = 0;
  for (const fields of await readCatalog(catalogDir, 'units.json', 'units', 'unit')) {
    const where = `units.json ${String(fields['id'])}`;
    const m3 = text(fields, 'm3', where);
    const file = modelFile(m3);
    if (!file) {
      withoutFile++;
      continue;
    }
    const id = text(fields, 'id', where);
    const name = text(fields, 'name', where);
    const unit: Unit = { id, name, race: text(fields, 'race', where), kind: text(fields, 'kind', where), family: text(fields, 'family', where), m3, fields, file, text: `${name} ${id}`.toLowerCase(), skybox: false };
    byId.set(id, unit);
    for (const icon of [maybeText(fields, 'icon', where), maybeText(fields, 'portrait', where)]) if (icon) icons.add(icon);
  }
  const list = [...byId.values()].sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));
  // Family: the EditorCategories ObjectFamily (Melee, Campaign, Storymode, ...); '' when the unit has none.
  const facets = { races: byCount(list, (u) => [u.race], () => 0), kinds: byCount(list, (u) => [u.kind], () => 0), families: byCount(list, (u) => [u.family], () => 0) };

  function search(query: string, race: string, kind: string, family: string | null, offset: number, limit: number): Page<Record<string, unknown>> {
    const textQuery = query.toLowerCase().trim();
    const words = textQuery.split(/\s+/).filter(Boolean);
    let hits = list.filter((u) => (!race || u.race === race) && (!kind || u.kind === kind) && (family === null || u.family === family) && words.every((word) => u.text.includes(word)));
    if (words.length) {
      // The map's own units first among equals, then melee units, then the rest.
      hits = sortBy(hits, (u) => rank(u, textQuery) * 4 + (u.fields['inMap'] ? 0 : u.family === 'Melee' ? 1 : 2));
    }
    // The RecordSummary fields (sub, placeable), then the SC2 ones. A skybox unit is a backdrop: "add all" leaves it out.
    const brief = (u: Unit): Record<string, unknown> => ({
      id: u.id,
      name: u.name,
      sub: `${u.race} · ${u.kind} · ${u.id}${u.skybox ? ' · skybox' : ''}`,
      icon: u.fields['icon'] ?? null,
      placeable: !u.skybox,
      notPlaceableAs: u.skybox ? 'skybox unit' : null,
      race: u.race,
      kind: u.kind,
      family: u.family,
      inMap: u.fields['inMap'],
      skybox: u.skybox,
    });
    return { total: hits.length, items: hits.slice(offset, offset + limit).map(brief) };
  }

  function get(id: string): Record<string, unknown> | null {
    const unit = byId.get(id);
    return unit ? { ...unit.fields, file: unit.file, skybox: unit.skybox } : null;
  }

  function markSkyboxes(isSkybox: (key: string) => boolean): void {
    for (const unit of byId.values()) unit.skybox = isSkybox(assetKey(unit.m3));
  }

  return { size: byId.size, withoutFile, facets, icons, search, get, markSkyboxes };
}
