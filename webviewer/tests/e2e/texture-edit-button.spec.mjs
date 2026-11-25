import { join } from 'node:path';
import { test, expect, ownServer } from '../fixtures.mjs';
import { add, frameItem, open as openGhost } from '../ghost.mjs';
import { open, textureFrame } from '../page.mjs';
import { editsState, openTextures, sessionsOf, tilesOf } from '../edits.mjs';

// The Edit Texture button of the texture window's tiles (SPEC-PHOTOCRAFT 9.1,
// R-PC-20, R-PC-23, R-PC-28, R-PC-29, R-PC-13): on each tile that shows a
// variant, a pencil at the bottom left of its preview. A click opens the
// edit session in the editor window and picks nothing. The page's state and
// the server's sessions decide; how the button looks is an operator check.

const ASSET = 'assets\\textures\\mutalisk_diffuse.dds';

test('each tile that shows a variant has the button; a click opens the session in the editor window and picks nothing; no list row and no Upscale tile has one', async ({ page, request }) => {
  test.setTimeout(180_000);
  const errors = await open(page);
  const frame = await openTextures(page, 'Mutalisk', ASSET);
  const before = await frame.evaluate(() => window.hdtex.state());
  expect(before.edits.tools).toBe(true);
  // In game and Original show a variant: each has the button, enabled.
  for (const id of ['in-game', 'original']) expect(before.tiles.find((tile) => tile.id === id).edit, id).toMatchObject({ disabled: '' });
  await expect(frame.locator('#cards .skin-tile[data-tile="in-game"] .tile-thumb .tile-edit')).toHaveAttribute('title', 'Edit Texture');
  await expect(frame.locator('#cards .skin-tile[data-tile="original"] .tile-thumb .tile-edit')).toHaveCount(1);
  // Negative: the Upscale tile has none, and no list row has one.
  expect(before.tiles.find((tile) => tile.kind === 'upscale').edit).toBeNull();
  await expect(frame.locator('#cards .skin-tile.upscale .tile-edit')).toHaveCount(0);
  await expect(frame.locator('#list .row .tile-edit, #list .row button')).toHaveCount(0);
  // Negative: nothing is asked of the editor before a click.
  expect((await editsState(page)).editor).toMatchObject({ open: false, session: null, phase: 'closed' });
  await expect(page.locator('#editor-window')).toBeHidden();

  // A click on the button of Original: the session of the texture's original opens in the editor window.
  await frame.locator('#cards .skin-tile[data-tile="original"] .tile-edit').click();
  await expect(page.locator('#editor-window')).toBeVisible({ timeout: 60_000 });
  const session = (await sessionsOf(request, 'scoba')).find((one) => one.asset === ASSET && one.variant === 'original');
  expect(session, 'the server holds the session').toBeTruthy();
  const editor = (await editsState(page)).editor;
  expect(editor).toMatchObject({ open: true, session: session.session });
  expect(new URL(editor.frame, page.url()).searchParams.get('host')).toBe(`/api/sc2/textures/edit/${session.session}`);
  await expect(page.locator('#editor-window .window-title')).toHaveText(`edit · ${ASSET} · original`);
  // Negative: the click did not reach the tile: no pick, nothing more in the picture, no draft bar (R-PC-23).
  const after = await frame.evaluate(() => window.hdtex.state());
  expect(after.picks).toEqual(before.picks);
  expect(after.shown).toEqual(before.shown);
  expect(after.draft.shown).toBe(false);
  // The session shows on the buttons of the tiles of that variant: a grey dot, it is not edited.
  await expect.poll(async () => (await tilesOf(frame)).filter((tile) => tile.variant === 'original').map((tile) => tile.edit.dot), { timeout: 15_000 }).toEqual(['other', 'other']);
  // Negative: an unchanged session gives the row no EDIT badge, and opens no dialog.
  await expect(frame.locator('#list .badge.edit')).toHaveCount(0);
  expect((await editsState(page)).dialogs.transfer.open).toBe(false);
  // The window closes by its close button; nothing is unsaved, so it does not ask.
  await page.locator('#editor-window .window-close').click();
  await expect(page.locator('#editor-window')).toBeHidden();
  expect((await editsState(page)).closing).toBe(false);
  expect(errors).toEqual([]);
});

