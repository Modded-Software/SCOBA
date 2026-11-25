import { existsSync } from 'node:fs';
import { test, expect } from '../fixtures.mjs';
import { open } from '../page.mjs';
import { changeScratch, cmd, editsState, editUrl, openSession, openTextures, painted, sessionOf, tilesOf } from '../edits.mjs';
import { stateOf } from '../skins.mjs';

// Detecting an edit, the transfer dialog and the session list
// (SPEC-PHOTOCRAFT 9.3 to 9.5; R-PC-40 to R-PC-44, R-PC-50 to R-PC-58, R-PC-33,
// R-PC-37). The scratch is changed by the commands of PhotoCraft's own
// renderer, as another program would (R-PC-74). The page's state, the
// server's sessions and the texture's variants decide.

const ASSET = 'assets\\textures\\sentry_diffuse.dds';
const EDITED = /^edit[0-9a-f]{12}@\d+$/;

const dialogs = async (page) => (await editsState(page)).dialogs;
const row = (page, session) => page.locator(`#edits-dialog .edit-session[data-session="${session}"]`);

test('an edited session opens the transfer dialog once; Keep Editing changes nothing and it does not open again; the list transfers it to a new variant; Discard Edit asks again', async ({ page, request }) => {
  test.setTimeout(360_000);
  const errors = await open(page);
  let frame = await openTextures(page, 'Sentry', ASSET);
  const session = await openSession(request, 'scoba', ASSET);
  const plane = session.planes[0];
  const made = async () => (await stateOf(request, 'scoba', ASSET)).variants.filter((variant) => EDITED.test(variant.id)).map((variant) => variant.id);
  const variantsBefore = await made();

  // The window shows the session within a poll: Manage Edits… is there, the tiles of the variant have a grey dot.
  await expect.poll(() => frame.evaluate(() => window.hdtex.state().edits.manage), { timeout: 15_000 }).toBe(true);
  await expect.poll(async () => (await tilesOf(frame)).find((tile) => tile.id === 'original').edit.dot, { timeout: 15_000 }).toBe('other');
  // Negative: an unchanged session opens no dialog and gives no badge.
  expect((await dialogs(page)).transfer.open).toBe(false);
  await expect(frame.locator('#list .badge.edit')).toHaveCount(0);

  // Another program changes the scratch: a layer in the first plane's group.
  await changeScratch(session, painted(session, plane));
  await expect.poll(async () => (await dialogs(page)).transfer.open, { timeout: 60_000 }).toBe(true);
  await expect(page.locator('#edit-transfer-dialog')).toBeVisible();
  await expect(page.locator('#edit-transfer-dialog .dialog-head span')).toHaveText('Transfer Edit to Texture');
  // The changed plane as two pictures, loaded; the others by name.
  await expect.poll(async () => (await dialogs(page)).transfer.pictures.every((picture) => !picture.endsWith(':none')), { timeout: 20_000 }).toBe(true);
  const offered = (await dialogs(page)).transfer;
  console.log(`offer: ${JSON.stringify(offered)}`);
  expect(offered).toMatchObject({ session: session.session, changed: [plane], error: '', buttons: ['Discard Edit', 'Keep Editing', 'Transfer Edit'] });
  expect(offered.pictures).toEqual([`base/${plane}:${session.size[0]}`, `rendered/${plane}:${session.size[0]}`]);
  const others = session.planes.filter((one) => one !== plane);
  if (others.length) expect(offered.lines).toContain(`not changed: ${others.join(', ')}`);
  expect(offered.lines.at(-1)).toBe(`A new variant of ${ASSET} will be made from your edit. The original stays as it is. No skin and no bake changes.`);
  await expect(page.locator('#edit-transfer-dialog .edit-what')).toHaveText(`${ASSET} · original · ${session.size.join('x')}`);
  // Negative: the dialog offers nothing about skins (R-PC-51).
  await expect(page.locator('#edit-transfer-dialog select, #edit-transfer-dialog input')).toHaveCount(0);
  await expect(page.locator('#edit-transfer-dialog')).not.toContainText(/skin\b(?! and no bake)/i);
  // The row of the texture has the badge EDIT, and the tiles of the variant an amber dot (R-PC-37).
  await expect.poll(() => frame.locator('#list .badge.edit').count(), { timeout: 15_000 }).toBeGreaterThan(0);
  expect((await tilesOf(frame)).find((tile) => tile.id === 'original').edit.dot).toBe('edited');

  // Keep Editing: nothing changes, and the same planes are not offered again (two polls and more pass).
  await page.locator('#edit-transfer-keep').click();
  await expect(page.locator('#edit-transfer-dialog')).toBeHidden();
  await page.waitForTimeout(5000);
  expect((await dialogs(page)).transfer.open).toBe(false);
  expect(await sessionOf(request, 'scoba', session.session)).toMatchObject({ state: 'edited', changed: [plane], transfers: [] });
  expect(await made()).toEqual(variantsBefore);
  expect(Object.keys((await editsState(page)).offered)).toContain(session.session);
  // Negative: a reload does not offer them again: what was offered is in the page's stored state.
  await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 20_000 }).toBe(true);
  frame = await openTextures(page, 'Sentry', ASSET);
  await expect.poll(() => frame.locator('#list .badge.edit').count(), { timeout: 15_000 }).toBeGreaterThan(0);
  await page.waitForTimeout(5000);
  expect((await dialogs(page)).transfer.open).toBe(false);

  // Manage Edits… lists the session with its state, what changed and its scratch on disk (R-PC-33).
  await frame.locator('#manage-edits').click();
  await expect(page.locator('#edits-dialog')).toBeVisible();
  const listed = (await dialogs(page)).list.rows.find((one) => one.session === session.session);
  console.log(`list row: ${JSON.stringify(listed)}`);
  expect(listed).toMatchObject({ texture: ASSET, variant: 'original', state: 'edited', buttons: ['Resume Edit', 'Transfer Edit…', 'Discard Edit'] });
  expect(listed.lines).toContain(`changed: ${plane}`);
  expect(listed.lines).toContain(session.scratch);

  // Transfer Edit… from the list, then Transfer Edit: the new variant shows in the tiles (R-PC-56).
  await row(page, session.session).locator('button.edit-transfer').click();
  await expect(page.locator('#edit-transfer-dialog')).toBeVisible();
  await page.locator('#edit-transfer-yes').click();
  await expect(page.locator('#edit-transfer-dialog')).toBeHidden({ timeout: 60_000 });
  await expect.poll(async () => (await sessionOf(request, 'scoba', session.session)).state, { timeout: 60_000 }).toBe('transferred');
  const variants = (await made()).filter((id) => !variantsBefore.includes(id));
  expect(variants).toHaveLength(1);
  await expect.poll(async () => (await tilesOf(frame)).map((tile) => tile.id), { timeout: 30_000 }).toContain(variants[0]);
  const tile = (await tilesOf(frame)).find((one) => one.id === variants[0]);
  // A user-made variant: its numbers show with no band, and no info mark (R-PC-80).
  expect(tile).toMatchObject({ kind: 'variant', band: 'none', info: '' });
  const numbers = frame.locator(`#cards .skin-tile[data-variant="${variants[0]}"] .tile-numbers .number`);
  expect(await numbers.count()).toBeGreaterThan(0);
  expect(await numbers.evaluateAll((nodes) => nodes.map((node) => node.dataset.band))).toEqual(Array(await numbers.count()).fill('none'));
  await expect(frame.locator(`#cards .skin-tile[data-variant="${variants[0]}"] .tile-info`)).toHaveCount(0);
  // The session is transferred: its mark is grey again, the badge is gone, and it is not offered.
  await expect.poll(async () => (await tilesOf(frame)).find((one) => one.id === 'original').edit.dot, { timeout: 15_000 }).toBe('other');
  await expect(frame.locator('#list .badge.edit')).toHaveCount(0);
  expect((await dialogs(page)).transfer.open).toBe(false);

  // Discard Edit asks again, naming the texture. Cancel keeps the session and its folder.
  await frame.locator('#manage-edits').click();
  await expect(row(page, session.session)).toBeVisible();
  expect((await dialogs(page)).list.rows.find((one) => one.session === session.session)).toMatchObject({ state: 'transferred', buttons: ['Resume Edit', 'Discard Edit'] });
  await row(page, session.session).locator('button.edit-discard').click();
  await expect(page.locator('#edit-discard-dialog')).toBeVisible();
  expect((await dialogs(page)).discard.text).toContain(ASSET);
  await page.locator('#edit-discard-no').click();
  await expect(page.locator('#edit-discard-dialog')).toBeHidden();
  expect(existsSync(session.scratch)).toBe(true);
  expect((await request.get(editUrl('scoba', `/${session.session}`))).status()).toBe(200);
  // Discard Edit, confirmed: the session is gone from the list and from disk; the variant stays (R-PC-32).
  await row(page, session.session).locator('button.edit-discard').click();
  await page.locator('#edit-discard-yes').click();
  await expect(row(page, session.session)).toHaveCount(0, { timeout: 30_000 });
  expect(existsSync(session.scratch)).toBe(false);
  expect((await request.get(editUrl('scoba', `/${session.session}`))).status()).toBe(404);
  expect(await made()).toContain(variants[0]);
  expect(Object.keys((await editsState(page)).offered)).not.toContain(session.session);
  expect(errors).toEqual([]);
});

