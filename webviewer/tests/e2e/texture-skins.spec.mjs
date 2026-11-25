import { test, expect } from '../fixtures.mjs';
import { cleanOwner, menu, openPage, ownerOf, place, shown, skinChoices, viewState } from '../skins.mjs';

// The skins of the instances (SPEC-VIEWER 17.4, src/page/core/skins.ts): an
// instance shows one skin of its owner. Original names nothing: it shows the
// game's textures (R-HD-131). A skin names a variant per texture. The menu's
// skin list chooses it: Original, the saved skins and New Skin with edit and
// trash, then "Add New Skin…" (R-VIEW-126). The choice has a skin icon
// and an arrow (R-VIEW-137). Ctrl+L switches the menu's "loop". The
// tests' store is fresh each run; the Zergling's owner never gets a skin.

const ADD = { name: '', label: 'Add New Skin…', icons: [] };
const ORIGINAL_ROW = { name: 'original', label: 'Original', icons: [] };
/** The menu's skin state on Original with nothing baked: Unbake is there and disabled. */
const onOriginal = (choices, rows) => ({ value: 'original', label: 'Original', dropdown: true, choices, rows: [...rows, ADD], bake: 'Unbake Skin', bakeDisabled: true, badge: null });

const selectRow = (page, id) => page.locator(`#scene li[data-id="${id}"] .head .name`).click();

test('negative: an owner with no skin offers Original alone and shows its own textures', async ({ page, request }) => {
  const clean = await cleanOwner(request, 'scoba', 'unit:Zergling');
  // Negative: nothing is baked, so no New Skin is offered (R-HD-137).
  expect(clean.skins).toEqual([]);
  const errors = await openPage(page);
  const zergling = await place(page, 'Zergling');
  expect(await shown(page, zergling)).toEqual({ skin: 'original', overrides: 0, largest: 1024, blue: false });
  expect(await skinChoices(page, zergling)).toMatchObject({ owner: 'unit:Zergling', choices: ['original'] });
  await menu(page, zergling);
  await expect(page.locator('#anim-menu input.loop')).toHaveCount(1);
  await expect(page.locator('#anim-menu button.skin-choice')).toHaveText('Original');
  // The old select is gone (R-VIEW-126).
  await expect(page.locator('#anim-menu select')).toHaveCount(0);
  // Negative: nothing is baked, so no badge, and Unbake Skin cannot be used.
  expect((await viewState(page)).pick.menu.skins).toEqual(onOriginal(['original'], [ORIGINAL_ROW]));
  await expect(page.locator('#anim-menu span.skin-baked')).toBeHidden();
  await expect(page.locator('#anim-menu button.skin-bake')).toBeDisabled();
  // The list: Original without an icon, then Add New Skin…
  await page.locator('#anim-menu button.skin-choice').click();
  await expect(page.locator('#anim-menu ul.skin-list li')).toHaveCount(2);
  await expect(page.locator('#anim-menu ul.skin-list li[data-skin="original"] button.skin-edit, #anim-menu ul.skin-list li[data-skin="original"] button.skin-trash')).toHaveCount(0);
  await expect(page.locator('#anim-menu ul.skin-list button.skin-add')).toHaveText('Add New Skin…');
  expect(errors).toEqual([]);
});

test('a unit and a doodad the map does not place have an owner in scoba; the menu offers skin and Upscale', async ({ page, request }) => {
  // Operator 2026-11-25: every unit and doodad the viewer lists can get a skin, placed or not.
  // Nova and the doodad Aiur_CliffRocks are not placed on the SCOBA map.
  for (const owner of ['unit:Nova', 'actor:Aiur_CliffRocks']) {
    const found = await ownerOf(request, 'scoba', owner);
    expect(found, owner).toMatchObject({ owner });
  }
  // Negative: a unit in no catalog has no owner.
  const none = await request.get(`/api/sc2/textures/owner?${new URLSearchParams({ dataset: 'scoba', owner: 'unit:NoSuchUnit' })}`);
  expect(none.status()).toBe(200);
  expect((await none.json()).owner).toBeNull();
  const errors = await openPage(page);
  const nova = await place(page, 'Nova');
  expect(await skinChoices(page, nova)).toMatchObject({ owner: 'unit:Nova', choices: ['original'] });
  await menu(page, nova);
  await expect(page.locator('#anim-menu button.skin-choice')).toHaveText('Original');
  await expect(page.locator('#anim-menu button.skin-upscale')).toHaveCount(1);
  await expect(page.locator('#anim-menu button.skin-bake')).toHaveCount(1);
  expect(errors).toEqual([]);
});

