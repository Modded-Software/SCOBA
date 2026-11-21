// Texture coordinate ranges of every unit model, per region, decoded two
// ways: the old rule (stored / 2048, the scale 16 assumed) and the file's
// rule (REGN version 5: stored * (uvwMult / 16) / 2048 + uvwOffset).
// A region whose first UV set spans far more than the texture (beyond
// [-0.5, 1.5]) tiles its texture many times: the "smallpox" look.
//
// usage: node tools/uv-survey.mjs DATA_DIR [UNIT_ID]

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const UV_BITS = [0x20000, 0x40000, 0x80000, 0x100000, 0x40000000];
const LOW = -0.5;
const HIGH = 1.5;

const [data, only] = process.argv.slice(2);
if (!data) throw new Error('usage: uv-survey.mjs DATA_DIR [UNIT_ID]');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
const byFile = new Map();
for (const [unit, path] of Object.entries(files)) if (!only || unit === only) if (!byFile.has(path)) byFile.set(path, unit);

let checked = 0;
const multsSeen = new Map();
const oldOut = [];
const newOut = [];
const unparsable = [];
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
  const flags = model.vertexFlags >>> 0;
  if (!div || !div.regions.entries || !model.vertices.entries || !(flags & 0x20000)) continue;
  const vertices = model.vertices.get();
  const view = new DataView(vertices.buffer, vertices.byteOffset, vertices.byteLength);
  const stride = 28 + 4 * UV_BITS.filter((bit) => flags & bit).length + (flags & 0x200 ? 4 : 0);
  const uvAt = 24 + (flags & 0x200 ? 4 : 0);
  checked++;
  let oldBad = 0;
  let newBad = 0;
  const lines = [];
  for (const [index, region] of div.regions.get().entries()) {
    const key = `v${region.version} mult=${region.uvwMult} offset=${region.uvwOffset}`;
    multsSeen.set(key, (multsSeen.get(key) || 0) + 1);
    let min = Infinity;
    let max = -Infinity;
    // Per axis too: [u min, u max, v min, v max].
    const axes = [Infinity, -Infinity, Infinity, -Infinity];
    for (let v = region.firstVertexIndex; v < region.firstVertexIndex + region.verticesCount; v++) {
      for (const k of [0, 2]) {
        const raw = view.getInt16(v * stride + uvAt + k, true);
        min = Math.min(min, raw);
        max = Math.max(max, raw);
        axes[k] = Math.min(axes[k], raw);
        axes[k + 1] = Math.max(axes[k + 1], raw);
      }
    }
    const old = [min / 2048, max / 2048];
    const scale = region.uvwMult / 16 / 2048;
    const now = [min * scale + region.uvwOffset, max * scale + region.uvwOffset];
    if (old[0] < LOW || old[1] > HIGH) oldBad++;
    if (now[0] < LOW || now[1] > HIGH) newBad++;
    const file = axes.map((c) => (c * scale + region.uvwOffset).toFixed(3));
    lines.push(`  region ${index} ${key} old [${old.map((x) => x.toFixed(2))}] file [${now.map((x) => x.toFixed(2))}] u [${file[0]}, ${file[1]}] v [${file[2]}, ${file[3]}]`);
  }
  if (oldBad) oldOut.push(`${unit}: ${oldBad} region(s)`);
  if (newBad) newOut.push(`${unit}: ${newBad} region(s)`);
  if (only) console.log(`${unit} ${path}\n${lines.join('\n')}`);
}
console.log('region UV rules seen:');
for (const [key, count] of [...multsSeen.entries()].sort((a, b) => b[1] - a[1])) console.log(`  ${key} x${count}`);
for (const line of newOut) console.log('OUT OF RANGE (file rule) ' + line);
for (const line of unparsable) console.log('UNPARSABLE ' + line);
console.log(`checked ${checked} model files; out of [${LOW}, ${HIGH}]: old rule ${oldOut.length} models, file rule ${newOut.length} models`);
