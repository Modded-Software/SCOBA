import { test, expect } from '../fixtures.mjs';
import { openTextures } from '../edits.mjs';
import { open } from '../page.mjs';
import { cleanOwner, colourTexture, madeVariant, makeSkin, ownerOf, post, stateOf } from '../skins.mjs';

// Shared textures in the texture window (SPEC-VIEWER 17.3, R-VIEW-160,
// R-VIEW-161): the users badge on a row's thumbnail, amber when another owner
// bakes a variant of the texture, and the "named by" row of the details. The
// state says who reads and who names a texture (R-HD-156); the page only
// shows it. The Corruptor is this file's unit alone: files run side by side.
// How the badge looks is an operator check; its text, title and class are read.

const UNIT = 'Corruptor';
const OWNER = `unit:${UNIT}`;

const entriesOf = (frame) => frame.evaluate(() => window.hdtex.entries());
const badgeOf = async (frame, asset) => (await entriesOf(frame)).find((entry) => entry.asset === asset).usersBadge;
/** The badge of a row as the page drew it: its text, title and whether it is amber; null: the row has none. */
const drawnBadge = (frame, index) =>
  frame.locator('#list .row').nth(index).evaluate((row) => {
    const badge = row.querySelector('.users-badge');
    return badge && { text: badge.textContent, title: badge.title, amber: badge.classList.contains('shared-bake') };
  });
const namedRows = (frame) => frame.locator('.details dd.named-by div').allTextContents();
/**
 * What the Delete Variant dialog says of other owners (R-VIEW-162), read with the dialog open on a variant's trash;
 * then Cancel. Nothing is deleted.
 */
async function deleteWarning(page, frame, variant) {
  await frame.locator(`#cards .skin-tile[data-variant="${variant}"] .tile-trash`).click();
  const dialog = page.locator('#variant-delete-dialog');
  await expect(dialog).toBeVisible();
  await expect(dialog.locator('.variant-named-head')).not.toHaveText('');
  const said = { head: await dialog.locator('.variant-named-head').textContent(), lines: await dialog.locator('.variant-named li').allTextContents(), yesDisabled: await dialog.locator('#variant-delete-yes').isDisabled() };
  await dialog.locator('#variant-delete-no').click();
  await expect(dialog).toBeHidden();
  return said;
}

