// Batch draw order (gap G2, M3): per unit model, the standard-material
// batches as the viewer collects them (composite sections in order), and
// whether the draw order (opaque first, then blended by priority ascending,
// stable; ref draworder.ts) differs from file order. One line per model
// whose order changes:
//   PRIO <unit> batches=<n> blended=<n> opaqueAfterBlended=<n> priorities=<file-order list of blended priorities>
// Up to 10 models already in order with two or more blended priorities:
//   SORTED <unit> batches=<n> blended=<n> priorities=<list>
// Ends with counts, and every model the parser cannot read:
//   UNPARSABLE <unit>: <error>
//
// usage: node tools/priority-survey.mjs DATA_DIR [UNIT_ID]

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const [data, only] = process.argv.slice(2);
if (!data) throw new Error('usage: priority-survey.mjs DATA_DIR [UNIT_ID]');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
const byFile = new Map();
for (const [unit, path] of Object.entries(files)) if (!only || unit === only) if (!byFile.has(path)) byFile.set(path, unit);

const unparsable = [];
let changed = 0;
let checked = 0;
let sortedShown = 0;
for (const [path, unit] of byFile) {
  const bytes = await readFile(path);
  const parsed = new M3Parser();
  try {
    parsed.load(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength));
  } catch (error) {
    unparsable.push(`${unit}: ${error.message}`);
    continue;
  }
  checked++;
  const model = parsed.model;
  const maps = model.materialReferences.list([]);
  const standards = model.materials[0].list([]);
  const composites = model.materials[2].list([]);
  const div = model.divisions.first();
  const drawn = []; // standard materials in file order, as model.ts collects them
  for (const batch of div && div.batches.entries ? div.batches.list([]) : []) {
    const map = maps[batch.materialReferenceIndex];
    if (map.materialType === 1) drawn.push(standards[map.materialIndex]);
    if (map.materialType === 3) {
      for (const s of composites[map.materialIndex].sections.list([])) {
        const sm = maps[s.materialReferenceIndex];
        if (sm.materialType === 1) drawn.push(standards[sm.materialIndex]);
      }
    }
  }
  const blended = drawn.filter((m) => m.blendMode !== 0);
  let opaqueAfterBlended = 0;
  let seenBlended = false;
  for (const m of drawn) {
    if (m.blendMode !== 0) seenBlended = true;
    else if (seenBlended) opaqueAfterBlended++;
  }
  const priorities = blended.map((m) => m.priority);
  const unsorted = priorities.some((p, i) => i > 0 && p < priorities[i - 1]);
  if (!unsorted && !opaqueAfterBlended && !only) {
    // Already in order with something to order: negative-case candidates.
    if (blended.length >= 2 && new Set(priorities).size >= 2 && sortedShown++ < 10) console.log(`SORTED ${unit} batches=${drawn.length} blended=${blended.length} priorities=${priorities.join(',')}`);
    continue;
  }
  if (unsorted || opaqueAfterBlended) changed++;
  console.log(`PRIO ${unit} batches=${drawn.length} blended=${blended.length} opaqueAfterBlended=${opaqueAfterBlended} priorities=${priorities.join(',')}`);
}
for (const line of unparsable) console.log('UNPARSABLE ' + line);
console.log(`checked ${checked} model files; draw order differs from file order in ${changed}`);
