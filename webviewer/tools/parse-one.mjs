// Parse the model file of one unit with the patched parser and print the
// failure with its stack, plus the struct versions in the file.
//
// usage: node tools/parse-one.mjs DATA_DIR UNIT_ID

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const [data, unit] = process.argv.slice(2);
if (!data || !unit) throw new Error('usage: parse-one.mjs DATA_DIR UNIT_ID');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
const path = files[unit];
if (!path) throw new Error(`no model file for ${unit}`);
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

try {
  new M3Parser().load(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength));
  console.log('parses');
} catch (error) {
  // The failure is the report: print it and exit non-zero.
  console.error(error.stack);
  process.exitCode = 1;
}