test('a texture several model files read has the users badge; baked by another owner it is amber and "named by" lists that owner', async ({ page, request }) => {
  test.setTimeout(240_000);
  await cleanOwner(request, 'scoba', OWNER);
  const asset = await colourTexture(request, 'scoba', OWNER);
  const { users } = await stateOf(request, 'scoba', asset);
  expect(users.length, `${asset} is read by several model files: ${users}`).toBeGreaterThan(1);
  // Another owner of the same texture: one of the model files that read it.
  const other = `model:${users[0]}`;
  await cleanOwner(request, 'scoba', other);

  const errors = await open(page);
  const frame = await openTextures(page, UNIT, asset);
  const index = (await entriesOf(frame)).findIndex((entry) => entry.asset === asset);
  // The badge counts the model files; its title names them. Nobody bakes it: not amber, and no "named by" row.
  const title = `read by ${users.length} model files\n${users.join('\n')}`;
  expect(await badgeOf(frame, asset)).toEqual({ count: users.length, title, sharedBake: false });
  expect(await drawnBadge(frame, index)).toEqual({ text: String(users.length), title, amber: false });
  expect((await frame.evaluate(() => window.hdtex.state())).namedBy).toEqual([]);
  await expect(frame.locator('.details dd.named-by')).toHaveCount(0);
  // Every row follows its own state: a badge with the count from 2 model files up, else none. (No texture of this
  // unit is read by one file alone; that a single reader gets no badge is tests/unit/skin-choices.spec.mjs.)
  const before = await frame.evaluate(() => ({ entries: window.hdtex.entries(), textures: window.hdtex.textures() }));
  for (const [at, entry] of before.entries.entries()) {
    const count = before.textures.find((state) => state.asset === entry.asset).users.length;
    expect((await drawnBadge(frame, at))?.text ?? null, entry.asset).toBe(count >= 2 ? String(count) : null);
  }
  // A second texture of the unit, for the negatives below: what happens to one texture changes no other row.
  const untouched = before.entries.find((entry) => entry.asset !== asset);
  const untouchedBadge = untouched.usersBadge;

  // The other owner makes a skin that names a variant: a skin is no bake. Listed under "named by", not amber.
  const { variant } = await madeVariant(request, 'scoba', asset);
  // Negative: nobody names the variant yet: the Delete Variant dialog says so, and lists nobody (R-VIEW-162).
  await frame.evaluate(() => window.hdtex.refresh());
  await expect(frame.locator(`#cards .skin-tile[data-variant="${variant}"] .tile-trash`)).toHaveCount(1, { timeout: 15_000 });
  expect(await deleteWarning(page, frame, variant)).toEqual({ head: 'No other owner names it.', lines: [], yesDisabled: false });
  await makeSkin(request, 'scoba', other, 'shared', { [asset]: variant });
  await frame.evaluate(() => window.hdtex.refresh());
  const skinLine = `${other} · shared · ${variant}`;
  await expect.poll(async () => (await frame.evaluate(() => window.hdtex.state())).namedBy, { timeout: 15_000 }).toEqual([skinLine]);
  expect((await badgeOf(frame, asset)).sharedBake).toBe(false);
  expect(await namedRows(frame)).toEqual([skinLine]);
  // The dialog lists the other owner's skin; it disables nothing.
  expect(await deleteWarning(page, frame, variant)).toEqual({ head: '1 skin or bake of another owner names it:', lines: [`${other} · shared`], yesDisabled: false });

  // It bakes the skin: the badge turns amber and names the owner; "named by" lists the bake first.
  const baked = await post(request, 'bake', 'scoba', { owner: other, skin: 'shared' });
  expect(baked.status(), await baked.text()).toBe(200);
  await frame.evaluate(() => window.hdtex.refresh());
  const amber = `${title}\nbaked by 1 other owner\n${other}`;
  await expect.poll(() => badgeOf(frame, asset), { timeout: 15_000 }).toEqual({ count: users.length, title: amber, sharedBake: true });
  expect(await drawnBadge(frame, index)).toEqual({ text: String(users.length), title: amber, amber: true });
  expect(await namedRows(frame)).toEqual([`${skinLine} · baked`, skinLine]);
  // The dialog lists the bake first, marked; cancelled each time, the variant is still there.
  expect(await deleteWarning(page, frame, variant)).toEqual({ head: '2 skins or bakes of other owners name it:', lines: [`${other} · shared (baked)`, `${other} · shared`], yesDisabled: false });
  expect((await stateOf(request, 'scoba', asset)).variants.map((one) => one.id)).toContain(variant);
  // Negative: another texture's badge is as before, not amber; the unit has no skin and no bake of its own.
  expect(untouchedBadge.sharedBake).toBe(false);
  expect(await badgeOf(frame, untouched.asset)).toEqual(untouchedBadge);
  const mine = await ownerOf(request, 'scoba', OWNER);
  expect([mine.skins, mine.bake]).toEqual([[], null]);

  // Unbaked: the amber is gone; the skin's line stays.
  const unbaked = await post(request, 'unbake', 'scoba', { owner: other });
  expect(unbaked.status(), await unbaked.text()).toBe(200);
  await frame.evaluate(() => window.hdtex.refresh());
  await expect.poll(async () => (await badgeOf(frame, asset)).sharedBake, { timeout: 15_000 }).toBe(false);
  expect(await namedRows(frame)).toEqual([skinLine]);
  expect(errors).toEqual([]);
  await cleanOwner(request, 'scoba', other);
});
