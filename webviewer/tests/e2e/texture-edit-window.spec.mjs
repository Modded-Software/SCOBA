import { test, expect, allowErrors } from '../fixtures.mjs';
import { open } from '../page.mjs';
import { baseOf, changeScratch, checkedSession, cmd, editorFrame, editsState, editUrl, layersOf, openSession, openTextures, painted, sessionOf, sessionsOf } from '../edits.mjs';

// The editor window (SPEC-PHOTOCRAFT 9.2, 6): PhotoCraft in a frame on the
// scratch of an edit session, through the session's own routes. The bridge's
// messages, the page's state and the scratch on disk decide. A save is made
// by the editor's own key. What the editor draws is an operator check
// (O-PC-1 to O-PC-6); a screenshot proves nothing here.

/** What a key of the viewer page would change: the camera, the grid, the items. */
const viewer = (page) =>
  page.evaluate(() => {
    const { camera, grid, items } = window.scobaeditor.state();
    return JSON.stringify({ camera, grid, items: items.length });
  });

const editor = async (page) => (await editsState(page)).editor;

/** Wait until the editor opened the scratch. */
async function opened(page) {
  await expect.poll(async () => (await editor(page)).phase === 'failed' ? (await editor(page)).reason : (await editor(page)).phase, { timeout: 150_000 }).toBe('opened');
}

/** An edit by the editor's own keys: a new layer. The frame has the keyboard. */
async function newLayer(page) {
  await editorFrame(page).locator('#photocraft_canvas').focus();
  await page.keyboard.press('Control+Shift+N');
  await page.keyboard.press('Enter');
  await expect.poll(async () => (await editor(page)).unsaved, { timeout: 20_000 }).toBe(true);
}

const saves = async (page) => (await editor(page)).messages.filter((kind) => kind === 'saved').length;

test('the editor opens the scratch of the session; Escape stays in the editor; a save by its own key writes the scratch on disk; a refused save is not confirmed and closing then asks', async ({ page, request }) => {
  test.setTimeout(360_000);
  const ASSET = 'assets\\textures\\immortal_diffuse.dds';
  allowErrors(/http 404 PUT .*\/textures\/edit\/[0-9a-f]{16}\/scratch/, /console\.error: .*404/);
  const downloads = [];
  page.on('download', (download) => downloads.push(download.suggestedFilename()));
  const asked = [];
  page.on('request', (sent) => asked.push(sent.url()));
  const errors = await open(page);
  const frame = await openTextures(page, 'Immortal', ASSET);
  const before = await viewer(page);

  await frame.locator('#cards .skin-tile[data-tile="original"] .tile-edit').click();
  await expect(page.locator('#editor-window')).toBeVisible({ timeout: 60_000 });
  // Until the editor opened the scratch the window says so.
  expect(['loading', 'opened']).toContain((await editor(page)).phase);
  await opened(page);
  const session = (await sessionsOf(request, 'scoba')).find((one) => one.asset === ASSET && one.variant === 'original');
  const start = await editor(page);
  console.log(`editor: messages ${JSON.stringify(start.messages)}; frame ${start.frame}`);
  expect(start).toMatchObject({ open: true, session: session.session, reason: '', unsaved: false });
  // The bridge said it started, and opened the scratch: no file chooser was needed (R-PC-22).
  expect(start.messages).toContain('ready');
  expect(start.messages.indexOf('opened')).toBeGreaterThan(start.messages.indexOf('ready'));
  await expect(page.locator('#editor-note')).toBeHidden();
  const canvas = await editorFrame(page).locator('#photocraft_canvas').boundingBox();
  expect(canvas.width).toBeGreaterThan(300);
  expect(canvas.height).toBeGreaterThan(200);
  // Negative (R-PC-12): the editor asked nothing past the viewer's address.
  const origin = new URL(page.url()).origin;
  expect(asked.filter((url) => !url.startsWith(origin) && !url.startsWith('data:') && !url.startsWith('blob:'))).toEqual([]);

  // Negative: Escape in the frame belongs to the editor: both windows stay open (R-PC-24).
  await editorFrame(page).locator('#photocraft_canvas').focus();
  await page.keyboard.press('Escape');
  await expect(page.locator('#editor-window')).toBeVisible();
  await expect(page.locator('#texture-window')).toBeVisible();

  // An edit and a save by the editor's own keys: the scratch on disk is the saved document.
  await newLayer(page);
  await page.keyboard.press('Control+S');
  await expect.poll(() => saves(page), { timeout: 60_000 }).toBe(1);
  await expect.poll(async () => (await editor(page)).unsaved, { timeout: 20_000 }).toBe(false);
  const saved = await checkedSession(request, 'scoba', session.session);
  expect(saved.scratchChanged).toBeGreaterThan(session.scratchChanged);
  const layers = await layersOf(saved.scratch);
  console.log(`editor: saved top level ${JSON.stringify(layers.top)}`);
  // The layer the keys made is on top, outside the plane groups; the groups are as they were built.
  expect(layers.top).toEqual(['Pixel Layer 1', ...session.planes.map((plane) => `Group ${plane}`)]);
  for (const plane of session.planes) expect(layers.children[plane], plane).toEqual(['Pixel base']);
  // It belongs to no plane: every plane is as it was, and the layer is named (R-PC-76).
  expect(saved).toMatchObject({ state: 'unchanged', changed: [], leftOut: ['Layer 1'], rendered: session.rendered });
  // Negative: a save to the session starts no download.
  expect(downloads).toEqual([]);
  // Negative: the editor's keys did not reach the viewer page.
  expect(await viewer(page)).toBe(before);
  // Negative: an unchanged session opens no transfer dialog: more than two polls pass.
  await page.waitForTimeout(5000);
  expect((await editsState(page)).dialogs.transfer.open).toBe(false);

  // Negative: a write the server refuses is not confirmed. The session is discarded elsewhere, then the editor saves.
  await newLayer(page);
  const gone = await request.post(editUrl('scoba', `/${session.session}/discard`));
  expect(gone.status(), await gone.text()).toBe(200);
  await page.keyboard.press('Control+S');
  await expect.poll(() => asked.filter((url) => url.endsWith(`/${session.session}/scratch`)).length, { timeout: 60_000 }).toBeGreaterThanOrEqual(3);
  await page.waitForTimeout(1500);
  expect(await saves(page)).toBe(1);
  expect((await editor(page)).unsaved).toBe(true);
  expect(downloads).toEqual([]);

  // Closing with unsaved work asks. Keep Editing keeps the window; Close Editor closes it (R-PC-26).
  await page.locator('#editor-window .window-close').click();
  await expect(page.locator('#editor-close-dialog')).toBeVisible();
  await expect(page.locator('#editor-close-yes')).toHaveText('Close Editor');
  await page.locator('#editor-close-no').click();
  await expect(page.locator('#editor-window')).toBeVisible();
  expect(await editor(page)).toMatchObject({ open: true, session: session.session, unsaved: true });
  await page.locator('#editor-window .window-close').click();
  await page.locator('#editor-close-yes').click();
  await expect(page.locator('#editor-window')).toBeHidden();
  expect(await editor(page)).toMatchObject({ open: false, session: null, phase: 'closed' });
  expect(errors.filter((error) => !/404/.test(error))).toEqual([]);
});

