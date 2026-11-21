// Check the vertex stride of every unit model: bytes / vertex count, against
// the library's rule and against m3addon's rule (structures.xml vertex formats).
//
// usage: node tools/vertex-survey.mjs DATA_DIR [UNIT_ID]

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const UV_BITS = [0x20000, 0x40000, 0x80000, 0x100000, 0x40000000];

/** The library before our fix: else-if on the UV bits, no vertex colour. */
function libraryStride(flags) {
  let uv = 1;
  if (flags & 0x40000) uv = 2;
  else if (flags & 0x80000) uv = 3;
  else if (flags & 0x100000) uv = 4;
  return (7 + uv) * 4;
}

/** One UV set per UV bit (0x20000 is set 0); 4 more bytes with vertex colours. */
function addonStride(flags) {
  const uv = UV_BITS.filter((bit) => flags & bit).length;
  return 28 + 4 * uv + (flags & 0x200 ? 4 : 0);
}

const [data, only] = process.argv.slice(2);
if (!data) throw new Error('usage: vertex-survey.mjs DATA_DIR [UNIT_ID]');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
const byFile = new Map();
for (const [unit, path] of Object.entries(files)) if (!only || unit === only) if (!byFile.has(path)) byFile.set(path, unit);

const flagsSeen = new Map();
let libraryWrong = 0;
let addonWrong = 0;
let checked = 0;
let skipped = 0;
let unparsable = 0;
for (const [path, unit] of byFile) {
  let model;
  try {
    const bytes = await readFile(path);
    const parsed = new M3Parser();
    parsed.load(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength));
    model = parsed.model;
  } catch {
    unparsable++;
    continue;
  }
  const div = model.divisions.first();
  if (!div) {
    skipped++;
    continue;
  }
  let count = 0;
  for (const region of div.regions.get() || []) count = Math.max(count, region.firstVertexIndex + region.verticesCount);
  const vertices = model.vertices.get();
  // No geometry (attachment-only or effect models): nothing to check.
  if (!count || !vertices) {
    skipped++;
    continue;
  }
  const bytes = vertices.length;
  checked++;
  const actual = bytes / count;
  const flags = model.vertexFlags >>> 0;
  const key = '0x' + flags.toString(16);
  const seen = flagsSeen.get(key) || { count: 0, actual: new Set(), library: libraryStride(flags), addon: addonStride(flags), example: unit };
  seen.count++;
  seen.actual.add(actual);
  flagsSeen.set(key, seen);
  if (libraryStride(flags) !== actual) libraryWrong++;
  if (addonStride(flags) !== actual) {
    addonWrong++;
    console.log(`ADDON MISMATCH ${unit} flags=${key} actual=${actual} addon=${addonStride(flags)}`);
  }
  if (only) console.log(`${unit} flags=${key} vertices=${count} bytes=${bytes} actual=${actual} library=${libraryStride(flags)} addon=${addonStride(flags)}`);
}
console.log(`skipped ${skipped} without geometry, ${unparsable} unparsable`);
console.log(`checked ${checked} model files; library stride wrong: ${libraryWrong}; m3addon stride wrong: ${addonWrong}`);
for (const [key, s] of [...flagsSeen.entries()].sort((a, b) => b[1].count - a[1].count)) {
  console.log(`  ${key} x${s.count} actual=${[...s.actual].join('/')} library=${s.library} addon=${s.addon} e.g. ${s.example}`);
}
