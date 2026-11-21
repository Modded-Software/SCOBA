// Parse one model file with the patched parser and print the failure with
// its stack, the struct versions in the file, and the geometry it references.
//
// usage: node tools/parse-one.mjs DATA_DIR UNIT_ID
//        node tools/parse-one.mjs DATA_DIR FILE.m3

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const [data, unit] = process.argv.slice(2);
if (!data || !unit) throw new Error('usage: parse-one.mjs DATA_DIR UNIT_ID|FILE.m3');
let path = unit;
if (!/\.m3$/i.test(unit)) {
  const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
  path = files[unit];
  if (!path) throw new Error(`no model file for ${unit}`);
}
const bytes = await readFile(path);
console.log(path, bytes.length, 'bytes');

const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
const indexOffset = view.getUint32(4, true);
const indexSize = view.getUint32(8, true);
const seen = new Map();
for (let i = 0; i < indexSize; i++) {
  const at = indexOffset + i * 16;
  const tag = [3, 2, 1, 0].map((k) => String.fromCharCode(view.getUint8(at + k))).join('').replace(/[^\x20-\x7e]/g, '_');
  const key = `${tag} v${view.getUint32(at + 12, true)}`;
  seen.set(key, (seen.get(key) || 0) + 1);
}
console.log([...seen.entries()].map(([key, count]) => `${key} x${count}`).join(', '));

/** A reference as "entries@index" with what get() gives. */
function ref(name, reference) {
  const got = reference.get();
  return `${name} ${reference.entries}@${reference.id}=${got === undefined ? 'undefined' : (got.length ?? 'object')}`;
}

try {
  const parsed = new M3Parser();
  parsed.load(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength));
  console.log('parses');
  const model = parsed.model;
  console.log([ref('divisions', model.divisions), ref('vertices', model.vertices), ref('sequences', model.sequences), ref('sts', model.sts), ref('stc', model.stc), ref('stg', model.stg)].join(', '));
  const div = model.divisions.first();
  if (div) console.log('division:', [ref('regions', div.regions), ref('triangles', div.triangles), ref('batches', div.batches)].join(', '));
  for (const [i, sts] of (model.sts.get() || []).entries()) console.log(`sts ${i}:`, ref('animIds', sts.animIds));
} catch (error) {
  // The failure is the report: print it and exit non-zero.
  console.error(error.stack);
  process.exitCode = 1;
}
