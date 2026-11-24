// StarCraft: Ghost next to the core (SPEC-VIEWER-GHOST 9, "In the page"):
// the palette and the material lookup, a model without clips, what a Ghost
// instance does not offer, and one instance of each game in one scene.
// Needs GHOST_PATH. Engine state only: probes, the state, the scene.
import { test, expect } from '@playwright/test';
import { open, add, probe, itemOf, frames } from './ghost.mjs';
import { sceneOf, reloadScene } from './scene.mjs';

test('the palette: each skinned vertex lies near its main bone; read one bone off, it does not', async ({ page }) => {
  const errors = await open(page);
  for (const name of ['zergling', 'lurker_alt']) {
    const id = await add(page, `3D/Models/${name}.nod`);
    const right = await probe(page, 'boneSpread', id, 0);
    const off = await probe(page, 'boneSpread', id, 1);
    console.log('palette', name, JSON.stringify({ right, off }));
    expect(right.vertices).toBeGreaterThan(0);
    expect(off.vertices).toBe(right.vertices);
    // Negative: a palette read one bone off puts the vertices farther from their bones.
    expect(right.mean, name).toBeLessThan(off.mean * 0.8);
  }
  expect(errors).toEqual([]);
});

test('the material lookup: zergling and crate draw with a texture', async ({ page }) => {
  const errors = await open(page);
  for (const name of ['zergling', 'crate']) {
    const id = await add(page, `3D/Models/${name}.nod`);
    await page.evaluate(() => window.sc2viewer.view('front'));
    await frames(page);
    const groups = await probe(page, 'groups', id);
    const drawn = groups.filter((g) => g.kind !== null);
    expect(drawn.length, `${name}: ${JSON.stringify(groups)}`).toBeGreaterThan(0);
    for (const g of drawn) expect([g.material, g.textureLoaded, g.drawnLast]).toEqual([g.material, true, true]);
    expect((await itemOf(page, id)).undrawn).toEqual([]);
    await page.evaluate((i) => window.sc2viewer.remove(i), id);
  }
  expect(errors).toEqual([]);
});

test('a model without a motion set: no sequences; asking for a clip changes no bone', async ({ page }) => {
  const errors = await open(page);
  const id = await add(page, '3D/Models/crate.nod');
  const item = await itemOf(page, id);
  expect([item.sequences, item.sequence]).toEqual([[], -1]);
  const before = (await probe(page, 'bones', id)).matrices;
  // Negative: clip 0 does not exist, the instance stays in its rest pose.
  expect(await probe(page, 'holdAt', id, 0, 500)).toEqual({ sequence: -1, frame: 500 });
  expect((await probe(page, 'bones', id)).matrices).toEqual(before);
  expect(errors).toEqual([]);
});

test('a Ghost instance has no team colour control and no hd option', async ({ page }) => {
  const errors = await open(page);
  const marine = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: -2, y: 0, pick: 0.5, sequence: -1, team: 2 }));
  const crate = await add(page, '3D/Models/crate.nod', 2);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  const rows = page.locator('#scene li');
  await expect(rows).toHaveCount(2);
  const items = (await page.evaluate(() => window.sc2viewer.state())).items;
  const row = (id) => rows.nth(items.findIndex((i) => i.id === id));
  // The SC2 unit has the control: the test can see it.
  await expect(row(marine).locator('select.team')).toHaveCount(1);
  await expect(row(crate).locator('select.team')).toHaveCount(0);
  const ghost = items.find((i) => i.id === crate);
  expect(ghost.hd).toBeUndefined();
  expect(items.find((i) => i.id === marine).hd).toBe(true);
  expect(errors).toEqual([]);
});

