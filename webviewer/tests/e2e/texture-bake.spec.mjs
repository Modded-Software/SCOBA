import { test, expect } from '../fixtures.mjs';
import { cleanOwner, colourTexture, madeVariant, makeSkin, menu, openPage, ownerOf, place, setSkin, shown, storedSkins, viewState } from '../skins.mjs';

// Bake Skin (SPEC-VIEWER 17.4, SPEC-HD-TEXTURES 4.8): the menu's Bake Skin
// asks first, then bakes the instance's skin for its owner in its dataset.
// Original shows the game's textures only (R-HD-131); Unbake Skin on Original
// removes the owner's bake. A refusal changes nothing. One
// texture of the Medic gets a fast variant here (HDTEX_RUNNER=repeat). No
// other spec file uses this owner: files run side by side.

const UNIT = 'Medic';
const OWNER = `unit:${UNIT}`;
const SKIN = 'hd';
let ASSET = '';

async function prepared(request) {
  ASSET = await colourTexture(request, 'scoba', OWNER);
  const made = await madeVariant(request, 'scoba', ASSET);
  await cleanOwner(request, 'scoba', OWNER);
  await cleanOwner(request, 'stock', OWNER);
  await makeSkin(request, 'scoba', OWNER, SKIN, { [ASSET]: made.variant });
  return made;
}

/** Click the menu's bake button and answer its dialog: `#bake-skin-dialog`, or `#unbake-skin-dialog` on Original. */
async function bakeByMenu(page, id, answer, kind = 'bake') {
  await menu(page, id);
  await page.locator('#anim-menu button.skin-bake').click();
  const dialog = page.locator(`#${kind}-skin-dialog`);
  await expect(dialog).toBeVisible();
  // Capitalised buttons (R-VIEW-128).
  await expect(dialog.locator('.answers button')).toHaveText(['Cancel', kind === 'bake' ? 'Bake Skin' : 'Unbake Skin']);
  const question = await dialog.locator('p.bake-question').textContent();
  await dialog.locator(answer === 'yes' ? `#${kind}-skin-yes` : `#${kind}-skin-no`).click();
  await expect(dialog).toBeHidden();
  // Answered: done when the status line says so; a refusal says why there.
  if (answer === 'yes') await expect(page.locator('#status')).toHaveText(kind === 'unbake' ? /: unbaked$/ : /: skin \S+ baked$/, { timeout: 15_000 });
  return question;
}

/** Look at an instance at x, so a right click finds its pixels. */
async function lookAt(page, x) {
  await page.keyboard.press('Escape');
  await page.evaluate((tx) => window.scobaeditor.view({ yaw: -Math.PI / 2, pitch: 0.5, distance: 6, target: [tx, 0, 0.5] }), x);
  await page.evaluate(() => new Promise((done) => requestAnimationFrame(() => requestAnimationFrame(done))));
}

test('Bake skin asks first; cancelled, nothing is baked; answered, the owner holds the bake and the menu says so', async ({ page, request }) => {
  test.setTimeout(120_000);
  const made = await prepared(request);
  const errors = await openPage(page);
  const baker = await place(page, UNIT);
  const other = await place(page, UNIT, { x: 30 });
  const elsewhere = await place(page, UNIT, { x: 60, dataset: 'stock' });
  await setSkin(page, baker, SKIN);
  // Negative: choosing a skin writes no bake.
  expect((await ownerOf(request, 'scoba', OWNER)).bake).toBeNull();

  // Negative: cancelled, the owner has no bake.
  const asked = await bakeByMenu(page, baker, 'no');
  expect(asked).toContain(`Bake skin "${SKIN}"`);
  expect(asked).toContain(OWNER);
  expect((await ownerOf(request, 'scoba', OWNER)).bake).toBeNull();

  await bakeByMenu(page, baker, 'yes');
  const owner = await ownerOf(request, 'scoba', OWNER);
  // The skin's variant, and `original` for every texture it does not name (R-HD-131).
  expect(owner.bake.skin).toBe(SKIN);
  expect(owner.bake.textures).toEqual({ ...Object.fromEntries(Object.keys(owner.bake.textures).map((asset) => [asset, 'original'])), [ASSET]: made.variant });
  // The owner shows its own bake now; its skins are the ones it holds, no other is offered.
  expect(owner.shows[ASSET]).toBe(made.variant);
  expect(owner.skins.map((one) => one.name)).toEqual([SKIN]);
  await menu(page, baker);
  expect((await viewState(page)).pick.menu.skins).toMatchObject({ bake: 'Bake Skin', bakeDisabled: false, badge: `🍞 ${SKIN}` });
  await expect(page.locator('#anim-menu span.skin-baked')).toHaveText(`🍞 ${SKIN}`);
  // Negative: the trash of the baked skin is disabled and says why (R-VIEW-126, R-HD-136).
  await page.locator('#anim-menu button.skin-choice').click();
  const trash = page.locator(`#anim-menu ul.skin-list li[data-skin="${SKIN}"] button.skin-trash`);
  await expect(trash).toBeDisabled();
  await expect(trash).toHaveAttribute('title', 'baked: unbake it or bake another skin first');
  await page.locator('#anim-menu button.skin-choice').click();
  // The bake is the owner's: the other instance, on Original, shows the badge too, and Unbake can be used.
  await lookAt(page, 30);
  await menu(page, other);
  expect((await viewState(page)).pick.menu.skins).toMatchObject({ value: 'original', bake: 'Unbake Skin', bakeDisabled: false, badge: `🍞 ${SKIN}` });
  // Original shows the game's textures only (R-HD-131), and no choice changes (R-VIEW-122).
  expect(await shown(page, other)).toMatchObject({ skin: 'original', overrides: 0 });
  expect((await shown(page, baker)).skin).toBe(SKIN);
  // Negative: the bake is scoba's; stock's Medic is untouched.
  expect((await ownerOf(request, 'stock', OWNER)).bake).toBeNull();
  expect((await shown(page, elsewhere)).overrides).toBe(0);

  // Unbake on Original asks first; cancelled, the bake stays; answered, it goes.
  const unasked = await bakeByMenu(page, other, 'no', 'unbake');
  expect(unasked).toContain('Remove the bake');
  expect((await ownerOf(request, 'scoba', OWNER)).bake).toMatchObject({ skin: SKIN });
  await bakeByMenu(page, other, 'yes', 'unbake');
  expect((await ownerOf(request, 'scoba', OWNER)).bake).toBeNull();
  await menu(page, other);
  expect((await viewState(page)).pick.menu.skins).toMatchObject({ bake: 'Unbake Skin', bakeDisabled: true, badge: null });
  // Negative: the skins themselves stay.
  expect(storedSkins(await ownerOf(request, 'scoba', OWNER))).toEqual([{ name: SKIN, textures: { [ASSET]: made.variant } }]);
  expect(errors).toEqual([]);
});
