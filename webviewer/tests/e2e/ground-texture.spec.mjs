import { test, expect } from '../fixtures.mjs';
import { api } from '../api.mjs';
import { open, state } from '../page.mjs';

// The ground texture (SPEC-VIEWER 17.7): the SC2 category "terrain" lists one
// record per terrain texture entry, with its colour file and normal map.
// Added, a record becomes the ground texture (not an instance); the ground
// button picks one or none, each row with a picture. The setting keeps it
// over a reload. The ground shows the chosen variant, else the terrain bake,
// else the original. How the textured ground looks is an operator check
// (SPEC-VIEWER 14); these tests read the texture the ground draws.

const ground = async (page) => {
  const now = await state(page);
  return { ground: now.ground, size: now.groundTexture, items: now.items.length };
};

/** The first ground texture record of scoba, and the size of its colour file. */
async function firstRecord(request) {
  const listed = await (await request.get(api.records('terrain', { limit: '1' }))).json();
  expect(listed.total).toBeGreaterThan(100);
  const record = listed.items[0];
  const full = await (await request.get(api.record('terrain', record.id))).json();
  const states = await (await request.get(`/api/sc2/textures?${new URLSearchParams({ dataset: 'scoba', asset: full.file })}`)).json();
  return { record: full, state: states.textures[0] };
}

test('the terrain category lists ground textures with their colour file and normal map; it has no gallery tab', async ({ page, request }) => {
  test.setTimeout(60_000);
  const { record, state: colour } = await firstRecord(request);
  console.log(`first ${JSON.stringify(record)}`);
  expect(record).toMatchObject({ placeable: false, notPlaceableAs: 'ground texture', dataset: 'scoba' });
  expect(record.file).toMatch(/^assets\\.*\.dds$/);
  expect(colour.kind).toBe('terrain');
  // Negative: no such entry.
  expect((await request.get(api.record('terrain', 'NoSuchEntry'))).status()).toBe(404);
  const errors = await open(page);
  // The ground button is the one place for ground textures (operator 2026-11-25).
  await expect(page.locator('#tab-units')).toBeVisible();
  await expect(page.locator('#ground-button')).toBeVisible();
  // Negative: no terrain tab and no terrain pane.
  await expect(page.locator('#tab-terrain')).toHaveCount(0);
  await expect(page.locator('#terrain')).toHaveCount(0);
  expect(await ground(page)).toEqual({ ground: null, size: null, items: 0 });
  expect(errors).toEqual([]);
});

test('the ground button picks a ground texture and (none); a reload keeps it; nothing is added to the scene', async ({ page, request }) => {
  test.setTimeout(90_000);
  const { record } = await firstRecord(request);
  const errors = await open(page);
  await expect(page.locator('#ground-button')).toBeVisible();
  // Negative: at first the ground draws no texture.
  expect(await ground(page)).toEqual({ ground: null, size: null, items: 0 });
  await page.click('#ground-button');
  await expect(page.locator('#ground-dialog')).toBeVisible();
  await page.fill('#ground-dialog input[type=search]', record.id);
  await page.locator(`#ground-dialog .picker-list li[data-id="${record.id}"]`).click();
  await expect(page.locator('#ground-dialog')).toBeHidden();
  await expect.poll(async () => (await ground(page)).size).not.toBeNull();
  const chosen = await ground(page);
  expect(chosen.ground).toMatchObject({ game: 'sc2', dataset: 'scoba', category: 'terrain', id: record.id, texture: record.file });
  expect(chosen.items).toBe(0);
  await expect(page.locator('#ground-button')).toHaveClass(/\bon\b/);
  console.log(`${record.id}: size ${chosen.size}`);
  expect(Math.min(...chosen.size)).toBeGreaterThan(0);

  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready))).toBe(true);
  await expect.poll(async () => (await ground(page)).size).toEqual(chosen.size);
  expect((await ground(page)).ground).toEqual(chosen.ground);

  await page.click('#ground-button');
  await page.locator('#ground-dialog .picker-list li[data-id=""]').click();
  await expect.poll(async () => (await ground(page)).ground).toBeNull();
  expect((await ground(page)).size).toBeNull();
  await expect(page.locator('#ground-button')).not.toHaveClass(/\bon\b/);
  expect(errors).toEqual([]);
});
