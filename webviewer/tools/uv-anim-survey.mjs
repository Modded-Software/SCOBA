// Layers whose UV offset, angle or tiling a sequence drives (gap A1).
// One line per layer:
//   UVANIM <unit> <material> <layer> mesh=<yes|no> tracks=<offset,angle,tiling> seqs=<names>
// mesh=yes: a mesh batch draws the material (else particles or ribbons use it).
// Then units with no UV transform at all (static identity):
//   STATIC <unit>   (first 20)
// and every model the parser cannot read:
//   UNPARSABLE <unit>: <error>
//
// usage: node tools/uv-anim-survey.mjs DATA_DIR [UNIT_ID]

import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { join } from 'node:path';

const require = createRequire(import.meta.url);
const { M3Parser } = require('../build/m3parser.cjs');

const LAYERS = ['diffuse', 'decal', 'specular', 'emissive', 'emissive2', 'alphaMask', 'alphaMask2', 'normal'];

const [data, only] = process.argv.slice(2);
if (!data) throw new Error('usage: uv-anim-survey.mjs DATA_DIR [UNIT_ID]');
const files = JSON.parse(await readFile(join(data, 'catalog', 'unit-files.json'), 'utf8'));
const byFile = new Map();
for (const [unit, path] of Object.entries(files)) if (!only || unit === only) if (!byFile.has(path)) byFile.set(path, unit);

/** One unit only: every STC's keys and values for the track. */
function printKeys(track, ref, stcs) {
  const id = ref.animId >>> 0;
  for (const stc of stcs) {
    const ids = stc.animIds.list(new Uint32Array(0));
    const at = [...ids].findIndex((x) => x >>> 0 === id);
    if (at < 0) continue;
    const uints = stc.animRefs.list(new Uint32Array(0));
    const pairs = new Uint16Array(uints.buffer, uints.byteOffset, uints.length * 2);
    const sd = stc.sd[pairs[at * 2 + 1]].get()[pairs[at * 2]];
    const keys = [...sd.keys.list(new Int32Array(0))];
    const vals = sd.values.list([]).map((v) => (typeof v === 'number' ? v.toFixed(4) : `(${[...v].map((x) => x.toFixed(4))})`));
    console.log(`  KEYS ${track} stc="${stc.name.get()}" interp=${ref.interpolationType} init=(${[...ref.initValue].map((x) => x.toFixed(4))}) ${keys.map((k, i) => `${k}:${vals[i]}`).join(' ')}`);
  }
}

const staticUnits = [];
const unparsable = [];
let driven = 0;
for (const [path, unit] of byFile) {
  const bytes = await readFile(path);
  const parsed = new M3Parser();
  try {
    parsed.load(new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength));
  } catch (error) {
    unparsable.push(`${unit}: ${error.message}`);
    continue;
  }
  const model = parsed.model;
  const stcs = model.stc.list([]);
  const stgs = model.stg.list([]);
  const sequences = model.sequences.list([]);
  // animId -> names of the sequences whose STG has an STC holding it.
  const seqsOf = new Map();
  stgs.forEach((stg, s) => {
    for (const i of stg.stcIndices.list(new Uint32Array(0))) {
      for (const id of stcs[i].animIds.list(new Uint32Array(0))) {
        const key = id >>> 0;
        if (!seqsOf.has(key)) seqsOf.set(key, new Set());
        seqsOf.get(key).add(sequences[s] ? sequences[s].name.get() : `#${s}`);
      }
    }
  });
  // Standard materials a mesh batch draws, directly or as a composite section
  // (others serve particles or ribbons, which the viewer does not draw).
  const maps = model.materialReferences.list([]);
  const composites = model.materials[2].list([]);
  const div = model.divisions.first();
  const meshDrawn = new Set();
  const reach = (mapIndex) => {
    const map = maps[mapIndex];
    if (map.materialType === 1) meshDrawn.add(map.materialIndex);
    if (map.materialType === 3) for (const s of composites[map.materialIndex].sections.list([])) reach(s.materialReferenceIndex);
  };
  for (const batch of div && div.batches.entries ? div.batches.list([]) : []) reach(batch.materialReferenceIndex);
  let any = false;
  for (const [mi, m] of model.materials[0].list([]).entries()) {
    for (const name of LAYERS) {
      const ref = m[name + 'Layer'];
      if (!ref || !ref.entries) continue;
      const l = ref.first();
      if (!l.imagePath.get()) continue;
      const tracks = [['offset', l.uvOffset], ['angle', l.uvAngle], ['tiling', l.uvTiling]].filter(([, r]) => seqsOf.has(r.animId >>> 0));
      const [ox, oy] = l.uvOffset.initValue;
      const az = l.uvAngle.initValue[2];
      const [tx, ty] = l.uvTiling.initValue;
      if (tracks.length || ox || oy || az || (tx !== 1 && tx !== 0) || (ty !== 1 && ty !== 0)) any = true;
      if (!tracks.length) continue;
      driven++;
      const seqs = new Set();
      for (const [, r] of tracks) for (const s of seqsOf.get(r.animId >>> 0)) seqs.add(s);
      console.log(`UVANIM ${unit} ${m.name.get()} ${name} mesh=${meshDrawn.has(mi) ? 'yes' : 'no'} tracks=${tracks.map(([t]) => t).join(',')} seqs=${[...seqs].join(',')}`);
      if (only) for (const [track, r] of tracks) printKeys(track, r, stcs);
    }
  }
  if (!any) staticUnits.push(unit);
}
for (const unit of staticUnits.slice(0, 20)) console.log(`STATIC ${unit}`);
for (const line of unparsable) console.log('UNPARSABLE ' + line);
console.log(`driven layers ${driven}; units with no uv transform ${staticUnits.length} of ${byFile.size}`);
