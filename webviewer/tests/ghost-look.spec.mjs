// StarCraft: Ghost materials in the page (SPEC-VIEWER-GHOST 9, "In the
// page"): the shader table decides which groups are drawn, which are named
// as not drawn, and which are left out unnamed; a refused model is
// reported. Needs GHOST_PATH. Engine state only: probes and the pick.
import { test, expect } from '@playwright/test';
import { open, add, probe, itemOf, frameItem, triangleHits } from './ghost.mjs';
// Built by src/tools/build.ts from src/games/ghost/server/container.ts.
import { packContainer } from '../build/ghost-container.mjs';

const ratio = ({ hit, miss }) => hit / Math.max(1, hit + miss);

test('a cutout group: its texture leaves holes the pick sees; a solid group has none', async ({ page }) => {
  const errors = await open(page);
  const crate = await add(page, '3D/Models/crate.nod');
  await frameItem(page, crate);
  const solid = await triangleHits(page, crate, 0);
  await page.evaluate((i) => window.sc2viewer.remove(i), crate);
  const vine = await add(page, '3D/Models/AR_Plant_Vine_01.nod');
  await frameItem(page, vine);
  const groups = await probe(page, 'groups', vine);
  const cut = groups.findIndex((g) => g.kind === 'cutout');
  expect(cut, JSON.stringify(groups)).toBeGreaterThanOrEqual(0);
  expect(groups[cut].textureLoaded).toBe(true);
  const masked = await triangleHits(page, vine, cut);
  console.log('cutout', JSON.stringify({ solid, masked }));
  expect(ratio(solid)).toBeGreaterThan(0.97);
  expect(masked.hit).toBeGreaterThan(0);
  // Negative: inside the cutout triangles some points are not the model.
  expect(ratio(masked)).toBeLessThan(ratio(solid) - 0.05);
  expect(errors).toEqual([]);
});

test('an unknown shader and a material no step finds: not drawn, named in undrawn', async ({ page }) => {
  const errors = await open(page);
  for (const [name, why] of [['3_3_2_Room01_FieldPanel02', 'shader dynamic is not drawn'], ['pCannon_collide', 'found by no step of the material lookup']]) {
    const id = await add(page, `3D/Models/${name}.nod`);
    await frameItem(page, id);
    const groups = await probe(page, 'groups', id);
    const named = groups.filter((g) => g.why === why);
    expect(named.length, `${name}: ${JSON.stringify(groups)}`).toBeGreaterThan(0);
    const item = await itemOf(page, id);
    for (const g of named) {
      expect(g.kind).toBeNull();
      expect(g.undrawn).toBe(`${g.material}: ${why}`);
      // Negative: a named group is not drawn.
      expect(g.drawnLast).toBe(false);
      expect(item.undrawn).toContain(`group ${g.index} ${g.undrawn}`);
    }
    // Every named group, and only those, is in the item's list.
    expect(item.undrawn.length).toBe(groups.filter((g) => g.undrawn !== null).length);
    await page.evaluate((i) => window.sc2viewer.remove(i), id);
  }
  expect(errors).toEqual([]);
});

test('a sky material: not drawn and not named', async ({ page }) => {
  const errors = await open(page);
  const id = await add(page, '3D/Models/swdemoSKY.nod');
  await frameItem(page, id);
  const groups = await probe(page, 'groups', id);
  const sky = groups.filter((g) => g.shader === 'sky');
  expect(sky.length, JSON.stringify(groups)).toBeGreaterThan(0);
  const item = await itemOf(page, id);
  for (const g of sky) {
    expect([g.kind, g.undrawn, g.why, g.drawnLast]).toEqual([null, null, null, false]);
    expect(item.undrawn.some((u) => u.startsWith(`group ${g.index} `))).toBe(false);
  }
  expect(errors).toEqual([]);
});

/** A container whose JSON is { error }: what the server sends for a model NODExport refused, by the server's own code. */
const refusedBody = (message) => packContainer({ error: message });

test('negative: without its shader file a model does not load, and the file is named', async ({ page }) => {
  await page.route('**/shaders/nod.frag', (route) => route.fulfill({ status: 404, body: 'gone' }));
  await page.goto('/');
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready, null, { timeout: 20_000 });
  const result = await page.evaluate(() => window.sc2viewer.add('3D/Models/crate.nod', { game: 'ghost' }).then(() => 'added', (e) => 'failed: ' + e.message));
  expect(result).toBe('failed: nod: 404 /shaders/nod.frag');
  expect((await page.evaluate(() => window.sc2viewer.state())).items).toEqual([]);
});

test('a refused model is reported with its error and not added', async ({ page }) => {
  const errors = await open(page);
  await page.route('**/api/ghost/file?*', (route) => {
    const path = new URL(route.request().url()).searchParams.get('path') ?? '';
    if (path.toLowerCase().endsWith('crate.nod')) return route.fulfill({ status: 200, contentType: 'application/octet-stream', body: refusedBody('bad group table') });
    return route.continue();
  });
  const result = await page.evaluate(() => window.sc2viewer.add('3D/Models/crate.nod', { game: 'ghost' }).then(() => 'added', (e) => 'failed: ' + e.message));
  expect(result).toContain('refused: bad group table');
  await expect(page.locator('#status')).toContainText('bad group table');
  expect((await page.evaluate(() => window.sc2viewer.state())).items).toEqual([]);
  // Negative: another model of the same game still loads.
  const other = await add(page, '3D/Models/zergling.nod');
  expect((await itemOf(page, other)).loaded).toBe(true);
  expect(errors).toEqual([]);
});
