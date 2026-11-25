import { test, expect } from '../fixtures.mjs';
import { cleanOwner, colourTexture, idle, madeVariant, makeSkin, menu, openPage, ownerOf, pickRow, place, post, setSkin, shown, skinChoices, skinDialog, storedSkins } from '../skins.mjs';

// The skin editor (SPEC-VIEWER 17.6, src/page/features/skins/editor.ts):
// opened from the menu's list, by the edit icon of a skin or by "Add New
// Skin…". It has no name box and no Copy (R-VIEW-118). Its first tile is In
// game, what the game shows; its last is Upscale Texture (R-VIEW-129, 131).
// A tile click picks it and changes nothing else; Save to Skin… asks the
// target and shows each change, then sets the picks; every instance on the
// skin follows (R-VIEW-133). A saved skin has Rename Skin and Delete Skin;
// each asks first; delete is marked dangerous (R-VIEW-128, 136; that it is
// red is an operator check). Each worker has its own store (tests/fixtures.mjs).

const UNIT = 'Marauder';
const OWNER = `unit:${UNIT}`;
const editor = (page) => page.evaluate(() => window.sc2viewer.skinEditor());

/** Open the editor from the instance's menu: the edit icon of a skin, or "Add New Skin…" (skin null). */
async function edit(page, id, skin = null) {
  await menu(page, id);
  if (skin === null) {
    await page.locator('#anim-menu button.skin-choice').click();
    await page.locator('#anim-menu ul.skin-list button.skin-add').click();
  } else await pickRow(page, skin, 'edit');
  await expect(page.locator('#skin-editor')).toBeVisible();
  await expect.poll(async () => (await editor(page)).tiles.length, { timeout: 15_000 }).toBeGreaterThan(2);
  return editor(page);
}

const tile = (page, id) => page.locator(`#skin-editor .skin-tile[data-tile="${id}"]`);

/** Show the editor's tiles of `asset`. */
async function choose(page, asset) {
  await page.locator(`#skin-editor .skin-texture[data-asset="${asset.replace(/\\/g, '\\\\')}"]`).click();
  await expect.poll(async () => (await editor(page)).selected).toBe(asset);
}

/** Answer the open skin dialog: `yes` or `no`, with a name typed first when given. */
async function answer(page, id, yes, name) {
  await expect(page.locator(`#${id}-dialog`)).toBeVisible();
  if (name !== undefined) await page.fill(`#${id}-dialog input.skin-name-box`, name);
  await page.locator(`#${id}-${yes ? 'yes' : 'no'}`).click();
  await expect(page.locator(`#${id}-dialog`)).toBeHidden();
}

