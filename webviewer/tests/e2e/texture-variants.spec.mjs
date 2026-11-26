import { test, expect } from '../fixtures.mjs';
import { cleanOwner, idle, menu, openPage, ownerOf, place, post, shown, slotsOf, stateOf } from '../skins.mjs';

// The Upscale dialog (SPEC-VIEWER 17.5, src/page/features/skins/upscale.ts)
// on an owner, from the instance menu: model and factor; the next New Skin N
// (R-HD-137), whose textures each get a request. Every refusal is the pipeline's (R-VIEW-116,
// 117). The Infestor is this file's owner alone: files run side by side.
// The runner needs no GPU (HDTEX_RUNNER=repeat).

const UNIT = 'Infestor';
const OWNER = `unit:${UNIT}`;
const dialogState = (page) => page.evaluate(() => window.scobaeditor.upscaleDialog());
/** The window for a step that waits on pipeline processes (judge, request, skin): they share the machine with the run. */
const PIPELINE = 30_000;

// A data texture offers only fast: tests/unit/skin-choices.spec.mjs; the route refuses the rest: tests/unit/texture-service-api.spec.mjs.

test('the menu\'s Upscale makes New Skin 1 of the owner; the instance shows it; each texture gets a request', async ({ page, request }) => {
  test.setTimeout(180_000);
  await cleanOwner(request, 'scoba', OWNER);
  const { textures } = await ownerOf(request, 'scoba', OWNER);
  const judged = (await (await post(request, 'judge', 'scoba', { assets: textures })).json()).textures;
  // What 2x gives a texture's model from the original; null: it cannot have it.
  const twice = (state, model) => {
    const found = state.asks.find((one) => one.input === 'original')?.models[model];
    return found && !found.reason && found.factors['2']?.reason === '' ? found.factors['2'].size : null;
  };
  const dataCount = judged.filter((state) => !state.colour && !state.reason && twice(state, 'fast') !== null).length;
  const askedCount = judged.filter((state) => !state.reason && twice(state, state.colour ? 'pbrify' : 'fast') !== null).length;
  const errors = await openPage(page);
  const id = await place(page, UNIT);
  await menu(page, id);
  await page.locator('#anim-menu button.skin-upscale').click();
  await expect(page.locator('#upscale-dialog')).toBeVisible();
  await expect.poll(async () => (await dialogState(page)).kind, { timeout: PIPELINE }).toBe('owner');
  // The input is the skin the instance shows; it goes into the next New Skin N, so there is no name box (R-VIEW-117).
  expect((await dialogState(page)).inputs).toEqual(['original']);
  await expect(page.locator('#upscale-dialog input')).toHaveCount(0);
  await expect(page.locator('#upscale-dialog button.upscale-submit')).toHaveText('Upscale Skin');
  await page.selectOption('#upscale-dialog select.upscale-model', 'pbrify');
  await page.selectOption('#upscale-dialog select.upscale-factor', '2');
  const dialog = await dialogState(page);
  const lines = dialog.lines;
  console.log(`owner plan ${JSON.stringify(lines)}`);
  expect(dialog.factors.map((one) => [one.factor, one.label, one.disabled])).toEqual([[2, '2x', false], [4, '4x', false]]);
  expect(lines.some((line) => line === `${dataCount} data textures get fast`)).toBe(dataCount > 0);
  expect(lines.filter((line) => line === `${askedCount} textures get a request`)).toHaveLength(1);
  expect(lines).toContain('Each texture gets 2x its side, at most 4096.');
  expect(lines.at(-1)).toBe('The result goes to a new skin, New Skin 1; rename it at will.');
  expect(dialog.submittable).toBe(askedCount > 0);
  await page.locator('#upscale-dialog button.upscale-submit').click();
  // It closes once New Skin 1 is stored and each texture's request is sent: pipeline steps.
  await expect(page.locator('#upscale-dialog')).toBeHidden({ timeout: PIPELINE });
  await idle(page);
  expect((await shown(page, id)).skin).toBe('New Skin 1');
  // The status line counts what was asked and what was kept.
  await expect(page.locator('#status')).toContainText(new RegExp(`New Skin 1 made \\(${askedCount} requested, ${textures.length - askedCount} kept\\)`));
  // Its variants are still being made: the page follows them (17.4).
  const following = (await page.evaluate((i) => window.scobaeditor.skinChoices(i), id)).following;
  console.log(`after submit: following ${following}, overrides ${(await shown(page, id)).overrides}`);
  const after = await ownerOf(request, 'scoba', OWNER);
  // Negative: New Skin 1 is the only change; nothing is baked.
  expect(after.skins.map((one) => one.name)).toEqual(['New Skin 1']);
  expect(after.bake).toBeNull();
  const skin = after.skins[0];
  // Negative: a skin names no other skin.
  expect(Object.keys(skin).sort()).toEqual(['name', 'textures']);
  const named = Object.entries(skin.textures);
  expect(named.length).toBeGreaterThan(0);
  // Each named variant is made; data textures were asked of fast.
  for (const [asset, variant] of named) {
    const state = judged.find((one) => one.asset === asset);
    const chosen = state.colour ? 'pbrify' : 'fast';
    expect(variant, asset).toBe(`${chosen}@${twice(state, chosen)}`);
    await expect
      .poll(async () => {
        const now = await stateOf(request, 'scoba', asset);
        const open = Object.values(now.requests).find((one) => one.state === 'failed');
        return open ? open.reason : now.variants.some((one) => one.id === variant);
      }, { timeout: 60_000 })
      .toBe(true);
  }
  // The page follows by itself while the variants are made: no reload, no new choice.
  // Each named texture the model has a slot for is shown; the others (effects, decals) change no slot.
  const slots = await slotsOf(page, id);
  const usable = async ([asset, variant]) => {
    const found = (await stateOf(request, 'scoba', asset)).variants.find((one) => one.id === variant);
    return Boolean(found) && !found.stale && (found.problems.length === 0 || Boolean(found.accepted));
  };
  const shownOnes = [];
  for (const entry of named) if (slots.includes(entry[0]) && (await usable(entry))) shownOnes.push(entry[0]);
  // `overrides` counts slots: one asset may fill several.
  const onModel = slots.filter((asset) => shownOnes.includes(asset)).length;
  console.log(`named ${named.length}, on the model ${onModel}, slots ${JSON.stringify(slots)}`);
  expect(onModel).toBeGreaterThan(0);
  try {
    await expect.poll(async () => (await shown(page, id)).overrides, { timeout: 15_000 }).toBe(onModel);
  } catch (error) {
    // What the page holds: its owner (skins, shows) and the states it shows, against the server's.
    const seen = await page.evaluate((i) => window.scobaeditor.skinChoices(i), id);
    console.log(`page owner ${JSON.stringify(seen)}; status ${await page.locator('#status').textContent()}`);
    for (const asset of shownOnes) console.log(`server ${asset}: ${JSON.stringify((await stateOf(request, 'scoba', asset)).variants.map((one) => [one.id, one.stale, one.problems.length]))}`);
    throw error;
  }
  expect((await shown(page, id)).skin).toBe('New Skin 1');
  // Negative: once every variant is made, the page stops reading their states.
  await expect.poll(async () => (await page.evaluate((i) => window.scobaeditor.skinChoices(i), id)).following, { timeout: 5_000 }).toBe(false);
  expect(errors).toEqual([]);
});