test('negative: a scratch that cannot give every plane opens no transfer dialog and its transfer is refused; the page says the reason, the list has it with no Transfer Edit…; Resume Edit opens the editor on it', async ({ page, request }) => {
  test.setTimeout(360_000);
  const OTHER = 'assets\\textures\\phoenixex2_diffuse.dds';
  const errors = await open(page);
  const frame = await openTextures(page, 'Phoenix', OTHER);
  const session = await openSession(request, 'scoba', OTHER);
  const variantsBefore = (await stateOf(request, 'scoba', OTHER)).variants.map((variant) => variant.id);
  await expect.poll(() => frame.evaluate(() => window.hdtex.state().edits.manage), { timeout: 15_000 }).toBe(true);

  // Another program saves the scratch at another size: no plane can be read from it (R-PC-75).
  await changeScratch(session, cmd('image.imageSize', { width: 32, height: 32 }));
  const reason = `the scratch is 32x32; the texture is ${session.size.join('x')}`;
  await expect.poll(async () => (await editsState(page)).told[session.session], { timeout: 60_000 }).toBe(reason);
  // The page said so when it found it, as a failure.
  await expect(page.locator('#status')).toHaveText(`${OTHER} (original): the edit cannot be transferred: ${reason}`);
  await expect(page.locator('#status')).toHaveClass(/failure/);
  expect(await sessionOf(request, 'scoba', session.session)).toMatchObject({ state: 'edited', reason, changed: [] });
  // Negative: no transfer is offered: more than two polls pass.
  await page.waitForTimeout(5000);
  expect((await dialogs(page)).transfer.open).toBe(false);
  expect(Object.keys((await editsState(page)).offered)).not.toContain(session.session);
  // Negative: the transfer route refuses it with the reason, and no variant is made (R-PC-53).
  const refused = await request.post(editUrl('scoba', `/${session.session}/transfer`), { data: {} });
  expect(refused.status(), await refused.text()).toBe(400);
  expect((await refused.json()).error).toContain(reason);
  expect((await stateOf(request, 'scoba', OTHER)).variants.map((variant) => variant.id)).toEqual(variantsBefore);

  // The list has the reason, and no Transfer Edit… for it.
  await frame.locator('#manage-edits').click();
  await expect(row(page, session.session)).toBeVisible();
  const listed = (await dialogs(page)).list.rows.find((one) => one.session === session.session);
  console.log(`list row: ${JSON.stringify(listed)}`);
  expect(listed).toMatchObject({ state: 'edited', buttons: ['Resume Edit', 'Discard Edit'] });
  expect(listed.lines).toContain(reason);

  // Resume Edit closes the list and opens the editor window on the session.
  await row(page, session.session).locator('button.edit-resume').click();
  await expect(page.locator('#edits-dialog')).toBeHidden();
  await expect(page.locator('#editor-window')).toBeVisible({ timeout: 60_000 });
  await expect.poll(async () => (await editsState(page)).editor.phase, { timeout: 150_000 }).toBe('opened');
  expect((await editsState(page)).editor).toMatchObject({ open: true, session: session.session, unsaved: false });
  await page.locator('#editor-window .window-close').click();
  await expect(page.locator('#editor-window')).toBeHidden();
  expect((await request.post(editUrl('scoba', `/${session.session}/discard`))).status()).toBe(200);
  expect(errors).toEqual([]);
});
