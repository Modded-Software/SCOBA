// Renderer gap survey: for every unit model file, which M3 features the
// viewer does not support it uses. Prints one line per feature:
//   GAP <id> <models> <instances> <description>
// "models" counts model files using the feature; "instances" counts the
// materials, layers or entries. Feature ids match
// docs/specifications/GAP-ANALYSIS-WEBVIEWER.md.
//
// usage: node tools/gap-survey.mjs DATA_DIR [UNIT_ID]

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const [data, only] = process.argv.slice(2);
if (!data) throw new Error('usage: gap-survey.mjs DATA_DIR [UNIT_ID]');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
const byFile = new Map();
for (const [unit, path] of Object.entries(files)) if (!only || unit === only) if (!byFile.has(path)) byFile.set(path, unit);

// ---- tallies ----

const gaps = new Map(); // id -> { text, models: Set, count }
function gap(id, text, file, n = 1) {
  if (!gaps.has(id)) gaps.set(id, { text, models: new Set(), count: 0 });
  const g = gaps.get(id);
  g.models.add(file);
  g.count += n;
}
const values = new Map(); // id -> Map(value -> count), for distributions
function tally(id, value) {
  if (!values.has(id)) values.set(id, new Map());
  const m = values.get(id);
  m.set(value, (m.get(value) || 0) + 1);
}

// ---- constants (m3addon structures.xml) ----

const MATERIAL_TYPES = ['', 'standard', 'displacement', 'composite', 'terrain', 'volume', 'unknown', 'creep', 'volume noise', 'splat terrain bake', 'reflection', 'lens flare', 'buffer'];
const DRAWN_TYPES = new Set([1, 2, 3]);
const UV_SOURCES = ['explicit uv 0', 'explicit uv 1', 'reflective cubic env', 'reflective spherical env', 'planar local z', 'planar world z', 'particle flipbook', 'cubic env', 'spherical env', 'explicit uv 2', 'explicit uv 3', 'planar local x', 'planar local y', 'planar world x', 'planar world y', 'screen space', 'triplanar local', 'triplanar world', 'triplanar world local z'];
const UV_DRAWN = new Set([0, 1, 9, 10]);
const LAYERS = ['diffuse', 'decal', 'specular', 'gloss', 'emissive', 'emissive2', 'evio', 'evioMask', 'alphaMask', 'alphaMask2', 'normal', 'height', 'lightMap', 'ambientOcclusion'];
// Layers the shader never reads (standardmaterial.ts BOUND_LAYERS, standard.frag.ts).
const UNUSED_LAYERS = { gloss: 'L1', evio: 'L2', evioMask: 'L2', height: 'L3', lightMap: 'L4', ambientOcclusion: 'L5' };
const MATERIAL_FLAGS = [
  [0x1, 'M5', 'vertex colour (useVertexColor)'],
  [0x2, 'M5', 'vertex alpha (useVertexAlpha)'],
  [0x100, 'M6', 'depth prepass'],
  [0x10000, 'M7', 'transparency depth effects'],
  [0x8000, 'M8', 'decal lighting'],
  [0x80000, 'M8', 'double lambert (darkNormalMapping)'],
  [0x40000000, 'M8', 'clamp output'],
  [0x20000000, 'M9', 'excluded from mouse-over highlight'],
  [0x4000000, 'M10', 'background object'],
];
// Entries the parser skips (indexentry.ts UnsupportedEntry).
const SKIPPED_TAGS = {
  PAR_: ['E1', 'particle emitters'], PARC: ['E1', 'particle emitter copies'],
  RIB_: ['E2', 'ribbon emitters'], SRIB: ['E2', 'ribbon splines'],
  LITE: ['E3', 'lights'], PROJ: ['E4', 'projections (decals, shadow blobs)'],
  FOR_: ['E5', 'forces'], WRP_: ['E5', 'warps'],
  PHSH: ['E6', 'physics shapes'], PHRB: ['E6', 'rigid bodies'], PHYJ: ['E6', 'physics joints'], PHCC: ['E6', 'cloth'], PHAC: ['E6', 'cloth'], PHCL: ['E6', 'cloth'],
  PATU: ['E7', 'turret parts'], IKJT: ['E7', 'inverse kinematics'],
  BBSC: ['E8', 'billboards'],
  ATVL: ['E9', 'attachment volumes'], SSGS: ['E9', 'hit test shapes'], SHBX: ['E9', 'shadow boxes'], TRGD: ['E9', 'TRGD'], MSEC: ['E9', 'MSEC'], DMSE: ['E9', 'DMSE'],
};

const reverse = (s) => s.split('').reverse().join('');

/** Raw index: tag -> entry count (the parser keeps no count for skipped tags). */
function rawIndex(bytes) {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  const tagAt = (at) => reverse(String.fromCharCode(bytes[at], bytes[at + 1], bytes[at + 2], bytes[at + 3]));
  if (tagAt(0) !== 'MD34') throw new Error('not MD34');
  const offset = view.getUint32(4, true);
  const entries = view.getUint32(8, true);
  const counts = new Map();
  for (let i = 0; i < entries; i++) {
    const at = offset + i * 16;
    const tag = tagAt(at);
    counts.set(tag, (counts.get(tag) || 0) + view.getUint32(at + 8, true));
  }
  return counts;
}

