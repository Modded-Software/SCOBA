// Displacement materials (DIS_) of every unit model: strength factor (and
// whether it is animated), flags, priority, and the normal and strength
// layer images with their channel setting.
//
// usage: node tools/displacement-survey.mjs DATA_DIR [UNIT_ID]

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const [data, only] = process.argv.slice(2);
if (!data) throw new Error('usage: displacement-survey.mjs DATA_DIR [UNIT_ID]');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
const byFile = new Map();
for (const [unit, path] of Object.entries(files)) if (!only || unit === only) if (!byFile.has(path)) byFile.set(path, unit);

const layerText = (ref) => {
  if (!ref.entries) return 'none';
  const layer = ref.first();
  const path = layer.imagePath.get();
  return `${path || '(no image)'} channels=${layer.colorChannelSetting} uv=${layer.uvSource} flags=0x${(layer.flags >>> 0).toString(16)}`;
};

let models = 0;
let materials = 0;
const strengths = [];
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
  const list = model.materials[1].list([]);
  if (!list.length) continue;
  models++;
  console.log(`${unit} ${path}`);
  for (const [i, m] of list.entries()) {
    materials++;
    strengths.push(m.strengthFactor.initValue);
    console.log(`  DIS ${i} "${m.name.get()}" strength=${m.strengthFactor.initValue} animated=${m.strengthFactor.animId !== 0xffffffff && m.strengthFactor.animId !== -1} flags=0x${(m.flags >>> 0).toString(16)} priority=${m.priority} unknown0=${m.unknown0}`);
    console.log(`    normal   ${layerText(m.normalLayer)}`);
    console.log(`    strength ${layerText(m.strengthLayer)}`);
  }
}
for (const line of unparsable) console.log('UNPARSABLE ' + line);
strengths.sort((a, b) => a - b);
console.log(`models with displacement: ${models}; materials: ${materials}; strength min ${strengths[0]} median ${strengths[strengths.length >> 1]} max ${strengths.at(-1)}`);
