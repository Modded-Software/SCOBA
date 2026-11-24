// The model container the Ghost server serves for a .nod file
// (src/games/ghost/server/exporter.ts; SPEC-VIEWER-GHOST 7):
//   "NODX", uint32 version 1, uint32 JSON length, the JSON, then the binary
//   of `NODExport nod`: vertices of 52 bytes (float3 position, float3
//   normal, float2 uv, uint8[4] model bone numbers, float[4] weights), then
//   uint32 triangle indices. In the file's own axes.
// The JSON is { model, materials }, or { error } for a model the exporter
// refused. Every field is checked; a body that is not one is refused.

export const MAGIC = 'NODX';
const VERSION = 1;
export const STRIDE = 52;

export interface NodBone {
  parent: number;
  position: [number, number, number];
  /** 3x3, rows. */
  orientation: number[];
  /** Minus the bone's rest position in model space [checked on zergling.nod]. */
  offset: [number, number, number];
}

export interface NodGroup {
  material: number;
  vertexType: number;
  firstVertex: number;
  vertexCount: number;
  firstIndex: number;
  indexCount: number;
  bones: number[];
}

export interface NodMaterial {
  name: string;
  /** The lookup step of SPEC-VIEWER-GHOST 4.4: archive, nas, texture, none. */
  step: string;
  properties: [string, string][];
  /** Texture property to its file, relative to the build; null when missing. */
  textures: Record<string, string | null>;
}

export interface NodData {
  boundsMin: [number, number, number];
  boundsMax: [number, number, number];
  materialNames: string[];
  bones: NodBone[];
  groups: NodGroup[];
  materials: NodMaterial[];
  vertices: ArrayBuffer;
  vertexCount: number;
  indices: Uint32Array;
}

export function isContainer(bytes: unknown): bytes is Uint8Array {
  return bytes instanceof Uint8Array && bytes.length >= 12 && String.fromCharCode(bytes[0] ?? 0, bytes[1] ?? 0, bytes[2] ?? 0, bytes[3] ?? 0) === MAGIC;
}

type Json = Record<string, unknown>;
const isObject = (v: unknown): v is Json => typeof v === 'object' && v !== null && !Array.isArray(v);

function fail(what: string, want: string): never {
  throw new Error(`nod container: ${what} is not ${want}`);
}
function object(v: unknown, what: string): Json {
  return isObject(v) ? v : fail(what, 'an object');
}
function array(v: unknown, what: string): unknown[] {
  return Array.isArray(v) ? v : fail(what, 'a list');
}
function int(v: unknown, what: string): number {
  return typeof v === 'number' && Number.isInteger(v) ? v : fail(what, 'a whole number');
}
function num(v: unknown, what: string): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : fail(what, 'a number');
}
function str(v: unknown, what: string): string {
  return typeof v === 'string' ? v : fail(what, 'text');
}
function vec3(v: unknown, what: string): [number, number, number] {
  const a = array(v, what);
  if (a.length !== 3) fail(what, 'three numbers');
  return [num(a[0], what), num(a[1], what), num(a[2], what)];
}
function nums(v: unknown, what: string, length: number): number[] {
  const a = array(v, what);
  if (a.length !== length) fail(what, `${length} numbers`);
  return a.map((x, i) => num(x, `${what}[${i}]`));
}

function material(v: unknown, what: string): NodMaterial {
  const m = object(v, what);
  const properties = array(m['properties'], `${what}.properties`).map((p, i): [string, string] => {
    const pair = array(p, `${what}.properties[${i}]`);
    return [str(pair[0], `${what}.properties[${i}]`), str(pair[1], `${what}.properties[${i}]`)];
  });
  const textures: Record<string, string | null> = {};
  for (const [key, file] of Object.entries(object(m['textures'], `${what}.textures`))) textures[key] = file === null ? null : str(file, `${what}.textures.${key}`);
  return { name: str(m['name'], `${what}.name`), step: str(m['step'], `${what}.step`), properties, textures };
}

