import { test, expect } from '@playwright/test';

// Every skybox of the game loads without a viewer error. A skybox with a
// mesh draws, every batch of it is drawn, and every texture it names loads.
// One test walks all of them, so a failure lists every broken skybox.

// Files with no mesh at all: no vertices, regions, batches or materials
// (checked with scripts/parse-one.sh). They load and draw nothing.
const MESHLESS = ['arcadeskyboxspace_02', 'arcadeskyboxspaceterran_02', 'arcadeskyboxspacezerg_02'];
// Screen effects the renderer does not draw. They must be reported (the
// state lists them, the page warns), never dropped without a word.
const EFFECT_MATERIALS = /\((displacement|lens flare)\)$/;
// Files in the skybox folders that show nothing from the sky camera (at
// their origin) in any direction, though they load, are not culled, and
// draw from outside. Measured 2026-11-21, seen from 60 units:
// - charskyparallax_prtmdl_group01: a prop (radius 7.5), 11207 px outside;
// - planet_skybox_moon: radius 13.4 yet only 16 px outside, not explained;
// - zerg_vision_border: a 0.1 unit model, 3 px outside.
const EMPTY_FROM_INSIDE = ['charskyparallax_prtmdl_group01', 'planet_skybox_moon', 'zerg_vision_border'];
// Look all around: a sky part (a moon, a parallax group) sits in one direction.
const DIRECTIONS = [
  [0, 0],
  [Math.PI / 2, 0],
  [Math.PI, 0],
  [-Math.PI / 2, 0],
  [0, 1.4],
  [0, -1.4],
];

test('every skybox loads; one with a mesh draws all of it with all its textures', async ({ page, request }) => {
  test.setTimeout(180_000);
  const { items } = await (await request.get('/api/skyboxes')).json();
  expect(items.length).toBeGreaterThanOrEqual(60);

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
  const emptyFromInside = [];
  for (const sky of items) {
    current = sky.id;
    const thrown = await page.evaluate((choice) => window.sc2viewer.setSky(choice).then(() => null, (error) => error.message), sky);
    await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 30_000 });
    const s = await page.evaluate(() => window.sc2viewer.state());
    let covered = 0;
    let drawn = 0;
    for (const [yaw, pitch] of DIRECTIONS) {
      await page.evaluate(([yaw, pitch]) => window.sc2viewer.view({ yaw, pitch }), [yaw, pitch]);
      covered += (await page.evaluate(() => window.sc2viewer.pixels())).covered;
      if ((await page.evaluate(() => window.sc2viewer.state())).skyDrawn) drawn++;
    }
    report.push(
      `${sky.id} vertices=${s.skyVertices} batches=${s.skyBatches} textures=${s.skyTextures}/${s.skyTexturesWanted} covered=${covered} ` +
        `undrawn=${s.skyUndrawn.length} bounds=${s.skyBoundsRadius.toFixed(1)} drawnIn=${drawn}/${DIRECTIONS.length} sequence=${s.skySequence}`,
    );
    if (thrown) problems.push(`${sky.id}: setSky threw ${thrown}`);
    for (const part of s.skyUndrawn) if (!EFFECT_MATERIALS.test(part)) problems.push(`${sky.id}: not drawn: ${part}`);
    // Undrawn parts are reported on the page, not only in the state.
    if (s.skyUndrawn.length && !warned.has(sky.id)) problems.push(`${sky.id}: undrawn parts without a warning`);
    if (s.skyVertices === 0) {
      meshless.push(sky.id);
      // Negative: a file with no mesh draws nothing.
      if (covered !== 0) problems.push(`${sky.id}: no mesh, yet ${covered} pixels drawn`);
      continue;
    }
    if (!s.skyLoaded) problems.push(`${sky.id}: a mesh, but no batch to draw`);
    if (s.skyTextures !== s.skyTexturesWanted) problems.push(`${sky.id}: ${s.skyTextures} of ${s.skyTexturesWanted} textures loaded`);
    if (covered === 0) {
      // Raw values: the same file as a scene model, seen from outside.
      const outside = await page.evaluate(async (file) => {
        await window.sc2viewer.setSky(null);
        await window.sc2viewer.add(file, { x: 0, y: 0 });
        window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: 0.5, distance: 60, target: [0, 0, 0] });
        const p = window.sc2viewer.pixels();
        const item = window.sc2viewer.state().items[0];
        window.sc2viewer.clear();
        return { covered: p.covered, drawn: item.drawn, bounds: item.boundsRadius };
      }, sky.file);
      report.push(`  ${sky.id} from outside: ${JSON.stringify(outside)}`);
      emptyFromInside.push(sky.id);
      if (!(outside.covered > 0)) problems.push(`${sky.id}: nothing drawn, not even from outside`);
    }
  }
  console.log(report.join('\n'));
  expect(problems).toEqual([]);
  expect(meshless.sort()).toEqual([...MESHLESS].sort());
  expect(emptyFromInside.sort()).toEqual([...EMPTY_FROM_INSIDE].sort());
});

test('an uncompressed DDS texture decodes: spacesinglenebula3.dds', async ({ page, request }) => {
  // spacesinglenebula*.dds are 24-bit uncompressed DDS files (no FourCC).
  const head = await request.get('/asset?path=' + encodeURIComponent('assets/textures/spacesinglenebula3.dds'));
  expect(head.status()).toBe(200);
  const bytes = await head.body();
  expect(bytes.subarray(0, 4).toString('latin1')).toBe('DDS ');
  expect(bytes.readUInt32LE(80) & 0x4).toBe(0); // pixel format flags: no FourCC
  expect(bytes.readUInt32LE(80) & 0x40).toBe(0x40); // DDPF_RGB
  expect(bytes.readUInt32LE(88)).toBe(24); // bits per pixel

  // Decode it with the renderer's parser in the page: size and colours.
  await page.goto('/');
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
  const image = await page.evaluate(async () => {
    const buffer = await (await fetch('/asset?path=' + encodeURIComponent('assets/textures/spacesinglenebula3.dds'))).arrayBuffer();
    const dds = new ModelViewer.parsers.dds.Image();
    dds.load(buffer);
    const top = dds.getMipmap(0);
    let lit = 0;
    for (let i = 0; i < top.data.length; i += 4) if (top.data[i] + top.data[i + 1] + top.data[i + 2] > 60) lit++;
    return { width: dds.width, height: dds.height, mipmaps: dds.mipmaps(), bytes: top.data.length, lit, alpha: top.data[3] };
  });
  console.log('nebula', JSON.stringify(image));
  expect(image.width).toBe(bytes.readUInt32LE(16));
  expect(image.height).toBe(bytes.readUInt32LE(12));
  expect(image.mipmaps).toBe(bytes.readUInt32LE(28));
  expect(image.bytes).toBe(image.width * image.height * 4);
  // A nebula: some pixels are lit, not a black or empty decode.
  expect(image.lit).toBeGreaterThan(100);
  expect(image.alpha).toBe(255); // no alpha mask: opaque
});
