import { test, expect } from '../fixtures.mjs';
import { chooseRow, textureFrame } from '../page.mjs';
import { sceneItem, sceneText, settled } from '../scene.mjs';
import { cleanOwner, idle, madeVariant, menu, openPage, ownerOf, place, post, setSkin, shown, skinChoices, skinDialog, storedSkins, viewState } from '../skins.mjs';

// New skins and their names (R-HD-137, R-VIEW-133, R-VIEW-156, R-VIEW-157):
// - "Add New Skin…" makes the next New Skin N at once, shows it and opens
//   the texture window on it; no question asks to save another first.
// - Save to Skin… from Original makes the next New Skin N.
// - The texture window's Rename Skin… renames the skin the instance shows;
//   the instance, the window and the bake follow.
// - The instance menu closes when a window opens, or on a press in a
//   window's frame; a press in the menu keeps it.
// Engine and server state decide. The Hydralisk is this file's owner alone:
// files run side by side. The runner needs no GPU (HDTEX_RUNNER=repeat).

const UNIT = 'Hydralisk';
const OWNER = `unit:${UNIT}`;
const names = async (request) => (await ownerOf(request, 'scoba', OWNER)).skins.map((one) => one.name);
const frameState = (page) => textureFrame(page).evaluate(() => window.hdtex.state());
const windowDone = (page) => expect.poll(async () => (await page.evaluate(() => window.scobaeditor.textureWindow())).originals, { timeout: 30_000 }).toBe('done');
/** Open the texture window on the instance by its row in the instance list. */
async function openWindow(page, id) {
  await page.locator(`#scene li[data-id="${id}"] .head .name`).dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  await windowDone(page);
}
/** The Hydralisk's diffuse texture (hydralisk_remastered_diff.dds): a colour plane that does not tile and can be upscaled. */
async function diffuseOf(request) {
  const { textures } = await ownerOf(request, 'scoba', OWNER);
  const judged = await post(request, 'judge', 'scoba', { assets: textures });
  expect(judged.status(), await judged.text()).toBe(200);
  const found = (await judged.json()).textures.find((state) => /_diff\.dds$/.test(state.asset) && state.colour && !state.tiles && !state.reason);
  expect(found, `${OWNER}: a diffuse texture among ${textures.join(', ')}`).toBeTruthy();
  return found.asset;
}
/** Click "Add New Skin…" in the open menu's skin list. */
async function addNewSkin(page) {
  await page.locator('#anim-menu button.skin-choice').click();
  await page.locator('#anim-menu ul.skin-list button.skin-add').click();
}

test('Add New Skin… makes New Skin 1, then New Skin 2: each shown at once, the window opened on it, nothing asked; the menu closes as the window opens', async ({ page, request }) => {
  test.setTimeout(90_000);
  await cleanOwner(request, 'scoba', OWNER);
  const errors = await openPage(page);
  const id = await place(page, UNIT);
  await menu(page, id);
  await addNewSkin(page);
  await expect.poll(async () => (await shown(page, id)).skin, { timeout: 15_000 }).toBe('New Skin 1');
  // The window opened on the instance; the menu closed with it (R-VIEW-157).
  await expect(page.locator('#texture-window')).toBeVisible();
  await expect(page.locator('#anim-menu')).toHaveCount(0);
  expect((await viewState(page)).pick.menu).toBeNull();
  await windowDone(page);
  await expect(page.locator('#texture-window')).toContainText(`textures · ${UNIT}`);
  await expect(page.locator('#texture-window .window-title')).toHaveText(/· New Skin 1$/);
  // Negative: no question asked to save or discard anything first.
  expect(await skinDialog(page)).toBeNull();
  expect(storedSkins(await ownerOf(request, 'scoba', OWNER))).toEqual([{ name: 'New Skin 1', textures: {} }]);

  // A second one: New Skin 2, beside New Skin 1.
  await page.locator('#texture-window .window-close').click();
  await menu(page, id);
  await addNewSkin(page);
  await expect.poll(async () => (await shown(page, id)).skin, { timeout: 15_000 }).toBe('New Skin 2');
  expect(await names(request)).toEqual(['New Skin 1', 'New Skin 2']);
  expect(await skinDialog(page)).toBeNull();
  // The list offers both, after Original.
  expect((await page.evaluate((i) => window.scobaeditor.skinChoices(i), id)).choices).toEqual(['original', 'New Skin 1', 'New Skin 2']);
  // Negative: a deleted number below the highest is not taken again.
  expect((await post(request, 'skin', 'scoba', { owner: OWNER, action: 'delete', name: 'New Skin 1' })).status()).toBe(200);
  const third = await post(request, 'skin', 'scoba', { owner: OWNER, action: 'copy', name: null, from: 'original' });
  expect((await third.json()).made).toBe('New Skin 3');
  expect(errors).toEqual([]);
});

