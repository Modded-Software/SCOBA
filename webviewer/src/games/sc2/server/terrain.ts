// The SC2 ground textures (SPEC-VIEWER 17.5, SPEC-VIEWER-SC2 8.2): one
// record per terrain texture entry (`CTerrainTex`) of the dataset, with
// its colour file and its normal map. The pipeline lists them, with their
// state (the texture service's listing of the kind "terrain", read from the
// pipeline's state index); this file groups the files by the entry that
// names them.

import type { Page } from '../../../shared/records';
import { HttpError } from '../../../server/core/backend';
import type { TextureListing, TextureService } from '../../../server/core/textures';
import type { TerrainRecord } from '../shared/records';

/** The pipeline's word for a terrain texture, and the roles of its files. */
const KIND = 'terrain';
const COLOUR = 'diffuse';
const NORMAL = 'normal';

/** "baked pbrify@2048 · 2 variants · packaged": what the row says of its colour file. */
function stateOf(colour: TextureListing): string {
  const parts = [colour.bake ? `baked ${colour.bake}` : 'original'];
  parts.push(colour.variants.length === 1 ? '1 variant' : `${colour.variants.length} variants`);
  if (colour.packaged) parts.push('packaged');
  return parts.join(' · ');
}

/** Every terrain texture entry with a colour file, by entry id. */
export function terrainRecords(service: TextureService, dataset: string): TerrainRecord[] {
  const byEntry = new Map<string, { colour?: TextureListing; normal?: TextureListing }>();
  for (const listed of service.listKind(dataset, KIND)) {
    for (const entry of listed.entries) {
      const files = byEntry.get(entry) ?? {};
      if (listed.role === COLOUR) files.colour = listed;
      if (listed.role === NORMAL) files.normal = listed;
      byEntry.set(entry, files);
    }
  }
  const records: TerrainRecord[] = [];
  for (const [id, { colour, normal }] of [...byEntry].sort(([a], [b]) => a.localeCompare(b))) {
    if (!colour) continue;
    const state = stateOf(colour);
    records.push({ id, name: id, sub: `${state}${colour.users.length ? ' · ' + colour.users.join(', ') : ''}`, icon: null, placeable: false, notPlaceableAs: 'ground texture', file: colour.asset, normal: normal ? normal.asset : null, users: colour.users, state, dataset });
  }
  return records;
}

/** One page of the ground textures that hold every query word, in name, file or terrain set. */
export function searchTerrain(service: TextureService, dataset: string, query: string, offset: number, limit: number): Page<TerrainRecord> {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  const hits = terrainRecords(service, dataset).filter((record) => words.every((word) => `${record.id} ${record.file} ${record.users.join(' ')}`.toLowerCase().includes(word)));
  return { total: hits.length, items: hits.slice(offset, offset + limit) };
}

/** One ground texture record; 404 when the dataset has no such entry. */
export function terrainRecord(service: TextureService, dataset: string, id: string): TerrainRecord {
  const found = terrainRecords(service, dataset).find((record) => record.id === id);
  if (!found) throw new HttpError(404, { error: 'not found', id, dataset });
  return found;
}
