// StarCraft: Ghost models in the page (SPEC-VIEWER-GHOST 9, "In the
// page"): the nod format draws what NODExport exports. Needs GHOST_PATH.
// Engine state only: probes of the format, the pick buffer, the state.
import { test, expect } from '@playwright/test';
import { open, add, probe, itemOf, hitId, frames } from './ghost.mjs';

test('a static model: one group, the triangles of the file, picked at its pixel and not beside it', async ({ page }) => {
  const errors = await open(page);
  const id = await add(page, '3D/Models/crate.nod');
  await page.evaluate(() => window.sc2viewer.view('front'));
  await frames(page);
  const item = await itemOf(page, id);
  expect([item.game, item.loaded, item.undrawn]).toEqual(['ghost', true, []]);
  const layout = await probe(page, 'layout', id);
  const groups = await probe(page, 'groups', id);
  expect(groups.length).toBe(1);
  expect(groups[0]).toEqual(expect.objectContaining({ material: 'chestCrate2', kind: 'solid', triangles: layout.indexCount / 3, textureLoaded: true, drawnLast: true }));
  expect(layout.indexCount).toBeGreaterThan(0);
  const pixel = await page.evaluate((i) => window.sc2viewer.itemPixel(i), id);
  expect(pixel, 'the model has a pixel the pick finds').not.toBeNull();
  expect(await hitId(page, pixel)).toBe(id);
  // Negative: a pixel well beside it, still on the canvas, finds nothing.
  const box = await page.locator('#view').boundingBox();
  const beside = [pixel[0] - 300 > box.x + 5 ? pixel[0] - 300 : pixel[0] + 300, pixel[1]];
  expect(beside[0]).toBeGreaterThan(box.x);
  expect(beside[0]).toBeLessThan(box.x + box.width);
  expect(await hitId(page, beside)).toBeNull();
  expect(errors).toEqual([]);
});

test('axes: the drawn triangles face their vertex normals; unmirrored values do not', async ({ page }) => {
  const errors = await open(page);
  for (const name of ['crate', 'zergling', 'nova', 'lurker']) {
    const id = await add(page, `3D/Models/${name}.nod`);
    const { drawn, unmirrored } = await probe(page, 'axes', id);
    console.log('axes', name, JSON.stringify({ drawn, unmirrored }));
    const total = drawn.agree + drawn.disagree;
    expect(total).toBeGreaterThan(0);
    expect(drawn.agree / total, name).toBeGreaterThan(0.95);
    expect(unmirrored.agree / total, `${name} unmirrored`).toBeLessThan(0.05);
  }
  expect(errors).toEqual([]);
});

test('rest pose: a skinned model with no clip stands at the file positions; the docs sign of offset does not', async ({ page }) => {
  const errors = await open(page);
  for (const name of ['zergling', 'lurker_alt', 'Zangakar']) {
    const id = await add(page, `3D/Models/${name}.nod`);
    const { skinned, file } = await probe(page, 'positions', id);
    const { matrices, globals } = await probe(page, 'bones', id);
    const layout = await probe(page, 'layout', id);
    let worst = 0;
    skinned.forEach((p, v) => {
      const f = file[v];
      worst = Math.max(worst, Math.abs(p[0] - f[0]), Math.abs(p[1] + f[1]), Math.abs(p[2] - f[2]));
    });
    // The docs read matrix = global x move(-offset): with that sign each bone moves by twice its rest place.
    let docsWorst = 0;
    for (let b = 0; b < layout.bones; b++) {
      const g = globals.slice(b * 16, b * 16 + 16);
      const m = matrices.slice(b * 16, b * 16 + 16);
      // m = g x move(offset); g x move(-offset) moves the origin by g x (-offset) - g x 0.
      const moved = [m[12] - g[12], m[13] - g[13], m[14] - g[14]];
      docsWorst = Math.max(docsWorst, Math.hypot(...moved) * 2);
    }
    console.log('rest', name, JSON.stringify({ worst, docsWorst, bones: layout.bones, vertices: skinned.length }));
    expect(worst, name).toBeLessThan(1e-4);
    if (layout.bones > 1) expect(docsWorst, `${name} with -offset`).toBeGreaterThan(0.01);
  }
  expect(errors).toEqual([]);
});