test('Save to Skin… on Original makes the next New Skin N with the picks; the skin made before does not change', async ({ page, request }) => {
  test.setTimeout(150_000);
  const asset = await diffuseOf(request);
  const made = await madeVariant(request, 'scoba', asset);
  await cleanOwner(request, 'scoba', OWNER);
  expect((await post(request, 'skin', 'scoba', { owner: OWNER, action: 'copy', name: null, from: 'original' })).status()).toBe(200);
  const errors = await openPage(page);
  const id = await place(page, UNIT);
  await openWindow(page, id);
  const frame = textureFrame(page);
  await chooseRow(frame, asset);
  await frame.locator(`#cards .skin-tile[data-variant="${made.variant}"]`).click();
  await frame.locator('#draft button.skin-draft-save').click();
  await expect.poll(async () => (await skinDialog(page))?.id ?? null, { timeout: 10_000 }).toBe('skin-draft-dialog');
  const dialog = await skinDialog(page);
  // On Original the new skin is chosen first; its name is the one the pipeline says it gives next.
  const owner = await ownerOf(request, 'scoba', OWNER);
  expect(owner.next).toBe('New Skin 2');
  expect(dialog.into).toEqual({ kind: 'new' });
  expect(dialog.next).toBe(`New skin: ${owner.next}`);
  // Negative: the list of existing skins holds skin names only.
  expect(dialog.skins).toEqual(['New Skin 1']);
  expect(dialog.existingDisabled).toBe(false);
  expect(dialog.text).toContain('1 of 1 textures change in New Skin 2.');
  expect(dialog.text).toContain('New Skin 2 will be made from Original');
  await page.locator('#skin-draft-yes').click();
  await expect.poll(async () => (await shown(page, id)).skin, { timeout: 15_000 }).toBe('New Skin 2');
  expect(storedSkins(await ownerOf(request, 'scoba', OWNER))).toEqual([
    { name: 'New Skin 1', textures: {} },
    { name: 'New Skin 2', textures: { [asset]: made.variant } },
  ]);
  expect(errors).toEqual([]);
});