test('a scratch with a mask, a blend mode, an adjustment layer, a layer style and a hidden layer keeps them and its planes through a save by the browser editor', async ({ page, request }) => {
  test.setTimeout(360_000);
  const ASSET = 'assets\\textures\\banshee_diffuse.dds';
  const judged = await request.post('/api/sc2/textures/judge?dataset=scoba', { data: { assets: [ASSET] } });
  expect(judged.status(), await judged.text()).toBe(200);
  const session = await openSession(request, 'scoba', ASSET);
  const plane = session.planes[0];
  // The scratch as a person would leave it, made by the renderer's commands: in one plane's group a red layer
  // with the blend mode Multiply and a mask over its left half, an Invert adjustment layer, a hidden white layer,
  // and a black layer with a colour overlay style.
  await changeScratch(
    session,
    painted(session, plane),
    cmd('layer.setProps', { blend: 'Multiply', opacity: 0.5 }),
    cmd('select.rect', { x: 0, y: 0, width: session.size[0] / 2, height: session.size[1], antiAlias: false }),
    cmd('layer.layerMask.revealSelection'),
    cmd('select.deselect'),
    baseOf(session, plane),
    cmd('layer.newAdjustmentLayer.invert'),
    baseOf(session, plane),
    cmd('layer.new.layer', { name: 'hidden' }),
    cmd('edit.fill', { contents: 'white' }),
    cmd('layer.setProps', { visible: false }),
    baseOf(session, plane),
    cmd('layer.new.layer', { name: 'styled' }),
    cmd('edit.fill', { contents: 'color', color: '#000000' }),
    cmd('layer.layerStyle.replace', { effects: [{ kind: 'colorOverlay', params: { color: '#00ff00' } }] }),
  );
  const edited = await checkedSession(request, 'scoba', session.session);
  expect(edited).toMatchObject({ state: 'edited', reason: '', changed: [plane], leftOut: [] });
  const was = await layersOf(edited.scratch);
  console.log(`editor: the group ${plane} holds ${JSON.stringify(was.carried[plane])}`);
  // The scratch holds what was put into it: else the comparison below proves nothing of them.
  expect(was.carried[plane].some((layer) => layer.hasMask && layer.blend === 'Multiply')).toBe(true);
  expect(was.carried[plane].some((layer) => layer.adjustment === 'invert')).toBe(true);
  expect(was.carried[plane].some((layer) => layer.effects.includes('Color Overlay'))).toBe(true);
  expect(was.carried[plane].some((layer) => layer.visible === false)).toBe(true);

  const errors = await open(page);
  await page.evaluate((target) => window.scobaeditor.edits.resume(target), { game: 'sc2', dataset: 'scoba', session: edited });
  await opened(page);
  // The editor window alone has the sessions read: the edit is offered. Keep Editing gives the keys back to the editor.
  await expect(page.locator('#edit-transfer-dialog')).toBeVisible({ timeout: 30_000 });
  await page.locator('#edit-transfer-keep').click();
  await newLayer(page);
  await page.keyboard.press('Control+S');
  await expect.poll(() => saves(page), { timeout: 60_000 }).toBe(1);

  const saved = await checkedSession(request, 'scoba', session.session);
  expect(saved.scratchChanged).toBeGreaterThan(edited.scratchChanged);
  const now = await layersOf(saved.scratch);
  // Every plane renders to the same pixels, and the group holds the same layers with what they carried.
  expect(saved.rendered).toEqual(edited.rendered);
  expect(saved).toMatchObject({ state: 'edited', changed: [plane], leftOut: ['Layer 1'] });
  expect(now.carried[plane]).toEqual(was.carried[plane]);
  for (const other of session.planes.filter((one) => one !== plane)) expect(now.carried[other], other).toEqual(was.carried[other]);
  // Negative: the same planes are not offered a second time.
  await page.waitForTimeout(5000);
  expect((await editsState(page)).dialogs.transfer.open).toBe(false);
  await page.locator('#editor-window .window-close').click();
  await expect(page.locator('#editor-window')).toBeHidden();
  expect((await request.post(editUrl('scoba', `/${session.session}/discard`))).status()).toBe(200);
  expect(errors).toEqual([]);
});

