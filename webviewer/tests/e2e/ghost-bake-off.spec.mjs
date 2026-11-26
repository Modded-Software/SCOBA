// StarCraft: Ghost bakes nothing yet (R-HD-154, R-VIEW-151): the head of
// its states names the reason; the menu shows Bake Skin and Unbake Skin
// disabled with that reason as the title; the bake routes refuse with it and
// write no bake. SC2 is not changed by it. Engine and server state decide.
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '../fixtures.mjs';
import { add, CRATE, CRATE_OWNER, CRATE_TEXTURE, DATASET, frameItem, NO_BAKE, open, textureBody, texturePost } from '../ghost.mjs';

const idle = (page) => page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 15_000 });
const menuSkins = async (page) => (await page.evaluate(() => window.scobaeditor.state())).pick.menu.skins;

/** Open the instance's menu by a right click on one of its pixels. */
async function menu(page, id) {
  const at = await page.evaluate((i) => window.scobaeditor.itemPixel(i), id);
  expect(at, `a pixel of instance ${id} in the view`).toBeTruthy();
  await page.mouse.click(at[0], at[1], { button: 'right' });
  await expect(page.locator('#anim-menu')).toBeVisible();
}

test('the head names the reason; bake and unbake are refused with it and write no bake', async ({ request, worker }) => {
  const body = await textureBody(request, CRATE_TEXTURE);
  expect(body.bake).toBe(NO_BAKE);
  const bakes = join(worker.store, 'ghost', 'datasets', DATASET, 'bakes.json');
  for (const [route, data] of [
    ['bake', { owner: CRATE_OWNER, skin: 'New Skin 1' }],
    ['unbake', { owner: CRATE_OWNER }],
    ['bake', { asset: CRATE_TEXTURE, variant: 'fast@512' }],
    ['unbake', { asset: CRATE_TEXTURE }],
  ]) {
    const answer = await texturePost(request, route, data);
    expect(answer.status(), `${route} ${JSON.stringify(data)}`).toBe(400);
    expect((await answer.json()).error).toBe(`ghost: ${NO_BAKE}`);
  }
  expect(existsSync(bakes)).toBe(false);
  // Negative: SC2's head names no reason.
  const sc2 = await (await request.get(`/api/sc2/textures?${new URLSearchParams({ dataset: 'stock', asset: 'assets\\textures\\marine_diffuse_blood.dds' })}`)).json();
  expect(sc2.bake).toBe('');
});

test('the menu of a Ghost instance shows Bake Skin disabled with the reason; on Original Unbake Skin too; an SC2 instance is not changed by it', async ({ page }) => {
  const errors = await open(page);
  const crate = await add(page, CRATE);
  await idle(page);
  await frameItem(page, crate);
  await menu(page, crate);
  expect(await menuSkins(page)).toMatchObject({ value: 'original', bake: 'Unbake Skin', bakeDisabled: true, bakeTitle: NO_BAKE });
  await expect(page.locator('#anim-menu button.skin-bake')).toBeDisabled();
  await expect(page.locator('#anim-menu button.skin-bake')).toHaveAttribute('title', NO_BAKE);
  await page.keyboard.press('Escape');

  // Negative: an SC2 instance keeps its own rule (nothing is baked), not Ghost's reason.
  await page.locator('#game-tabs button[data-game="sc2"]').click();
  const marine = await page.evaluate(() => window.scobaeditor.addUnit('Marine', { x: 0, y: 0, pick: 0.5, sequence: -1 }));
  await idle(page);
  await page.evaluate(() => window.scobaeditor.remove(window.scobaeditor.state().items.find((i) => i.game === 'ghost').id));
  await idle(page);
  await page.evaluate(() => window.scobaeditor.view({ yaw: -Math.PI / 2, pitch: 0.5, distance: 6, target: [0, 0, 0.5] }));
  await menu(page, marine);
  expect(await menuSkins(page)).toMatchObject({ bake: 'Unbake Skin', bakeDisabled: true, bakeTitle: 'nothing is baked' });
  expect(errors).toEqual([]);
});