test('Rename Skin… in the texture window: refused names keep it disabled; a good one renames the skin, and the instance, the window and the bake follow', async ({ page, request }) => {
  test.setTimeout(90_000);
  await cleanOwner(request, 'scoba', OWNER);
  for (const name of [null, 'Other']) expect((await post(request, 'skin', 'scoba', { owner: OWNER, action: 'copy', name, from: 'original' })).status()).toBe(200);
  const baked = await post(request, 'bake', 'scoba', { owner: OWNER, skin: 'New Skin 1' });
  expect(baked.status(), await baked.text()).toBe(200);
  const errors = await openPage(page);
  const id = await place(page, UNIT);
  await openWindow(page, id);
  // Negative: on Original there is no name to change.
  await expect.poll(async () => (await frameState(page)).skinLine, { timeout: 10_000 }).toEqual({ shown: true, text: 'Skin: Original', renameDisabled: true, renameTitle: 'Original names nothing; pick or make a skin first' });
  await setSkin(page, id, 'New Skin 1');
  await expect.poll(async () => (await frameState(page)).skinLine, { timeout: 10_000 }).toMatchObject({ text: 'Skin: New Skin 1', renameDisabled: false });
  await textureFrame(page).locator('#skin-rename').click();
  await expect(page.locator('#skin-rename-dialog')).toBeVisible();
  const state = async () => {
    const one = await skinDialog(page);
    return { name: one.name, why: one.lines[0], disabled: one.yesDisabled };
  };
  expect(await state()).toEqual({ name: 'New Skin 1', why: 'that is its name now', disabled: true });
  expect((await skinDialog(page)).text).toContain('the bake names the new name');
  // Negative: a taken name (case ignored), Original and a double space are refused.
  for (const [typed, why] of [
    ['other', 'there is a skin "Other" already'],
    ['Original', 'Original is the skin that names nothing'],
    ['a  b', 'a name is 1 to 40 letters, digits, - or _, with one space between words'],
  ]) {
    await page.fill('#skin-rename-name', typed);
    expect(await state(), typed).toEqual({ name: typed, why, disabled: true });
  }
  await page.fill('#skin-rename-name', 'Hull Plates');
  expect(await state()).toEqual({ name: 'Hull Plates', why: '', disabled: false });
  await page.locator('#skin-rename-yes').click();
  await expect(page.locator('#skin-rename-dialog')).toBeHidden();
  // The skin, the instance, the bake and the window all carry the new name.
  await expect.poll(async () => (await shown(page, id)).skin, { timeout: 15_000 }).toBe('Hull Plates');
  // The instance takes the name first; the server's rename is done when the owner says so. Its skins and its bake
  // change in one read (skinbakes.rename): no read shows the new skin name beside the old bake name.
  const seen = [];
  await expect
    .poll(async () => {
      const now = await ownerOf(request, 'scoba', OWNER);
      seen.push([now.skins.map((one) => one.name).join('+'), now.bake?.skin ?? null]);
      return now.skins.some((one) => one.name === 'Hull Plates');
    }, { timeout: 15_000 })
    .toBe(true);
  expect(seen.filter(([skins, bake]) => skins.includes('Hull Plates') !== (bake === 'Hull Plates')), JSON.stringify(seen)).toEqual([]);
  const owner = await ownerOf(request, 'scoba', OWNER);
  expect(owner.skins.map((one) => one.name)).toEqual(['Hull Plates', 'Other']);
  expect(owner.bake.skin).toBe('Hull Plates');
  await expect(page.locator('#texture-window .window-title')).toHaveText(/· Hull Plates$/);
  await expect.poll(async () => (await frameState(page)).skinLine.text, { timeout: 10_000 }).toBe('Skin: Hull Plates');
  // Negative: the other skin keeps its name.
  expect(owner.skins[1]).toEqual({ name: 'Other', textures: {} });
  await post(request, 'unbake', 'scoba', { owner: OWNER });
  expect(errors).toEqual([]);
});

/** Import a scene of one Hydralisk on `skin`; its item. */
async function importOn(page, skin) {
  await page.evaluate((text) => window.scobaeditor.scenes.importText(text), sceneText([sceneItem({ category: 'units', record: UNIT, variant: null }, { options: { skin } })]));
  await settled(page);
  const items = (await viewState(page)).items;
  expect(items.map((one) => one.skin)).toEqual([skin]);
  return items[0];
}

test('data from before New Skin N: a stored skin named "new" and a scene item on it are an ordinary skin, shown as it is', async ({ page, request }) => {
  test.setTimeout(60_000);
  await cleanOwner(request, 'scoba', OWNER);
  // A skin called "new" is a name like any other; the pipeline neither renames nor refuses it.
  expect((await post(request, 'skin', 'scoba', { owner: OWNER, action: 'copy', name: 'new', from: 'original' })).status()).toBe(200);
  const owner = await ownerOf(request, 'scoba', OWNER);
  expect(owner.skins.map((one) => one.name)).toEqual(['new']);
  expect(owner.next).toBe('New Skin 1');
  const errors = await openPage(page);
  const item = await importOn(page, 'new');
  // Negative: it is not missing, and the list and the button say "new", the name the owner holds.
  expect(item.missingSkin).toBe(false);
  expect((await skinChoices(page, item.id)).choices).toEqual(['original', 'new']);
  await menu(page, item.id);
  const row = (await viewState(page)).pick.menu.skins;
  expect({ value: row.value, label: row.label, missing: row.missing }).toEqual({ value: 'new', label: 'new', missing: '' });
  expect(errors).toEqual([]);
});

