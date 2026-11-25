import { test, expect } from '../fixtures.mjs';
import { api } from '../api.mjs';
import { frames, idle, open, state, view } from '../page.mjs';

// Every skybox of the game loads without a viewer error. A skybox with a
// mesh has batches, is drawn in every direction, and every texture it names
// loads. One test walks all of them, so a failure lists every broken
// skybox. What a sky shows from inside is an operator check (SPEC-VIEWER 14).

// Files with no mesh at all: no vertices, regions, batches or materials
// (checked with scripts/parse-one.sh). They load and draw nothing.
const MESHLESS = ['arcadeskyboxspace_02', 'arcadeskyboxspaceterran_02', 'arcadeskyboxspacezerg_02'];
// Screen effects the renderer does not draw. They must be reported (the
// state lists them, the page warns), never dropped without a word.
const EFFECT_MATERIALS = /\((displacement|lens flare)\)$/;
// Look all around: a sky part (a moon, a parallax group) sits in one direction.
const DIRECTIONS = [
  [0, 0],
  [Math.PI / 2, 0],
  [Math.PI, 0],
  [-Math.PI / 2, 0],
  [0, 1.4],
  [0, -1.4],
];

test('every skybox loads; one with a mesh draws all of it with all its textures @slow', async ({ page, request }) => {
  test.setTimeout(180_000);
  const { items, total } = await (await request.get(api.backdrops('limit=500'))).json();
  expect(items.length).toBeGreaterThanOrEqual(60);
  // Every skybox, not the first page of them.
  expect(items).toHaveLength(total);

  const problems = [];
  const warned = new Set();
  let current = '';
  page.on('pageerror', (e) => problems.push(`${current}: pageerror ${e.message}`));
  page.on('console', (m) => {
    // The viewer logs a failed resource as "viewer: ..."; the page warns
    // about undrawn parts with "sc2viewer: NAME: not drawn: ...".
    if (m.text().startsWith('sc2viewer:') && m.text().includes('not drawn')) warned.add(current);
    else if (m.text().startsWith('viewer:') || m.type() === 'error') problems.push(`${current}: ${m.text()}`);
  });
  await page.goto('/');
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
  await page.evaluate(() => window.sc2viewer.setGrid(false));

  const report = [];
  const meshless = [];
  for (const sky of items) {
    current = sky.id;
    const thrown = await page.evaluate((choice) => window.sc2viewer.setSky(choice).then(() => null, (error) => error.message), sky);
    await idle(page);
    const s = await state(page);
    let drawn = 0;
    for (const [yaw, pitch] of DIRECTIONS) {
      await view(page, { yaw, pitch });
      await frames(page);
      if ((await state(page)).skyDrawn) drawn++;
    }
    report.push(
      `${sky.id} vertices=${s.skyVertices} batches=${s.skyBatches} textures=${s.skyTextures}/${s.skyTexturesWanted} ` +
        `undrawn=${s.skyUndrawn.length} bounds=${s.skyBoundsRadius.toFixed(1)} drawnIn=${drawn}/${DIRECTIONS.length} sequence=${s.skySequence}`,
    );
    if (thrown) problems.push(`${sky.id}: setSky threw ${thrown}`);
    for (const part of s.skyUndrawn) if (!EFFECT_MATERIALS.test(part)) problems.push(`${sky.id}: not drawn: ${part}`);
    // Undrawn parts are reported on the page, not only in the state.
    if (s.skyUndrawn.length && !warned.has(sky.id)) problems.push(`${sky.id}: undrawn parts without a warning`);
    if (s.skyVertices === 0) {
      meshless.push(sky.id);
      // Negative: a file with no mesh has no batch to draw.
      if (s.skyBatches !== 0) problems.push(`${sky.id}: no mesh, yet ${s.skyBatches} batches`);
      continue;
    }
    if (!s.skyLoaded) problems.push(`${sky.id}: a mesh, but no batch to draw`);
    if (s.skyTextures !== s.skyTexturesWanted) problems.push(`${sky.id}: ${s.skyTextures} of ${s.skyTexturesWanted} textures loaded`);
    // Not culled: the sky is drawn in every direction.
    if (drawn !== DIRECTIONS.length) problems.push(`${sky.id}: drawn in ${drawn} of ${DIRECTIONS.length} directions`);
  }
  console.log(report.join('\n'));
  expect(problems).toEqual([]);
  expect(meshless.sort()).toEqual([...MESHLESS].sort());
});

test('an uncompressed DDS texture decodes: spacesinglenebula3.dds', async ({ page, request }) => {
  // spacesinglenebula*.dds are 24-bit uncompressed DDS files (no FourCC).
  const head = await request.get(api.asset('assets/textures/spacesinglenebula3.dds'));
  expect(head.status()).toBe(200);
  const bytes = await head.body();
  expect(bytes.subarray(0, 4).toString('latin1')).toBe('DDS ');
  expect(bytes.readUInt32LE(80) & 0x4).toBe(0); // pixel format flags: no FourCC
  expect(bytes.readUInt32LE(80) & 0x40).toBe(0x40); // DDPF_RGB
  expect(bytes.readUInt32LE(88)).toBe(24); // bits per pixel

  // Decode it with the renderer's parser in the page: its size, and each
  // texel of the top level is the file's BGR triple with full alpha.
  await open(page);
  const image = await page.evaluate(async (url) => {
    const buffer = await (await fetch(url)).arrayBuffer();
    const file = new Uint8Array(buffer);
    const dds = new window.sc2viewer.DdsImage();
    dds.load(buffer);
    const top = dds.getMipmap(0);
    let differ = 0;
    let first = -1;
    for (let t = 0; t < dds.width * dds.height; t++) {
      const f = 128 + t * 3;
      const d = t * 4;
      if (top.data[d] !== file[f + 2] || top.data[d + 1] !== file[f + 1] || top.data[d + 2] !== file[f] || top.data[d + 3] !== 255) {
        differ++;
        if (first < 0) first = t;
      }
    }
    return { width: dds.width, height: dds.height, mipmaps: dds.mipmaps(), bytes: top.data.length, differ, first };
  }, api.asset('assets/textures/spacesinglenebula3.dds'));
  console.log('nebula', JSON.stringify(image));
  expect(image.width).toBe(bytes.readUInt32LE(16));
  expect(image.height).toBe(bytes.readUInt32LE(12));
  expect(image.mipmaps).toBe(bytes.readUInt32LE(28));
  expect(image.bytes).toBe(image.width * image.height * 4);
  expect(image.differ).toBe(0);
});
