// Print the standard materials of one unit's model: flags, blend mode and,
// per layer, texture path, flags, uv source and channel setting.
//
// usage: node tools/m3-materials.mjs DATA_DIR UNIT_ID

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const LAYERS = ['diffuse', 'decal', 'specular', 'gloss', 'emissive', 'emissive2', 'evio', 'evioMask',
  'alphaMask', 'alphaMask2', 'normal', 'height', 'lightMap', 'ambientOcclusion'];

const [data, unit] = process.argv.slice(2);
if (!data || !unit) throw new Error('usage: m3-materials.mjs DATA_DIR UNIT_ID');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
const path = files[unit];
if (!path) throw new Error(`no model file for ${unit}`);
const bytes = await readFile(path);
const parsed = new M3Parser();
parsed.load(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength));
const hex = (n) => '0x' + (n >>> 0).toString(16);

console.log(path);
for (const m of parsed.model.materials[0].get()) {
  console.log(`MAT ${m.name.get()} v${m.version} flags=${hex(m.flags)} add=${hex(m.additionalFlags)} blend=${m.blendMode}`
    + ` layerBlend=${m.layerBlendType} emisBlend=${m.emisBlendType} emisMode=${m.emisMode} specType=${m.specType}`
    + ` spec=${m.specularity} specMult=${m.specMult} emisMult=${m.emisMult}`);
  for (const name of LAYERS) {
    const ref = m[name + 'Layer'];
    if (!ref || !ref.entries) continue;
    const l = ref.first();
    const image = l.imagePath.get();
    // Flag 0x400: a constant colour layer (no texture); its colour is the animated `color`.
    const constant = l.flags & 0x400;
    if (!image && !constant) continue;
    const color = constant ? ` color=(${[...l.color.initValue].join(',')}) bgra` : '';
    console.log(`  ${name}: ${image || '(constant colour)'} flags=${hex(l.flags)} uv=${l.uvSource} ch=${l.colorChannelSetting}${color}`);
  }
}