test('Ctrl+L switches the "loop" choice when a unit is selected; the menu shows it', async ({ page }) => {
  const errors = await openPage(page);
  const marine = await place(page, 'Marine');
  expect((await viewState(page)).pick.loop).toBe(false);
  // Negative: nothing is selected.
  await page.keyboard.press('Control+l');
  expect((await viewState(page)).pick.loop).toBe(false);

  await selectRow(page, marine);
  await page.keyboard.press('Control+l');
  expect((await viewState(page)).pick.loop).toBe(true);
  await expect(page.locator('#status')).toHaveText('loop on');
  await menu(page, marine);
  await expect(page.locator('#anim-menu input.loop')).toBeChecked();
  // With the choice on, a picked animation loops: it becomes the unit's own.
  const item = async () => (await viewState(page)).items.find((i) => i.id === marine);
  const standing = await item();
  const name = standing.sequences.find((s) => s !== standing.sequenceName && /Walk/.test(s));
  expect(name).toBeTruthy();
  await page.locator('#anim-menu button', { hasText: new RegExp(`^${name}$`) }).click();
  expect((await item()).oneShot).toBeNull();
  expect((await item()).sequenceName).toBe(name);

  await page.keyboard.press('Control+l');
  await expect(page.locator('#anim-menu input.loop')).not.toBeChecked();
  expect((await viewState(page)).pick.loop).toBe(false);
  await expect(page.locator('#status')).toHaveText('loop off');
  expect(errors).toEqual([]);
});

test('Ctrl+L never reaches the browser, in the page, a text field or the texture window; Ctrl+H is the browser\'s again', async ({ page }) => {
  const errors = await openPage(page);
  const marine = await place(page, 'Marine');
  /** Whether a keydown sent to `where` had its default action cancelled (true: the browser does nothing). */
  const cancelled = (key, where, mods = { ctrlKey: true }) =>
    page.evaluate(([k, w, m]) => {
      const target = w === 'frame' ? document.getElementById('texture-frame').contentDocument.body : w === 'field' ? document.getElementById('search-units') : document.body;
      if (w === 'field') target.focus();
      const sent = new (target.ownerDocument.defaultView.KeyboardEvent)('keydown', { key: k, bubbles: true, cancelable: true, ...m });
      const done = !target.dispatchEvent(sent);
      if (w === 'field') target.blur();
      return done;
    }, [key, where, mods]);

  // Nothing selected: consumed, and the toast says why nothing happened.
  expect(await cancelled('l', 'page')).toBe(true);
  await expect(page.locator('#status')).toHaveText('Ctrl+L: select an instance first');
  expect(await cancelled('l', 'field')).toBe(true);
  await page.locator(`#scene li[data-id="${marine}"] .head .name`).dblclick();
  await expect(page.locator('#texture-window')).toBeVisible();
  await page.waitForFunction(() => document.getElementById('texture-frame').contentDocument.readyState === 'complete' && window.sc2viewer.textureWindow().originals !== 'loading');
  expect(await cancelled('l', 'frame')).toBe(true);
  // Negative: Ctrl+H has no meaning here any more, and other keys keep the browser's.
  expect(await cancelled('h', 'page')).toBe(false);
  expect(await cancelled('h', 'frame')).toBe(false);
  expect(await cancelled('j', 'page')).toBe(false);
  expect(await cancelled('l', 'page', { ctrlKey: true, shiftKey: true })).toBe(false);
  expect(await cancelled('l', 'page', {})).toBe(false);
  expect(errors).toEqual([]);
});
