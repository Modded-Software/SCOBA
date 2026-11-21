// Print the regions of one unit's model: first vertex, vertex count, first
// triangle index, index count, and the largest vertex index a region's
// triangles reach (firstVertexIndex + its largest local index). Flags the
// regions whose indices go past 65535 (a 16-bit element buffer wraps there).
//
// usage: node tools/m3-regions.mjs DATA_DIR UNIT_ID

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const [data, unit] = process.argv.slice(2);
if (!data || !unit) throw new Error('usage: m3-regions.mjs DATA_DIR UNIT_ID');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
const path = files[unit];
if (!path) throw new Error(`no model file for ${unit}`);
const bytes = await readFile(path);
const parsed = new M3Parser();
parsed.load(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength));
const div = parsed.model.divisions.first();
const triangles = div.triangles.list(new Uint16Array(0));
let vertices = 0;
let past = 0;
console.log(path);
for (const [i, r] of div.regions.list([]).entries()) {
  let local = 0;
  for (let k = 0; k < r.triangleIndicesCount; k++) local = Math.max(local, triangles[r.firstTriangleIndex + k]);
  const top = r.firstVertexIndex + local;
  vertices = Math.max(vertices, r.firstVertexIndex + r.verticesCount);
  const wraps = top > 65535;
  if (wraps) past++;
  console.log(`region ${i}: firstVertex ${r.firstVertexIndex} vertices ${r.verticesCount} firstIndex ${r.firstTriangleIndex} indices ${r.triangleIndicesCount} top ${top}${wraps ? '  PAST 65535' : ''}`);
}
console.log(`vertices ${vertices}, regions ${div.regions.list([]).length}, past 65535: ${past}`);