test('Save to Skin… sets the pick in the skin open; every instance showing it follows; In game can be picked', async ({ page, request }) => {
  test.setTimeout(150_000);
  const asset = await colourTexture(request, 'scoba', OWNER);
  const made = await madeVariant(request, 'scoba', asset);
  await cleanOwner(request, 'scoba', OWNER);
  await makeSkin(request, 'scoba', OWNER, 'mine', {});
  const errors = await openPage(page);
  const id = await place(page, UNIT);
  const other = await place(page, UNIT, { x: 30, skin: 'mine' });
  const plain = await place(page, UNIT, { x: 60 });
  await setSkin(page, id, 'mine');
  const opened = await edit(page, id, 'mine');
  expect(opened.buttons).toEqual(['Rename Skin', 'Delete Skin']);
  expect(opened.danger).toEqual(['Delete Skin']);
  await choose(page, asset);
  const tiles = (await editor(page)).tiles;
  expect(tiles.find((one) => one.id === made.variant)).toMatchObject({ kind: 'variant', highlighted: false, band: 'ok', info: '' });
  await expect(tile(page, made.variant).locator('.tex-preview img')).toHaveCount(1, { timeout: 15_000 });
  // A number in the ok band has no info mark.
  await expect(tile(page, made.variant).locator('.tile-info')).toHaveCount(0);

  await tile(page, made.variant).click();
  await expect.poll(async () => (await editor(page)).tiles.find((one) => one.id === made.variant).highlighted).toBe(true);
  // Negative: the click stores nothing; no instance changes (R-VIEW-133).
  expect(storedSkins(await ownerOf(request, 'scoba', OWNER))[0].textures).toEqual({});
  expect((await shown(page, other)).overrides).toBe(0);
  await page.locator('#skin-editor button.skin-draft-save').click();
  await expect(page.locator('#skin-draft-dialog')).toBeVisible();
  // The skin open is the target; New Skin is offered too.
  expect(await skinDialog(page)).toMatchObject({ targets: ['new', 'mine'], target: 'mine', lines: [`${asset.split('\\').pop()}: original → ${made.variant}`] });
  await answer(page, 'skin-draft', true);
  await expect.poll(async () => storedSkins(await ownerOf(request, 'scoba', OWNER))[0].textures).toEqual({ [asset]: made.variant });
  // Both instances on "mine" follow without a reload.
  await expect.poll(async () => (await shown(page, other)).overrides).toBe(1);
  await expect.poll(async () => (await shown(page, id)).overrides).toBe(1);
  // Negative: the instance on Original does not, and no New Skin was made.
  expect((await shown(page, plain)).overrides).toBe(0);
  expect(storedSkins(await ownerOf(request, 'scoba', OWNER)).map((one) => one.name)).toEqual(['mine']);

  // In game: nothing is baked, so the game shows the original; it can be picked and saved.
  expect((await editor(page)).tiles[0]).toMatchObject({ kind: 'in-game', variant: 'original', highlighted: false });
  await tile(page, 'in-game').click();
  expect((await editor(page)).picks).toEqual({ [asset]: 'original' });
  await page.locator('#skin-editor button.skin-draft-save').click();
  await answer(page, 'skin-draft', true);
  await expect.poll(async () => storedSkins(await ownerOf(request, 'scoba', OWNER))[0].textures).toEqual({ [asset]: 'original' });
  await expect.poll(async () => (await shown(page, id)).overrides).toBe(0);
  expect(errors).toEqual([]);
});

test('Rename Skin asks a name and keeps the instances on the skin; Delete Skin asks first, then they show Original', async ({ page, request }) => {
  test.setTimeout(120_000);
  await cleanOwner(request, 'scoba', OWNER);
  await makeSkin(request, 'scoba', OWNER, 'old', {});
  const errors = await openPage(page);
  const id = await place(page, UNIT, { skin: 'old' });
  await idle(page);
  await edit(page, id, 'old');
  await page.locator('#skin-editor button.skin-rename').click();
  expect(await skinDialog(page)).toMatchObject({ id: 'skin-rename-dialog', title: 'Rename Skin', buttons: ['Cancel', 'Rename Skin'], danger: false });
  await expect(page.locator('#skin-rename-dialog input.skin-name-box')).toHaveValue('old');
  // Negative: cancelled, the name stays.
  await answer(page, 'skin-rename', false, 'kept');
  expect(storedSkins(await ownerOf(request, 'scoba', OWNER)).map((one) => one.name)).toEqual(['old']);
  await page.locator('#skin-editor button.skin-rename').click();
  await answer(page, 'skin-rename', true, 'renamed');
  await expect.poll(async () => (await editor(page)).skin).toBe('renamed');
  expect(storedSkins(await ownerOf(request, 'scoba', OWNER)).map((one) => one.name)).toEqual(['renamed']);
  expect((await shown(page, id)).skin).toBe('renamed');

  // Negative: cancelled, the skin stays.
  await page.locator('#skin-editor button.skin-delete').click();
  expect(await skinDialog(page)).toMatchObject({ id: 'skin-delete-dialog', title: 'Delete Skin', buttons: ['Cancel', 'Delete Skin'], danger: true });
  await answer(page, 'skin-delete', false);
  expect(storedSkins(await ownerOf(request, 'scoba', OWNER)).map((one) => one.name)).toEqual(['renamed']);

  await page.locator('#skin-editor button.skin-delete').click();
  await answer(page, 'skin-delete', true);
  await expect.poll(async () => storedSkins(await ownerOf(request, 'scoba', OWNER))).toEqual([]);
  await expect.poll(async () => (await shown(page, id)).skin).toBe('original');
  // The editor follows the instance a moment later (e2e10: read once, it was still "new").
  await expect.poll(async () => (await editor(page)).skin).toBe('original');
  expect(errors).toEqual([]);
});