test('negative: a texture that cannot be upscaled has the button disabled, with the reason; a click opens nothing', async ({ page }) => {
  test.setTimeout(60_000);
  const REASON = 'it is a cube map of six faces';
  const errors = await open(page);
  await page.goto('/texture-viewer.html');
  await page.waitForFunction(() => Boolean(window.hdtex));
  // The server's states of this texture, with a reason why it has no role: the page's rule is what is tested.
  for (const route of ['**/api/sc2/textures?*', '**/api/sc2/textures/judge?*']) {
    await page.route(route, async (found) => {
      const reply = await found.fetch();
      const body = await reply.json();
      for (const texture of body.textures ?? []) Object.assign(texture, { judged: true, reason: REASON, asks: [] });
      await found.fulfill({ response: reply, json: body });
    });
  }
  await page.evaluate(async (asset) => {
    const canvas = Object.assign(document.createElement('canvas'), { width: 4, height: 4 });
    const texture = { texture: 'mutalisk_diffuse.dds', asset, format: 'DXT5', size: [4, 4], planes: [{ plane: 'color', image: canvas.toDataURL() }], facts: [] };
    window.editAsked = [];
    await window.hdtex.show({ user: 'probe', game: 'sc2', dataset: 'scoba', service: true, owner: null, textures: [texture], failed: [], changed() {}, edit: { open: (...asked) => window.editAsked.push(asked), manage() {} } });
  }, ASSET);
  await expect(page.locator('#cards .skin-tile[data-tile="original"] .tile-edit')).toHaveCount(1);
  const tiles = await page.evaluate(() => window.hdtex.state().tiles);
  for (const id of ['in-game', 'original']) expect(tiles.find((tile) => tile.id === id).edit, id).toEqual({ disabled: REASON, dot: null });
  const button = page.locator('#cards .skin-tile[data-tile="original"] .tile-edit');
  await expect(button).toHaveAttribute('aria-disabled', 'true');
  await expect(button).toHaveAttribute('title', `Edit Texture: ${REASON}`);
  // The test runner waits for an enabled target; a person's click lands all the same, so it is forced.
  await button.click({ force: true });
  expect(await page.evaluate(() => window.editAsked)).toEqual([]);
  // Negative: the click picked nothing either.
  expect(await page.evaluate(() => window.hdtex.state())).toMatchObject({ picks: {}, shown: ['original'] });
  // Negative: handed no edit tools (a game without the service, or no install), the same tiles have no button.
  await page.evaluate(async (asset) => {
    const canvas = Object.assign(document.createElement('canvas'), { width: 4, height: 4 });
    const texture = { texture: 'mutalisk_diffuse.dds', asset, format: 'DXT5', size: [4, 4], planes: [{ plane: 'color', image: canvas.toDataURL() }], facts: [] };
    await window.hdtex.show({ user: 'probe', game: 'sc2', dataset: 'scoba', service: true, owner: null, textures: [texture], failed: [], changed() {} });
  }, ASSET);
  await expect(page.locator('#cards .skin-tile[data-tile="original"]')).toHaveCount(1);
  await expect(page.locator('.tile-edit')).toHaveCount(0);
  expect((await page.evaluate(() => window.hdtex.state())).edits).toMatchObject({ tools: false, manage: false });
  expect(errors).toEqual([]);
});

test('negative: a game without a texture service gets no edit control in its texture window', async ({ page }) => {
  test.setTimeout(60_000);
  const errors = await openGhost(page);
  const id = await add(page, '3D/Models/crate.nod');
  await frameItem(page, id);
  const at = await page.evaluate((i) => window.sc2viewer.itemPixel(i), id);
  await page.mouse.dblclick(at[0], at[1]);
  await expect(page.locator('#texture-window')).toBeVisible();
  await expect.poll(() => page.evaluate(() => window.sc2viewer.textureWindow().originals), { timeout: 20_000 }).toBe('done');
  const frame = textureFrame(page);
  expect((await frame.evaluate(() => window.hdtex.state())).edits).toMatchObject({ tools: false, manage: false, sessions: [] });
  await expect(frame.locator('.tile-edit')).toHaveCount(0);
  await expect(frame.locator('#manage-edits')).toBeHidden();
  // Negative: nothing is read of edit sessions for it: two polls pass and the page holds none.
  await page.waitForTimeout(4500);
  expect((await editsState(page)).sessions).toEqual({});
  expect(errors).toEqual([]);
});

test.describe('without a PhotoCraft install', () => {
  test.describe.configure({ mode: 'serial', timeout: 240_000 });
  let server;
  test.beforeAll(async ({ worker }, testInfo) => {
    server = await ownServer(worker, testInfo.parallelIndex, 'edit-button-no-install', { PHOTOCRAFT_HOME: join(worker.root, 'no-photocraft-home') });
  });
  test.afterAll(async () => {
    if (server) await server.stop();
  });

  test('negative: no tile has the button, and the page asks for no edit session', async ({ page }) => {
    const asked = [];
    page.on('request', (sent) => {
      if (sent.url().includes('/textures/edit')) asked.push(sent.url());
    });
    const errors = await open(page, { path: `${server.url}/` });
    const frame = await openTextures(page, 'Mutalisk', ASSET);
    const now = await frame.evaluate(() => window.hdtex.state());
    expect(now.edits).toMatchObject({ tools: false, manage: false });
    for (const tile of now.tiles) expect(tile.edit, tile.id).toBeNull();
    await expect(frame.locator('.tile-edit')).toHaveCount(0);
    await page.waitForTimeout(4500);
    expect(asked).toEqual([]);
    expect(errors).toEqual([]);
  });
});