test('negative: resumed on a session that is gone, the window shows the reason and Reload Editor; after the session is there again, Reload Editor opens it', async ({ page, request }) => {
  test.setTimeout(360_000);
  const ASSET = 'assets\\textures\\colossus_diffuse.dds';
  allowErrors(/http 404 GET .*\/textures\/edit\/[0-9a-f]{16}\/scratch/, /console\.error: .*404/);
  const errors = await open(page);
  // A session as a list read it; then it is discarded elsewhere.
  const judged = await request.post('/api/sc2/textures/judge?dataset=scoba', { data: { assets: [ASSET] } });
  expect(judged.status(), await judged.text()).toBe(200);
  const session = await openSession(request, 'scoba', ASSET);
  expect((await request.post(editUrl('scoba', `/${session.session}/discard`))).status()).toBe(200);

  await page.evaluate((target) => window.scobaeditor.edits.resume(target), { game: 'sc2', dataset: 'scoba', session });
  await expect(page.locator('#editor-window')).toBeVisible();
  await expect.poll(async () => (await editor(page)).phase, { timeout: 150_000 }).toBe('failed');
  const failed = await editor(page);
  console.log(`editor: failed: ${failed.reason}; messages ${JSON.stringify(failed.messages)}`);
  expect(failed.reason).toMatch(/404/);
  expect(failed.messages).not.toContain('opened');
  await expect(page.locator('#editor-note')).toBeVisible();
  await expect(page.locator('#editor-note .editor-reason')).toHaveText(failed.reason);
  await expect(page.locator('#editor-reload')).toBeVisible();
  // Negative: the main page's Escape does not close the editor window.
  await page.locator('#editor-window .window-title').click();
  await page.keyboard.press('Escape');
  await expect(page.locator('#editor-window')).toBeVisible();

  // The session is opened again (the same origin and variant: the same id). Reload Editor loads a fresh frame on it.
  expect((await openSession(request, 'scoba', ASSET)).session).toBe(session.session);
  await page.locator('#editor-reload').click();
  await opened(page);
  await expect(page.locator('#editor-note')).toBeHidden();
  expect((await sessionOf(request, 'scoba', session.session)).state).toBe('unchanged');
  await page.locator('#editor-window .window-close').click();
  await expect(page.locator('#editor-window')).toBeHidden();
  expect(errors.filter((error) => !/404/.test(error))).toEqual([]);
});