test('negative: the baked skin cannot be deleted, in the editor or by the service; a rename renames it in the bake', async ({ page, request }) => {
  test.setTimeout(120_000);
  await cleanOwner(request, 'scoba', OWNER);
  try {
    await makeSkin(request, 'scoba', OWNER, 'old', {});
    await makeSkin(request, 'scoba', OWNER, 'spare', {});
    const baked = await post(request, 'bake', 'scoba', { owner: OWNER, skin: 'old' });
    expect(baked.status(), await baked.text()).toBe(200);
    const bakeBefore = (await ownerOf(request, 'scoba', OWNER)).bake;
    const errors = await openPage(page);
    const id = await place(page, UNIT, { skin: 'old' });
    await idle(page);
    const opened = await edit(page, id, 'old');
    await expect(page.locator('#skin-editor button.skin-delete')).toBeDisabled();
    expect((await editor(page)).deleteBlocked).toBe('baked: unbake it or bake another skin first');
    // In game: baked; its amber line follows whether the package holds the bake (R-VIEW-131).
    const held = bakeBefore && (await ownerOf(request, 'scoba', OWNER)).held;
    console.log(`in game ${JSON.stringify(opened.tiles[0])}, owner held ${held}`);
    expect(opened.tiles[0]).toMatchObject({ kind: 'in-game', variant: 'original', note: held ? '' : 'not in the package yet: build the map' });
    await expect(tile(page, 'in-game')).toContainText('baked');
    await expect(tile(page, 'in-game')).not.toContainText('not baked');
    const refused = await post(request, 'skin', 'scoba', { owner: OWNER, action: 'delete', name: 'old' });
    console.log(`baked delete ${refused.status()} ${await refused.text()}`);
    expect(refused.status()).toBe(400);
    expect(await refused.text()).toContain('is baked; unbake it or bake another skin first');
    expect(storedSkins(await ownerOf(request, 'scoba', OWNER)).map((one) => one.name)).toEqual(['old', 'spare']);
    // A rename renames it in the bake; the bake's textures stay.
    await page.locator('#skin-editor button.skin-rename').click();
    await answer(page, 'skin-rename', true, 'kept');
    await expect.poll(async () => (await ownerOf(request, 'scoba', OWNER)).bake).toEqual({ ...bakeBefore, skin: 'kept' });
    await expect.poll(async () => (await editor(page)).skin).toBe('kept');
    await expect(page.locator('#skin-editor button.skin-delete')).toBeDisabled();
    // Negative: a skin that is not baked can be deleted.
    const spare = await post(request, 'skin', 'scoba', { owner: OWNER, action: 'delete', name: 'spare' });
    expect(spare.status(), await spare.text()).toBe(200);
    // Negative: a name another skin holds, in another case, is refused (R-HD-138).
    await makeSkin(request, 'scoba', OWNER, 'two', {});
    const clash = await post(request, 'skin', 'scoba', { owner: OWNER, action: 'rename', name: 'two', new: 'KEPT' });
    expect(clash.status()).toBe(400);
    expect(await clash.text()).toContain("there is a skin 'kept' already");
    expect(errors.filter((line) => !/status of 400/.test(line))).toEqual([]);
  } finally {
    await cleanOwner(request, 'scoba', OWNER);
  }
});

test('a doodad is an owner of its own: its actor', async ({ page }) => {
  const errors = await openPage(page);
  const tree = await page.evaluate(() => window.sc2viewer.addDoodad('ZerusTree', { x: 0, y: 0, pick: 0.5 }));
  await idle(page);
  const choices = await skinChoices(page, tree);
  expect(choices.owner).toBe('actor:ZerusTree');
  expect(choices.choices[0]).toBe('original');
  expect(choices.state).toMatchObject({ owner: 'actor:ZerusTree', layer: 'actor' });
  expect(errors).toEqual([]);
});