function survey(file, bytes) {
  for (const [tag, n] of rawIndex(bytes)) if (SKIPPED_TAGS[tag] && n > 0) gap(SKIPPED_TAGS[tag][0], SKIPPED_TAGS[tag][1], file, n);

  const parsed = new M3Parser();
  parsed.load(bytes);
  const model = parsed.model;
  const animated = new Set();
  for (const sts of model.sts.list([])) for (const id of sts.animIds.list(new Uint32Array(0))) animated.add(id >>> 0);
  const isAnimated = (ref) => animated.has(ref.animId >>> 0);

  // Material types reached by batches, directly or through composites.
  const maps = model.materialReferences.list([]);
  const composites = model.materials[2].list([]);
  const div = model.divisions.first();
  const batches = div && div.batches.entries ? div.batches.list([]) : [];
  for (const batch of batches) {
    const map = maps[batch.materialReferenceIndex];
    const types = [map.materialType];
    if (map.materialType === 3) {
      for (const section of composites[map.materialIndex].sections.list([])) {
        types.push(maps[section.materialReferenceIndex].materialType);
        if (section.alphaFactor.initValue !== 1 || isAnimated(section.alphaFactor)) gap('C1', 'composite section alpha factor not 1 or animated', file);
      }
    }
    for (const t of types) if (!DRAWN_TYPES.has(t)) gap(`T${t}`, `material type ${t} (${MATERIAL_TYPES[t] || 'unknown'})`, file);
  }

  if (model.vertexFlags & 0x200) gap('V1', 'vertices carry colours (vertexFlags 0x200)', file);

  for (const m of model.materials[0].list([])) {
    if (m.depthBlendFalloff) gap('M1', 'depth blend falloff (soft particles)', file);
    if (m.cutoutThreshold) gap('M2', 'alpha cutout threshold', file);
    if (m.priority) gap('M3', 'material priority set (draw order)', file);
    if (m.blendMode > 5) gap('M4', `blend mode above 5`, file);
    tally('blendMode', m.blendMode);
    tally('layerBlendType', m.layerBlendType);
    tally('specType', m.specType);
    tally('emisMode', m.emisMode);
    for (const [bit, id, text] of MATERIAL_FLAGS) if (m.flags & bit) gap(id, text, file);
    if (m.envConstMult !== 1 || m.envDiffMult || m.envSpecMult) gap('M11', 'environment multipliers set', file);

    for (const name of LAYERS) {
      const ref = m[name + 'Layer'];
      if (!ref || !ref.entries) continue;
      const l = ref.first();
      const image = l.imagePath.get();
      const constant = l.flags & 0x400;
      if (!image && !constant) continue;
      if (UNUSED_LAYERS[name]) gap(UNUSED_LAYERS[name], `${name} layer (never read)`, file);
      const uv = l.uvSource;
      if (!UV_DRAWN.has(uv)) gap(`U${uv}`, `uv source ${uv} (${UV_SOURCES[uv] || 'unknown'})`, file);
      if (name === 'normal' && uv !== 0) gap('U-normal', 'normal map on a uv set other than 0', file);
      if (isAnimated(l.uvOffset) || isAnimated(l.uvAngle) || isAnimated(l.uvTiling)) gap('A1', 'animated uv offset, angle or tiling', file);
      const [ox, oy] = l.uvOffset.initValue;
      const [ax, ay, az] = l.uvAngle.initValue;
      const [tx, ty] = l.uvTiling.initValue;
      if (ox || oy || ax || ay || az || tx !== 1 || ty !== 1) gap('A2', 'static uv offset, angle or tiling', file);
      if (l.flags & 0x100 || l.flipBookRows * l.flipBookColumns > 1) gap('A3', 'flipbook', file);
      if (l.flags & 0x200) gap('A4', 'video texture', file);
      if (constant) gap('A5', 'constant colour layer (colorEnabled)', file);
      if (isAnimated(l.color)) gap('A6', 'animated layer colour', file);
      if (l.brightMult.initValue !== 1 || isAnimated(l.brightMult)) gap('A7', 'bright multiply not 1 or animated', file);
      if (l.midtoneOffset.initValue || isAnimated(l.midtoneOffset)) gap('A7', 'midtone offset set or animated', file);
      if (l.brightness.initValue !== 1 || isAnimated(l.brightness)) tally('brightness', `${l.brightness.initValue}${isAnimated(l.brightness) ? ' animated' : ''}`);
      if (l.fresnelType) gap('F1', 'fresnel', file);
      if (l.noiseAmp) gap('A8', 'noise', file);
      if (l.rttChannel >= 0) gap('A9', 'render target channel', file);
      if (l.flags & 0x10) tally('invert', name);
    }
  }
  for (const d of model.materials[1].list([])) if (isAnimated(d.strengthFactor)) gap('D1', 'displacement strength animated', file);
}

let checked = 0;
const unparsable = [];
for (const [file, unit] of byFile) {
  let bytes;
  try {
    const buffer = await readFile(file);
    bytes = new Uint8Array(buffer.buffer, buffer.byteOffset, buffer.byteLength);
    survey(file, bytes);
    checked++;
  } catch (error) {
    unparsable.push(`${unit}: ${error.message}`);
  }
}

console.log(`model files: ${byFile.size}, surveyed: ${checked}, unparsable: ${unparsable.length}`);
for (const [id, g] of [...gaps.entries()].sort((a, b) => b[1].models.size - a[1].models.size)) console.log(`GAP\t${id}\t${g.models.size}\t${g.count}\t${g.text}`);
for (const [id, m] of values) console.log(`VALUES ${id}: ${[...m.entries()].sort((a, b) => b[1] - a[1]).map(([v, n]) => `${v}=${n}`).join(' ')}`);
for (const line of unparsable) console.log('UNPARSABLE ' + line);