/** The container's parts, checked. A refused model throws its message (R-VIEW-82). */
export function readContainer(bytes: Uint8Array, name: string): NodData {
  if (!isContainer(bytes)) throw new Error(`${name}: not a nod container`);
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  if (view.getUint32(4, true) !== VERSION) throw new Error(`${name}: container version ${view.getUint32(4, true)}, not ${VERSION}`);
  const length = view.getUint32(8, true);
  if (12 + length > bytes.length) throw new Error(`${name}: the description runs past the end`);
  const body = object(JSON.parse(new TextDecoder().decode(bytes.subarray(12, 12 + length))), 'body');
  if (body['error'] !== undefined) throw new Error(`refused: ${str(body['error'], 'error')}`);
  const model = object(body['model'], 'model');
  if (int(model['vertexStride'], 'vertexStride') !== STRIDE) fail('vertexStride', String(STRIDE));
  const vertexCount = int(model['vertexCount'], 'vertexCount');
  const indexCount = int(model['indexCount'], 'indexCount');
  const indexOffset = int(model['indexOffset'], 'indexOffset');
  const start = 12 + length;
  if (indexOffset !== vertexCount * STRIDE || start + indexOffset + indexCount * 4 !== bytes.length) throw new Error(`${name}: the binary is ${bytes.length - start} bytes, not ${indexOffset + indexCount * 4}`);
  const materialNames = array(model['materials'], 'materials').map((m, i) => str(m, `materials[${i}]`));
  const bones = array(model['bones'], 'bones').map((b, i): NodBone => {
    const o = object(b, `bones[${i}]`);
    return { parent: int(o['parent'], `bones[${i}].parent`), position: vec3(o['position'], `bones[${i}].position`), orientation: nums(o['orientation'], `bones[${i}].orientation`, 9), offset: vec3(o['offset'], `bones[${i}].offset`) };
  });
  bones.forEach((b, i) => {
    if (b.parent >= i || b.parent < -1) throw new Error(`${name}: bone ${i} has parent ${b.parent}, not an earlier bone`);
  });
  const groups = array(model['groups'], 'groups').map((g, i): NodGroup => {
    const o = object(g, `groups[${i}]`);
    const group = {
      material: int(o['material'], `groups[${i}].material`),
      vertexType: int(o['vertexType'], `groups[${i}].vertexType`),
      firstVertex: int(o['firstVertex'], `groups[${i}].firstVertex`),
      vertexCount: int(o['vertexCount'], `groups[${i}].vertexCount`),
      firstIndex: int(o['firstIndex'], `groups[${i}].firstIndex`),
      indexCount: int(o['indexCount'], `groups[${i}].indexCount`),
      bones: array(o['bones'], `groups[${i}].bones`).map((x, k) => int(x, `groups[${i}].bones[${k}]`)),
    };
    if (group.material >= materialNames.length || group.firstIndex + group.indexCount > indexCount) throw new Error(`${name}: group ${i} names material ${group.material} or indices past the end`);
    return group;
  });
  const materials = array(body['materials'], 'materials').map((m, i) => material(m, `materials[${i}]`));
  const indices = new Uint32Array(bytes.slice(start + indexOffset, start + indexOffset + indexCount * 4).buffer);
  for (const index of indices) if (index >= vertexCount) throw new Error(`${name}: index ${index} of ${vertexCount} vertices`);
  const limit = Math.max(bones.length, 1); // a model without bones names bone 0
  for (let v = 0; v < vertexCount; v++) {
    for (let k = 0; k < 4; k++) {
      const bone = bytes[start + v * STRIDE + 32 + k] ?? 0;
      if (bone >= limit) throw new Error(`${name}: vertex ${v} names bone ${bone} of ${bones.length}`);
    }
  }
  return {
    boundsMin: vec3(model['boundsMin'], 'boundsMin'),
    boundsMax: vec3(model['boundsMax'], 'boundsMax'),
    materialNames,
    bones,
    groups,
    materials,
    vertices: bytes.slice(start, start + indexOffset).buffer,
    vertexCount,
    indices,
  };
}