test('the Ghost tab makes Ghost the gallery game; the scene, the camera and the selection stay', async ({ page }) => {
  const errors = await open(page);
  const marine = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, pick: 0.5, sequence: -1, team: 2 }));
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate((ids) => window.SC2App.setSelection(ids), [marine]);
  const before = await page.evaluate(() => window.sc2viewer.state());
  await page.locator('#game-tabs button[data-game="ghost"]').click();
  await expect.poll(() => page.evaluate(() => window.sc2viewer.games.current())).toBe('ghost');
  await expect(page.locator('#game-tabs button[data-game="ghost"]')).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('#pane-actors')).toHaveCount(1);
  await expect(page.locator('#pane-models')).toHaveCount(1);
  await expect(page.locator('#dataset')).toHaveValue('build');
  await expect(page.locator('#pane-actors li[data-id]').first()).toBeAttached({ timeout: 15_000 });
  // Negative: the other game's panes are gone; the scene, the camera and the selection did not change.
  await expect(page.locator('#pane-units')).toHaveCount(0);
  const after = await page.evaluate(() => window.sc2viewer.state());
  expect(after.items.map((i) => [i.id, i.game, i.x, i.y])).toEqual(before.items.map((i) => [i.id, i.game, i.x, i.y]));
  expect(after.camera).toEqual(before.camera);
  expect(await page.evaluate(() => window.SC2App.selectedIds())).toEqual([marine]);
  expect(errors).toEqual([]);
});

test('two games in one scene: selected together, moved, copied, pasted, back after a reload', async ({ page }) => {
  const errors = await open(page);
  const marine = await page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: -2, y: 0, pick: 0.5, sequence: -1, team: 2 }));
  const crate = await add(page, '3D/Models/crate.nod', 2);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate((ids) => window.SC2App.setSelection(ids), [marine, crate]);
  expect((await page.evaluate(() => window.SC2App.selectedIds())).sort()).toEqual([marine, crate].sort());
  // Moved: the instance list's x field of each, by the same step.
  for (const id of [marine, crate]) {
    const items = (await page.evaluate(() => window.sc2viewer.state())).items;
    const field = page.locator('#scene li').nth(items.findIndex((i) => i.id === id)).locator('input.x');
    await field.fill(String(items.find((i) => i.id === id).x + 1));
    await field.press('Enter');
  }
  const moved = (await page.evaluate(() => window.sc2viewer.state())).items;
  expect(moved.map((i) => [i.game, i.x])).toEqual([['sc2', -1], ['ghost', 3]]);
  // Copied and pasted off the view: the copies keep their game and place.
  // The x field keeps its own keys while it has the focus: leave it first.
  await page.evaluate(() => document.activeElement instanceof HTMLElement && document.activeElement.blur());
  const panel = await page.locator('#gallery').boundingBox();
  await page.mouse.move(panel.x + panel.width / 2, panel.y + panel.height / 2);
  await page.evaluate((ids) => window.SC2App.setSelection(ids), [marine, crate]);
  await page.locator('body').press('Control+c');
  expect(await page.evaluate(() => window.SC2App.copiedCount())).toBe(2);
  await page.locator('body').press('Control+v');
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  const pasted = (await page.evaluate(() => window.sc2viewer.state())).items;
  expect(pasted.map((i) => [i.game, i.path, i.x])).toEqual([...moved, ...moved].map((i) => [i.game, i.path, i.x]));
  // Saved: the stored scene names each item's game; back after a reload.
  const stored = await sceneOf(page);
  expect(stored.items.map((i) => i.game)).toEqual(['sc2', 'ghost', 'sc2', 'ghost']);
  await reloadScene(page);
  const back = (await page.evaluate(() => window.sc2viewer.state())).items;
  expect(back.map((i) => [i.game, i.path, i.x, i.loaded])).toEqual(pasted.map((i) => [i.game, i.path, i.x, true]));
  // Negative: nothing of one game came back as the other.
  expect(back.filter((i) => i.game === 'ghost').every((i) => i.path.toLowerCase().endsWith('.nod'))).toBe(true);
  expect(back.filter((i) => i.game === 'sc2').every((i) => i.path.toLowerCase().endsWith('.m3'))).toBe(true);
  expect(errors).toEqual([]);
});