test('an owner upscale beside a New Skin 1 makes New Skin 2; New Skin 1 stays as it was', async ({ page, request }) => {
  test.setTimeout(120_000);
  await cleanOwner(request, 'scoba', OWNER);
  const made = await post(request, 'skin', 'scoba', { owner: OWNER, action: 'copy', name: null, from: 'original' });
  expect(made.status(), await made.text()).toBe(200);
  expect((await made.json()).made).toBe('New Skin 1');
  const errors = await openPage(page);
  const id = await place(page, UNIT);
  await menu(page, id);
  await page.locator('#anim-menu button.skin-upscale').click();
  // The dialog opens once the pipeline judged the owner's textures: a pipeline step, so the wider window.
  await expect.poll(async () => (await dialogState(page)).kind, { timeout: PIPELINE }).toBe('owner');
  await page.selectOption('#upscale-dialog select.upscale-model', 'fast');
  expect((await dialogState(page)).lines.at(-1)).toBe('The result goes to a new skin, New Skin 2; rename it at will.');
  await page.locator('#upscale-dialog button.upscale-submit').click();
  await expect(page.locator('#upscale-dialog')).toBeHidden({ timeout: PIPELINE });
  await idle(page);
  expect((await shown(page, id)).skin).toBe('New Skin 2');
  const after = await ownerOf(request, 'scoba', OWNER);
  expect(after.skins.map((one) => one.name)).toEqual(['New Skin 1', 'New Skin 2']);
  // Negative: the skin made before is not touched, and no refusal asks to save or discard it.
  expect(after.skins[0].textures).toEqual({});
  expect((await dialogState(page)).error).toBe('');
  expect(errors).toEqual([]);
});