test('an item on a skin its owner does not have: said once, shown as missing in red, no override, nothing acts on it; choosing a skin ends it', async ({ page, request }) => {
  test.setTimeout(60_000);
  await cleanOwner(request, 'scoba', OWNER);
  expect((await post(request, 'skin', 'scoba', { owner: OWNER, action: 'copy', name: null, from: 'original' })).status()).toBe(200);
  const errors = await openPage(page);
  const item = await importOn(page, 'nosuch');
  expect(item.missingSkin).toBe(true);
  expect((await shown(page, item.id)).overrides).toBe(0);
  const said = 'Hydralisk: skin "nosuch" does not exist in scoba';
  const log = async () => (await page.locator('#status-log').textContent()) ?? '';
  await expect.poll(log).toContain(said);
  await menu(page, item.id);
  const why = `${OWNER} has no skin "nosuch"; choose another skin`;
  const row = (await viewState(page)).pick.menu.skins;
  expect({ value: row.value, label: row.label, missing: row.missing }).toEqual({ value: 'nosuch', label: 'nosuch (missing)', missing: why });
  // Its row comes first, disabled; then Original and the skins the owner has.
  expect(row.rows.map((one) => one.name)).toEqual(['nosuch', 'original', 'New Skin 1', '']);
  await page.locator('#anim-menu button.skin-choice').click();
  await expect(page.locator('#anim-menu li[data-skin="nosuch"] button.skin-pick')).toBeDisabled();
  await expect(page.locator('#anim-menu button.skin-choice .skin-label')).toHaveClass(/missing/);
  // Negative: nothing acts on a skin that is not there.
  expect({ bake: row.bakeDisabled, bakeTitle: row.bakeTitle, upscale: row.upscaleDisabled, upscaleTitle: row.upscaleTitle }).toEqual({ bake: true, bakeTitle: why, upscale: true, upscaleTitle: why });
  await expect(page.locator('#anim-menu button.skin-add')).toBeDisabled();
  // Negative: the scene keeps the name; nothing put another skin in its place.
  expect((await page.evaluate(() => window.scobaeditor.scenes.document())).items[0].options.skin).toBe('nosuch');
  // Negative: set refuses a skin the owner does not have before anything changes.
  expect(await page.evaluate((i) => window.scobaeditor.setSkin(i, 'other').then(() => 'set', (e) => e.message), item.id)).toBe(`${OWNER} has no skin "other"`);
  expect((await shown(page, item.id)).skin).toBe('nosuch');
  // Said once.
  expect((await log()).split(said).length - 1).toBe(1);
  // Choosing a skin the owner has ends it.
  await setSkin(page, item.id, 'New Skin 1');
  expect((await viewState(page)).items[0]).toMatchObject({ skin: 'New Skin 1', missingSkin: false });
  expect(errors).toEqual([]);
});

test.describe('a view wider than the texture window', () => {
  // The window is 1100 wide, from the right of the gallery: an instance in the middle of a 3400 wide view stays clear of it.
  test.use({ viewport: { width: 3400, height: 900 } });
  test('the instance menu closes on a press inside the texture window; a press in the menu keeps it', async ({ page, request }) => {
    test.setTimeout(60_000);
    await cleanOwner(request, 'scoba', OWNER);
    const errors = await openPage(page);
    const id = await place(page, UNIT);
    await openWindow(page, id);
    await menu(page, id);
    // Negative: a press in the menu itself keeps it.
    await page.locator('#anim-menu .title').click();
    await expect(page.locator('#anim-menu')).toBeVisible();
    // A press in the frame of the window: the page never sees it, and the menu closes all the same.
    await textureFrame(page).locator('#search').click();
    await expect(page.locator('#anim-menu')).toHaveCount(0);
    expect((await viewState(page)).pick.menu).toBeNull();
    // Negative: the window stays open.
    await expect(page.locator('#texture-window')).toBeVisible();
    await idle(page);
    expect(errors).toEqual([]);
  });
});
