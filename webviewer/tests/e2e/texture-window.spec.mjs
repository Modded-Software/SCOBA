import { test, expect } from '../fixtures.mjs';
import { chooseRow, open, state, textureFrame } from '../page.mjs';

// The texture window (src/page/core/texturewindow.ts, the page
// public/texture-viewer.html with src/page/texview): hidden until a
// double-click on a gallery row, an instance row, or an instance in the
// view. It lists every texture that thing's model names, decoded in the
// page, each with its state from the texture service (SPEC-VIEWER 17.3).
// The window compares; it changes nothing (R-VIEW-101). The tests' store is
// fresh: no texture has a variant here. Variants: texture-variants.spec.mjs.

const win = (page) => page.evaluate(() => window.sc2viewer.textureWindow());

/** The texture page's own state, once the window handed it the textures of `user` and the page read their states. */
async function inside(page, user) {
  await expect
    .poll(async () => {
      const frame = textureFrame(page);
      if (!frame) return 'no frame';
      return frame.evaluate(() => (window.hdtex ? window.hdtex.state().user : 'loading')).catch((error) => error.message);
    }, { timeout: 30_000 })
    .toBe(user);
  // The window is done when the page holds the textures and their states.
  await expect.poll(async () => (await win(page)).originals, { timeout: 30_000 }).toBe('done');
  // Then the page has the pipeline judge those nobody asked for by name: what they may ask for shows after it (30 s: it reads each original once).
  await expect.poll(() => textureFrame(page).evaluate(() => window.hdtex.state().judging), { timeout: 30_000 }).toBe(false);
  return textureFrame(page).evaluate(() => ({ ...window.hdtex.state(), entries: window.hdtex.entries(), problems: window.hdtex.problems(), textures: window.hdtex.textures(), message: window.hdtex.message() }));
}

async function unitRow(page, name) {
  await page.fill('#search-units', name);
  const row = page.locator('#units li', { has: page.locator('.name', { hasText: new RegExp(`^${name}$`, 'i') }) }).first();
  await expect(row).toBeVisible();
  return row;
}

