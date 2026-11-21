// Parse the model file of every catalog unit with the patched M3 parser.
// Prints how many parse, and the failures grouped by message.
// Writes catalog/unparsable.json: unit id -> message.
//
// usage: node tools/parse-survey.mjs DATA_DIR

import { readFile, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const data = process.argv[2];
if (!data) throw new Error('usage: parse-survey.mjs DATA_DIR');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));

const failed = {};
const groups = new Map();
let ok = 0;
for (const [unit, path] of Object.entries(files)) {
  try {
    const bytes = await readFile(path);
    new M3Parser().load(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength));
    ok++;
  } catch (error) {
    const message = String(error.message || error).replace(/^: /, '');
    failed[unit] = message;
    if (!groups.has(message)) groups.set(message, []);
    groups.get(message).push(unit);
  }
}

await writeFile(join(data, 'catalog', 'unparsable.json'), JSON.stringify(failed, null, 1) + '\n');
console.log(`units with a model file ${Object.keys(files).length}  parse ${ok}  fail ${Object.keys(failed).length}`);
for (const [message, units] of [...groups.entries()].sort((a, b) => b[1].length - a[1].length)) {
  console.log(`  ${units.length} x ${message}  e.g. ${units.slice(0, 5).join(', ')}`);
}
