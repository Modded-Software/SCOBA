// Write a small HD texture viewer for the tests: the real page template
// (scripts/hdtex/compare.html) filled with four entries, and their images.
//
//   node tools/hdtex-fixture.mjs <template> <icons folder> <out folder> [<models cache folder> <dds file> <2048 dds file>]
//
// The entries: two used by the unit Marine, one by the doodad ZerusTree, one
// terrain texture. No entry is used by the Zergling, for the negative tests.
import { copyFile, mkdir, readFile, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

const DATA_MARK = '/*PAIRS*/[]'; // scripts/hdtex/compare.py
const [template, icons, out, models, skin, large] = process.argv.slice(2);
if (!template || !icons || !out) {
  console.error('usage: hdtex-fixture.mjs <template> <icons folder> <out folder> [<models cache folder> <dds file> <2048 dds file>]');
  process.exit(2);
}

const BEFORE = 'btn-unit-terran-marine.png';
const AFTER = 'btn-unit-zerg-zergling.png';

function pair(id, source, category, users, role) {
  const [texture, plane] = id.split('.');
  return {
    id,
    source,
    category,
    users,
    texture: `${texture}.dds`,
    role,
    plane,
    format: 'DXT5',
    before: 'img/original.png',
    thumb: 'img/original.png',
    before_size: [76, 76],
    note: '',
    seam_source: 0.5,
    layers: [{ variant: 'Upscale 4x', image: 'img/upscale.png', size: [76, 76], model: 'fast', encode_psnr: 40, correlation: 0.99, coarse_rmse: 0.2, seam: 0.1 }],
  };
}

const pairs = [
  pair('zerus_1.color', 'terrain', 'Terrain', ['Zerus1'], 'color'),
  // A texture the SCOBA Marine's model does name: the viewer must not list it a second time.
  pair('marine_remastered_diff.color', 'models', 'Marine', ['Marine'], 'color'),
  pair('marine_normal.normal', 'models', 'Marine', ['Marine'], 'normal'),
  pair('zerustree_diffuse.color', 'models', 'Doodads', ['ZerusTree'], 'color'),
];

const page = await readFile(template, 'utf8');
if (page.split(DATA_MARK).length !== 2) throw new Error(`${template} must hold ${DATA_MARK} exactly once`);
await rm(out, { recursive: true, force: true });
await mkdir(join(out, 'img'), { recursive: true });
await copyFile(join(icons, BEFORE), join(out, 'img', 'original.png'));
await copyFile(join(icons, AFTER), join(out, 'img', 'upscale.png'));
await writeFile(join(out, 'index.html'), page.replace(DATA_MARK, JSON.stringify(pairs)));
console.log(`hdtex fixture: ${pairs.length} entries in ${out}`);

// The cache of upscaled model textures (src/games/sc2/server/textures.ts hdRoute), two textures:
// - the Zergling's skin, whose "HD" file is another picture (`skin`), so the
//   tests can tell the two sets apart in the view; it is not a large one;
// - the Roach's skin, whose "HD" file is a 2048 picture (`large`). The Roach,
//   because no other test measures its colours.
if (models) {
  if (!skin || !large) throw new Error('the models cache needs two DDS files to stand in for the HD textures');
  await rm(models, { recursive: true, force: true });
  await mkdir(join(models, 'dds'), { recursive: true });
  await copyFile(skin, join(models, 'dds', 'scoba_hd_m_zergling_diffuse.dds'));
  await copyFile(large, join(models, 'dds', 'scoba_hd_m_roach_diffuse.dds'));
  const manifest = {
    source: 'models',
    textures: [
      { asset: 'assets\\textures\\zergling_diffuse.dds', file: 'dds/scoba_hd_m_zergling_diffuse.dds' },
      { asset: 'assets\\textures\\roach_diffuse.dds', file: 'dds/scoba_hd_m_roach_diffuse.dds' },
    ],
  };
  await writeFile(join(models, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
  console.log(`hdtex fixture: ${manifest.textures.length} HD model textures in ${models}`);
}
