// Check the culling bounds of every unit model. The viewer culls with a
// sphere around the model origin that holds the header box, every sequence
// box and every rest-pose vertex (M3Model.setupBounds). This survey reads
// the boxes and the vertices apart, and reports:
// - models whose boxes give no size (radius 0, or not finite);
// - models whose rest-pose vertices reach past the boxes' sphere (the
//   viewer widens the sphere for these).
//
// usage: node tools/bounds-survey.mjs DATA_DIR [UNIT_ID]

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const UV_BITS = [0x20000, 0x40000, 0x80000, 0x100000, 0x40000000];
const stride = (flags) => 28 + 4 * UV_BITS.filter((bit) => flags & bit).length + (flags & 0x200 ? 4 : 0);

/** The viewer's sphere radius: the farthest corner of any box from the origin. */
function reach(boxes) {
  let r = 0;
  for (const box of boxes) {
    for (const x of [box.min[0], box.max[0]]) for (const y of [box.min[1], box.max[1]]) for (const z of [box.min[2], box.max[2]]) r = Math.max(r, Math.hypot(x, y, z));
  }
  return r;
}

/** The farthest rest-pose vertex from the origin. */
function vertexReach(model, count) {
  const bytes = model.vertices.get();
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const size = stride(model.vertexFlags >>> 0);
  let r = 0;
  for (let i = 0; i < count; i++) {
    const at = i * size;
    r = Math.max(r, Math.hypot(view.getFloat32(at, true), view.getFloat32(at + 4, true), view.getFloat32(at + 8, true)));
  }
  return r;
}

const [data, only] = process.argv.slice(2);
if (!data) throw new Error('usage: bounds-survey.mjs DATA_DIR [UNIT_ID]');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
const byFile = new Map();
for (const [unit, path] of Object.entries(files)) if (!only || unit === only) if (!byFile.has(path)) byFile.set(path, unit);

let checked = 0;
let skipped = 0;
const unparsable = [];
const sizeless = [];
const short = [];
let largest = { r: 0, unit: '' };
for (const [path, unit] of byFile) {
  let model;
  try {
    const bytes = await readFile(path);
    const parsed = new M3Parser();
    parsed.load(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength));
    model = parsed.model;
  } catch (error) {
    unparsable.push(`${unit}: ${error.message}`);
    continue;
  }
  const div = model.divisions.first();
  let count = 0;
  for (const region of (div && div.regions.get()) || []) count = Math.max(count, region.firstVertexIndex + region.verticesCount);
  if (!count || !model.vertices.get()) {
    skipped++;
    continue;
  }
  checked++;
  const sequences = model.sequences.get() || [];
  const r = reach([model.boundings, ...sequences.map((s) => s.boundingSphere)]);
  const v = vertexReach(model, count);
  if (!(r > 0) || !Number.isFinite(r)) sizeless.push(`${unit} r=${r} vertices reach ${v.toFixed(3)}`);
  else if (v > r * 1.001) short.push(`${unit} r=${r.toFixed(3)} vertices reach ${v.toFixed(3)} (x${(v / r).toFixed(2)})`);
  if (Number.isFinite(r) && r > largest.r) largest = { r, unit };
  if (only) console.log(`${unit} sphere r=${r.toFixed(3)} header r=${model.boundings.radius.toFixed(3)} sequences=${sequences.length} vertices reach ${v.toFixed(3)}`);
}
for (const line of sizeless) console.log('NO SIZE ' + line);
for (const line of short) console.log('SHORT ' + line);
for (const line of unparsable) console.log('UNPARSABLE ' + line);
console.log(`checked ${checked} model files, skipped ${skipped} without geometry, ${unparsable.length} unparsable`);
console.log(`no size: ${sizeless.length}; vertices past the sphere: ${short.length}; largest sphere ${largest.r.toFixed(1)} (${largest.unit})`);
