// Reading the catalog files (tools/build_catalog.py, tools/build_doodads.py).
// A record keeps every field the catalog wrote; the server reads only
// the fields it needs, each checked here.

import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { errorCode } from '../../../server/core/http';

/** A catalog record: the fields as written, untouched. */
export type CatalogRecord = Readonly<Record<string, unknown>>;

/** In-model asset path (lower case, backslashes) -> servable path. */
export interface AssetLookup {
  get(key: string): string | undefined;
}

export const assetKey = (path: string): string => path.toLowerCase().replaceAll('/', '\\');

const isRecord = (value: unknown): value is CatalogRecord => typeof value === 'object' && value !== null && !Array.isArray(value);

/** A text field; `where` names the record in the error. */
export function text(record: CatalogRecord, key: string, where: string): string {
  const value = record[key];
  if (typeof value !== 'string') throw new Error(`${where}: "${key}" is not text`);
  return value;
}

/** A text field that may be absent or null. */
export function maybeText(record: CatalogRecord, key: string, where: string): string | null {
  const value = record[key];
  if (value === undefined || value === null) return null;
  if (typeof value !== 'string') throw new Error(`${where}: "${key}" is not text`);
  return value;
}

/** A number field. */
export function num(record: CatalogRecord, key: string, where: string): number {
  const value = record[key];
  if (typeof value !== 'number') throw new Error(`${where}: "${key}" is not a number`);
  return value;
}

/** A list of texts. */
export function texts(record: CatalogRecord, key: string, where: string): string[] {
  const value = record[key];
  if (!Array.isArray(value) || !value.every((v): v is string => typeof v === 'string')) throw new Error(`${where}: "${key}" is not a list of texts`);
  return value;
}

/** The record list under `key` of a catalog file, or a clear error when the file is missing. */
export async function readCatalog(catalogDir: string, file: string, key: string, kind: string): Promise<CatalogRecord[]> {
  const full = join(catalogDir, file);
  let body: string;
  try {
    body = await readFile(full, 'utf8');
  } catch (error) {
    if (errorCode(error) === 'ENOENT') throw new Error(`${kind} catalog missing: ${full}. Run "make viewer-catalog".`);
    throw error;
  }
  const data: unknown = JSON.parse(body);
  const list: unknown = isRecord(data) ? data[key] : undefined;
  if (!Array.isArray(list)) throw new Error(`${full}: no "${key}" list`);
  return list.map((entry: unknown, i) => {
    if (!isRecord(entry)) throw new Error(`${full}: ${key}[${i}] is not an object`);
    return entry;
  });
}

/** Lower is better: the whole name, a name that starts with the query, a word that does, the id. */
export function rank(record: { name: string; id: string }, query: string): number {
  const name = record.name.toLowerCase();
  if (name === query) return 0;
  if (name.startsWith(query)) return 1;
  if (name.split(/\s+/).some((word) => word.startsWith(query))) return 2;
  if (record.id.toLowerCase().startsWith(query)) return 3;
  return 4;
}

/** The values of a field over a list, the most common first; ties in the order `tie` gives. */
export function byCount<T>(list: readonly T[], valuesOf: (item: T) => readonly string[], tie: (a: string, b: string) => number): string[] {
  const seen = new Map<string, number>();
  for (const item of list) for (const value of valuesOf(item)) seen.set(value, (seen.get(value) ?? 0) + 1);
  return [...seen.entries()].sort((a, b) => b[1] - a[1] || tie(a[0], b[0])).map(([value]) => value);
}

/** Sort a list by a key, stable. */
export function sortBy<T>(list: readonly T[], key: (item: T) => number): T[] {
  return list
    .map((item): [number, T] => [key(item), item])
    .sort((a, b) => a[0] - b[0])
    .map(([, item]) => item);
}