test('the window is hidden at first; a double-click on a unit of the gallery opens it with every texture of its model, shown as the skin editor\'s tiles: In game first; "used by" scrolls at a fixed height; no Use, no checkbox; a click on In game picks nothing', async ({ page }) => {
  test.setTimeout(90_000);
  const errors = await open(page);
  await expect(page.locator('#texture-window')).toBeHidden();
  expect(await win(page)).toMatchObject({ open: false, user: null });
  const row = await unitRow(page, 'Marine');
  // Negative: one click previews the unit and opens nothing.
  await row.click();
  await expect(page.locator('#preview-units .name')).toHaveText('Marine');
  await expect(page.locator('#texture-window')).toBeHidden();

  await row.dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  await expect(page.locator('#texture-window .window-title')).toContainText('Marine');
  expect(await win(page)).toMatchObject({ open: true, user: 'Marine' });
  const shown = await inside(page, 'Marine');
  console.log(`Marine: ${shown.entries.map((e) => `${e.id} ${e.category}`).join(', ')}; problems ${shown.problems}; message ${shown.message}`);
  expect(shown.embed).toBe(true);
  expect(shown.message).toBe('');
  const names = shown.entries.map((entry) => entry.texture);
  expect(names).toContain('marine_remastered_diff.dds');
  expect(names).toContain('marine_remastered_norm.dds');
  // Every entry is named for the service, and the service knows each one.
  for (const entry of shown.entries) expect(entry.asset, entry.id).toBe(`assets\\textures\\${entry.texture.toLowerCase()}`);
  expect(new Set(shown.textures.map((t) => t.asset))).toEqual(new Set(shown.entries.map((e) => e.asset)));
  for (const entry of shown.entries) expect(entry.category, entry.id).toBe(shown.textures.find((t) => t.asset === entry.asset).kind);
  expect(shown.problems).toEqual([]);
  await expect(textureFrame(page).locator('#list .row')).toHaveCount(shown.entries.length);
  // Negative: the store is fresh, so no row has an HD or a package badge, and the view shows the original alone.
  expect(shown.entries.every((entry) => entry.variants.length === 0)).toBe(true);
  await expect(textureFrame(page).locator('#list .badge.hd, #list .badge.packaged')).toHaveCount(0);
  await expect(textureFrame(page).locator('#view .divider')).toHaveCount(0);
  // The window had every texture judged; the card of one that can be upscaled has the Upscale button, one.
  expect(shown.textures.filter((t) => !t.judged).map((t) => t.asset)).toEqual([]);
  await expect(textureFrame(page).locator('#cards .unread')).toHaveCount(0);
  const current = shown.textures.find((t) => t.asset === shown.current.asset);
  expect(current.reason).toBe('');
  await expect(textureFrame(page).locator('#cards button.upscale')).toHaveCount(1);
  // Negative: compare only: no pick, no default, no step button of its own.
  await expect(textureFrame(page).locator('#cards select, #default, #cards .steps button')).toHaveCount(0);
  // The double-click adds nothing to the scene (the "add to scene" button and a drag do).
  expect((await state(page)).items).toEqual([]);

  // The window shows the skin editor's tiles (R-VIEW-131 to 134).
  const frame = textureFrame(page);
  // The texture with the most users: its "used by" is the longest.
  const most = [...shown.textures].sort((a, b) => b.users.length - a.users.length)[0];
  console.log(`most users: ${most.asset} ${most.users.length}: ${most.users.join(', ')}`);
  expect(most.users.length).toBeGreaterThan(0);
  await chooseRow(frame, most.asset);
  const now = await frame.evaluate(() => window.hdtex.state());
  console.log(`tiles ${JSON.stringify(now.tiles)}`);
  // In game first: the store is fresh, nothing is baked, so it is the original; it and Original are shown, outlined (R-VIEW-131, 132).
  expect(now.tiles[0]).toMatchObject({ id: 'in-game', kind: 'in-game', variant: 'original', highlighted: true, note: '' });
  expect(now.tiles[1]).toMatchObject({ id: 'original', kind: 'original', highlighted: true });
  expect(now).toMatchObject({ shown: ['original'], picks: {}, draft: { shown: false }, owner: 'unit:Marine' });
  await expect(frame.locator('#cards .skin-tile.highlighted')).toHaveCount(2);
  await expect(frame.locator('#cards .skin-tile[data-tile="in-game"]')).toContainText('not baked');
  // "used by": one user per line; a long list scrolls inside its box (R-VIEW-134).
  const box = await frame.locator('#cards dd.used-by').evaluate((node) => ({ lines: node.children.length, client: node.clientHeight, scroll: node.scrollHeight }));
  console.log(`used by ${JSON.stringify(box)}`);
  expect(box.lines).toBe(most.users.length);
  if (most.users.length > 4) expect(box.scroll).toBeGreaterThan(box.client);
  // Negative: no Use button, no show checkbox, no card, no "what it shows now".
  await expect(frame.locator('button.use-variant, input.show-variant, .card')).toHaveCount(0);
  await expect(frame.locator('#cards')).not.toContainText('what it shows now');
  // Negative: a click on In game (here the original) is no pick: there is nothing to save (R-VIEW-133).
  await frame.locator('#cards .skin-tile[data-tile="in-game"]').click();
  expect(await frame.evaluate(() => window.hdtex.state())).toMatchObject({ picks: {}, draft: { shown: false } });
  await expect(frame.locator('#list .badge.picked')).toHaveCount(0);
  expect(errors).toEqual([]);
});

test('negative: the texture page opened alone holds no texture', async ({ page }) => {
  const errors = await open(page);
  await page.goto('/texture-viewer.html');
  await page.waitForFunction(() => Boolean(window.hdtex));
  // Opened alone, nothing was handed to it.
  expect(await page.evaluate(() => window.hdtex.state())).toMatchObject({ user: '', visible: 0, total: 0, embed: false });
  expect(errors).toEqual([]);
});

test('negative: handed a texture with no owner, the page shows its tiles but keeps no pick and offers no Save to Skin', async ({ page }) => {
  const errors = await open(page);
  await page.goto('/texture-viewer.html');
  await page.waitForFunction(() => Boolean(window.hdtex));
  await page.evaluate(async () => {
    const canvas = Object.assign(document.createElement('canvas'), { width: 4, height: 4 });
    const image = canvas.toDataURL();
    const texture = { texture: 'marine_remastered_diff.dds', asset: 'assets\\textures\\marine_remastered_diff.dds', format: 'DXT5', size: [4, 4], planes: [{ plane: 'color', image }], facts: [] };
    await window.hdtex.show({ user: 'probe', game: 'sc2', dataset: 'scoba', service: true, owner: null, textures: [texture], failed: [], changed() {} });
  });
  await expect(page.locator('#cards .skin-tile[data-tile="in-game"]')).toHaveCount(1);
  await page.locator('#cards .skin-tile[data-tile="original"]').click();
  expect(await page.evaluate(() => window.hdtex.state())).toMatchObject({ owner: null, picks: {}, draft: { shown: false }, shown: ['original'] });
  await expect(page.locator('#draft')).toBeHidden();
  expect(errors).toEqual([]);
});
