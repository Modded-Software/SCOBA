// Upscaling a StarCraft: Ghost texture (R-HD-150 to R-HD-153, R-VIEW-152):
// a request of one texture, then an Upscale Skin of an owner, shown on one
// instance. The test store's upscaler needs no GPU
// (HDTEX_RUNNER=repeat). Engine state decides: the service's states and
// owners, and the instance's overrides. How it looks is an operator check.
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '../fixtures.mjs';
import { add, addRecord, CRATE, CRATE_OWNER, CRATE_TEXTURE, DATASET, itemOf, open, ownerLookup, probe, textureBody, texturePost } from '../ghost.mjs';

const MODEL = 'fast';
/** The skin an upscale without a name makes of an owner with no skin (R-HD-137). */
const NEW1 = 'New Skin 1';
/**
 * A sign whose one texture gets a stand-in variant with no problem (found by a
 * request of 40 textures of the build, 2026-11-25): the stand-in repeats
 * pixels, and across the wrap-around edge most Ghost textures miss the seam
 * limit; every Ghost texture is taken to tile (SPEC-HD-TEXTURES 6.2).
 */
const SIGN = '3D/Models/BorgoWelcomeSign.nod';
const SIGN_OWNER = 'model:3d\\models\\borgowelcomesign.nod';
const SIGN_TEXTURE = '3d\\materials\\borgowelcome.dds';

const idle = (page) => page.waitForFunction(() => window.scobaeditor.idle(), null, { timeout: 15_000 });

/** A texture judged: what `fast` may have from the original, its largest factor and the side it gives. */
async function largest(request, asset = CRATE_TEXTURE) {
  const judged = await texturePost(request, 'judge', { assets: [asset] });
  expect(judged.status(), await judged.text()).toBe(200);
  const [state] = (await judged.json()).textures;
  expect(state).toMatchObject({ asset, judged: true, reason: '' });
  const factors = state.asks.find((one) => one.input === 'original').models[MODEL].factors;
  const [factor, { size }] = Object.entries(factors).filter(([, one]) => one.reason === '').sort(([a], [b]) => Number(b) - Number(a))[0];
  return { state, factor: Number(factor), size };
}

/** Wait until the texture holds `variant`; a failed request ends the wait with its reason. */
async function made(request, variant, asset = CRATE_TEXTURE) {
  await expect
    .poll(async () => {
      const [state] = (await textureBody(request, asset)).textures;
      const open = state.requests[MODEL];
      return open && open.state === 'failed' ? open.reason : state.variants.some((one) => one.id === variant);
    }, { timeout: 60_000 })
    .toBe(true);
}

/** An owner with no skin: nothing another test left. */
async function clean(request, owner) {
  const found = await ownerLookup(request, owner);
  expect(found, `${DATASET} holds ${owner}`).not.toBeNull();
  for (const skin of found.skins) {
    const gone = await texturePost(request, 'skin', { owner, action: 'delete', name: skin.name });
    expect(gone.status(), await gone.text()).toBe(200);
  }
}

test('a Ghost texture is upscaled at a factor of its side; a size no factor gives is refused with the reason', async ({ request }) => {
  test.setTimeout(90_000);
  const { state, factor, size } = await largest(request);
  // A diffuse texture of the build (R-HD-151, R-HD-153).
  expect(state.users).toContain('3d\\models\\crate.nod');
  // Negative: a size past the largest side is refused, with the reason, and starts nothing.
  const refused = await texturePost(request, 'request', { asset: CRATE_TEXTURE, input: 'original', model: MODEL, size: 8192 });
  expect(refused.status()).toBe(400);
  expect((await refused.json()).error).toContain('8192 is no size a factor of fast gives now');
  const [before] = (await textureBody(request, CRATE_TEXTURE)).textures;
  expect(before.variants.some((one) => one.id === `${MODEL}@8192`)).toBe(false);
  const asked = await texturePost(request, 'request', { asset: CRATE_TEXTURE, input: 'original', model: MODEL, factor });
  expect(asked.status(), await asked.text()).toBe(200);
  await made(request, `${MODEL}@${size}`);
  const [after] = (await textureBody(request, CRATE_TEXTURE)).textures;
  const variant = after.variants.find((one) => one.id === `${MODEL}@${size}`);
  // The variant keeps its original's format and is served (R-HD-153).
  expect(variant).toMatchObject({ stale: false });
  const file = await request.get(`/api/ghost/textures/file?${new URLSearchParams({ dataset: DATASET, asset: CRATE_TEXTURE, variant: variant.id, v: variant.sha256 })}`);
  expect(file.status()).toBe(200);
  const bytes = await file.body();
  expect(bytes.subarray(0, 4).toString('latin1')).toBe('DDS ');
  expect(bytes.subarray(84, 88).toString('latin1')).toBe('DXT1');
  expect([bytes.readUInt32LE(12), bytes.readUInt32LE(16)]).toEqual([size, size]);
});

/** Upscale Skin of an owner: New Skin 1, one request per texture. The variant ids it named, by asset. */
async function upscaleSkin(request, owner, asset) {
  await clean(request, owner);
  const { factor, size } = await largest(request, asset);
  const answer = await texturePost(request, 'skin', { owner, action: 'upscale', name: null, from: 'original', model: MODEL, factor });
  expect(answer.status(), await answer.text()).toBe(200);
  const { upscaled, made: madeSkin } = await answer.json();
  expect(madeSkin).toBe(NEW1);
  expect(upscaled.failed).toEqual([]);
  // Asked for, unless an earlier test of this worker made the variant already.
  const now = await textureBody(request, asset);
  const had = now.textures[0].variants.some((one) => one.id === `${MODEL}@${size}`);
  expect(had || upscaled.requests[asset] === `${MODEL}@${size}`, JSON.stringify(upscaled)).toBe(true);
  await made(request, `${MODEL}@${size}`, asset);
  expect((await ownerLookup(request, owner)).skins.find((one) => one.name === NEW1).textures).toEqual({ [asset]: `${MODEL}@${size}` });
  return size;
}

const textureFrame = (page) => page.frames().find((frame) => frame.url().includes('/texture-viewer.html'));

test('Upscale Texture from the texture window\'s tile: the window shows the request, then its variant', async ({ page, request }) => {
  test.setTimeout(120_000);
  await clean(request, CRATE_OWNER);
  const { factor, size } = await largest(request);
  const variant = `${MODEL}@${size}`;
  // Not made before: an earlier test of this worker may have made it.
  const [had] = (await textureBody(request, CRATE_TEXTURE)).textures;
  for (const one of had.variants.filter((v) => v.recipe === MODEL)) {
    const gone = await texturePost(request, 'remove', { asset: CRATE_TEXTURE, variant: one.id });
    expect(gone.status(), await gone.text()).toBe(200);
  }
  const errors = await open(page);
  const id = await add(page, CRATE);
  await idle(page);
  const at = await page.evaluate((i) => window.scobaeditor.itemPixel(i), id);
  await page.mouse.dblclick(at[0], at[1]);
  await expect.poll(async () => (await page.evaluate(() => window.scobaeditor.textureWindow())).originals, { timeout: 30_000 }).toBe('done');
  const before = await textureFrame(page).evaluate(() => window.hdtex.entries().find((e) => e.asset)?.variants ?? null);
  console.log(`window before: ${JSON.stringify(before)}`);
  expect(before).not.toBeNull();
  await textureFrame(page).locator('#cards .skin-tile.upscale').click();
  await expect.poll(async () => (await page.evaluate(() => window.scobaeditor.upscaleDialog())).kind, { timeout: 30_000 }).toBe('texture');
  await page.selectOption('#upscale-dialog select.upscale-model', MODEL);
  await page.selectOption('#upscale-dialog select.upscale-factor', String(factor));
  await page.locator('#upscale-dialog button.upscale-submit').click();
  await expect(page.locator('#upscale-dialog')).toBeHidden({ timeout: 30_000 });
  // The window reads the states again: its tile shows the request while it runs, then the variant.
  const seen = [];
  await expect
    .poll(async () => {
      const now = await textureFrame(page).evaluate(() => ({ variants: window.hdtex.entries().find((e) => e.asset)?.variants ?? [], polling: window.hdtex.state().polling, requests: window.hdtex.textures().map((t) => Object.keys(t.requests)) }));
      seen.push(JSON.stringify(now));
      return now.variants.includes(variant);
    }, { timeout: 60_000 })
    .toBe(true);
  console.log(`window after: ${seen.slice(0, 3).join(' | ')} … ${seen.at(-1)}`);
  expect(errors).toEqual([]);
  await clean(request, CRATE_OWNER);
});

test.describe('a view wider than the texture window', () => {
// The window is 1100 wide, from the right of the gallery: the instance in the middle of a 3400 wide view stays clear of it, for the right click (2800 wide: pixel 1400, window to 1436).
test.use({ viewport: { width: 3400, height: 900 } });
test('Upscale Skin from the menu with the texture window open on the owner: the window shows the request or its variant, with no reload', async ({ page, request, worker }) => {
  test.setTimeout(120_000);
  await clean(request, SIGN_OWNER);
  const { factor, size } = await largest(request, SIGN_TEXTURE);
  const variant = `${MODEL}@${size}`;
  const [had] = (await textureBody(request, SIGN_TEXTURE)).textures;
  for (const one of had.variants.filter((v) => v.recipe === MODEL)) {
    const gone = await texturePost(request, 'remove', { asset: SIGN_TEXTURE, variant: one.id });
    expect(gone.status(), await gone.text()).toBe(200);
  }
  const errors = await open(page);
  const id = await add(page, SIGN);
  await idle(page);
  const at = await page.evaluate((i) => window.scobaeditor.itemPixel(i), id);
  await page.mouse.dblclick(at[0], at[1]);
  await expect.poll(async () => (await page.evaluate(() => window.scobaeditor.textureWindow())).originals, { timeout: 30_000 }).toBe('done');
  const windowNow = () => textureFrame(page).evaluate((asset) => {
    const state = window.hdtex.textures().find((t) => t.asset === asset);
    return { variants: state?.variants.map((v) => v.id) ?? [], requests: Object.values(state?.requests ?? {}).map((r) => `${r.variant}:${r.state}`), polling: window.hdtex.state().polling, tiles: window.hdtex.state().tiles.map((t) => `${t.kind}:${t.variant}`) };
  }, SIGN_TEXTURE);
  const before = await windowNow();
  console.log(`window before: ${JSON.stringify(before)}`);
  expect(before.variants).not.toContain(variant);
  // The menu's Upscale on the instance: the whole owner (R-VIEW-117). The pixel is clear of the window.
  const box = await page.locator('#texture-window').boundingBox();
  expect(at[0] > box.x + box.width || at[1] > box.y + box.height, `instance pixel ${at} beside the window ${JSON.stringify(box)}`).toBe(true);
  await page.mouse.click(at[0], at[1], { button: 'right' });
  await expect(page.locator('#anim-menu')).toBeVisible();
  await page.locator('#anim-menu button.skin-upscale').click();
  await expect.poll(async () => (await page.evaluate(() => window.scobaeditor.upscaleDialog())).kind, { timeout: 30_000 }).toBe('owner');
  await page.selectOption('#upscale-dialog select.upscale-model', MODEL);
  await page.selectOption('#upscale-dialog select.upscale-factor', String(factor));
  await page.locator('#upscale-dialog button.upscale-submit').click();
  await expect(page.locator('#upscale-dialog')).toBeHidden({ timeout: 30_000 });
  // Raw: what the window held at each read, so a failure shows what the page did.
  const seen = [];
  await expect
    .poll(async () => {
      const now = await windowNow();
      seen.push(JSON.stringify(now));
      return now.variants.includes(variant) && now.tiles.includes(`variant:${variant}`);
    }, { timeout: 60_000 })
    .toBe(true);
  console.log(`window after: ${seen.join(' | ')}`);
  // Negative: the window did not load anew; it is the same page, refreshed in place.
  expect((await page.evaluate(() => window.scobaeditor.textureWindow())).originals).toBe('done');
  // The request's launch output went to this worker's own folder, not the operator's (TEXTURE_LOGS).
  expect(existsSync(join(worker.root, 'server-texture-logs', 'ghost', 'requests.out'))).toBe(true);
  expect(errors).toEqual([]);
  await clean(request, SIGN_OWNER);
});
});

const setSkin = async (page, id, skin) => {
  await page.evaluate(([i, s]) => window.scobaeditor.setSkin(i, s), [id, skin]);
  await idle(page);
};

test('Upscale Skin on the sign makes New Skin 1; the instance that shows it holds an override per group of the texture; another instance does not change', async ({ page, request }) => {
  test.setTimeout(120_000);
  const size = await upscaleSkin(request, SIGN_OWNER, SIGN_TEXTURE);
  const errors = await open(page);
  const sign = await add(page, SIGN);
  const second = await add(page, SIGN, 6);
  const crate = await add(page, CRATE, 12);
  await idle(page);
  expect((await page.evaluate((i) => window.scobaeditor.skinChoices(i), sign)).choices).toEqual(['original', NEW1]);
  const groups = (await probe(page, 'groups', sign)).filter((g) => g.kind !== null && g.triangles > 0 && g.texture?.toLowerCase() === '3d/materials/borgowelcome.dds');
  expect(groups.length).toBeGreaterThan(0);
  await setSkin(page, sign, NEW1);
  const shown = await itemOf(page, sign);
  expect({ skin: shown.skin, overrides: shown.overrides, largest: shown.largestTexture }).toEqual({ skin: NEW1, overrides: groups.length, largest: size });
  // Negative: the other instance of the sign keeps Original; the crate is not touched.
  expect(await itemOf(page, second)).toMatchObject({ skin: 'original', overrides: 0 });
  expect(await itemOf(page, crate)).toMatchObject({ skin: 'original', overrides: 0 });
  // Back to Original: no override is left.
  await setSkin(page, sign, 'original');
  expect(await itemOf(page, sign)).toMatchObject({ skin: 'original', overrides: 0 });
  expect(errors).toEqual([]);
  await clean(request, SIGN_OWNER);
});

test('the window on an instance that shows New Skin 1: the picks are changes against it, so the bar and Save to Skin count the same', async ({ page, request }) => {
  test.setTimeout(120_000);
  const size = await upscaleSkin(request, SIGN_OWNER, SIGN_TEXTURE);
  const variant = `${MODEL}@${size}`;
  const errors = await open(page);
  const sign = await add(page, SIGN);
  await idle(page);
  // The window opens on the sign while it shows Original; then the sign shows New Skin 1: the window follows (skin-set).
  const at = await page.evaluate((i) => window.scobaeditor.itemPixel(i), sign);
  expect(at, 'a pixel of the sign').toBeTruthy();
  await page.mouse.dblclick(at[0], at[1]);
  await expect.poll(async () => (await page.evaluate(() => window.scobaeditor.textureWindow())).originals, { timeout: 30_000 }).toBe('done');
  const frame = textureFrame(page);
  expect(await frame.evaluate(() => window.hdtex.state().skin)).toBe('original');
  await setSkin(page, sign, NEW1);
  await expect(page.locator('#texture-window')).toContainText('textures · BorgoWelcomeSign.nod · New Skin 1');
  const pageState = () => frame.evaluate(() => {
    const s = window.hdtex.state();
    return { skin: s.skin, picks: s.picks, draft: s.draft.shown, highlighted: s.tiles.filter((t) => t.highlighted).map((t) => `${t.kind}:${t.variant}`) };
  });
  // Nothing picked yet: the variant New Skin 1 names is the one marked, and the bar is hidden (Ghost bakes nothing: In game is Original).
  await expect.poll(pageState, { timeout: 10_000 }).toEqual({ skin: NEW1, picks: {}, draft: false, highlighted: [`variant:${variant}`] });
  // Negative: a click on the variant New Skin 1 names is no change.
  await frame.locator(`#cards .skin-tile[data-variant="${variant}"]`).click();
  expect(await pageState()).toMatchObject({ picks: {}, draft: false });
  // A click on Original is one change, in the bar and in the dialog alike.
  await frame.locator('#cards .skin-tile.original').click();
  expect(await pageState()).toMatchObject({ picks: { [SIGN_TEXTURE]: 'original' }, draft: true });
  await frame.locator('#draft button.skin-draft-save').click();
  await expect.poll(async () => (await page.evaluate(() => window.scobaeditor.skinDialog()))?.id ?? null, { timeout: 10_000 }).not.toBeNull();
  const dialog = await page.evaluate(() => window.scobaeditor.skinDialog());
  console.log(`save dialog: ${JSON.stringify(dialog)}`);
  expect(dialog.into).toEqual({ kind: 'existing', skin: NEW1 });
  expect(dialog.text).toContain('1 of 1 textures change in New Skin 1.');
  // Its Save button is enabled: no answer of the dialog is disabled.
  await expect(page.locator(`#${dialog.id} .answers button[disabled]`)).toHaveCount(0);
  await page.keyboard.press('Escape');
  expect(errors).toEqual([]);
  await clean(request, SIGN_OWNER);
});

test('the trash: only the variant picked now is kept; one New Skin 1 names is deleted, and New Skin 1 names the original for it', async ({ page, request }) => {
  test.setTimeout(120_000);
  const size = await upscaleSkin(request, SIGN_OWNER, SIGN_TEXTURE);
  const variant = `${MODEL}@${size}`;
  const errors = await open(page);
  const sign = await add(page, SIGN);
  await idle(page);
  const at = await page.evaluate((i) => window.scobaeditor.itemPixel(i), sign);
  expect(at, 'a pixel of the sign').toBeTruthy();
  await page.mouse.dblclick(at[0], at[1]);
  await expect.poll(async () => (await page.evaluate(() => window.scobaeditor.textureWindow())).originals, { timeout: 30_000 }).toBe('done');
  const frame = textureFrame(page);
  await setSkin(page, sign, NEW1);
  await expect(page.locator('#texture-window')).toContainText('textures · BorgoWelcomeSign.nod · New Skin 1');
  const trashOf = () => frame.evaluate((v) => window.hdtex.state().tiles.find((t) => t.kind === 'variant' && t.variant === v)?.trash ?? null, variant);
  // Negative: picked now (New Skin 1 names it and nothing else is picked), its trash is disabled.
  await frame.locator(`#cards .skin-tile[data-variant="${variant}"]`).click();
  await expect.poll(() => frame.evaluate(() => window.hdtex.state().picks), { timeout: 10_000 }).toEqual({});
  expect(await trashOf()).toEqual({ disabled: 'it is picked now; pick another tile first' });
  // Original picked: New Skin 1 still names it, and its trash is enabled.
  await frame.locator('#cards .skin-tile.original').click();
  await expect.poll(trashOf, { timeout: 10_000 }).toEqual({ disabled: '' });
  await frame.locator(`#cards .skin-tile[data-variant="${variant}"] .tile-trash`).click();
  const dialog = page.locator('#variant-delete-dialog');
  await expect(dialog).toContainText('A skin that names it uses the original for this texture from then on.');
  await dialog.locator('.answers button', { hasText: 'Delete Variant' }).click();
  // The variant is gone from the store, and New Skin 1 names the original for the sign's texture.
  await expect.poll(async () => (await textureBody(request, SIGN_TEXTURE)).textures[0].variants.map((one) => one.id), { timeout: 30_000 }).not.toContain(variant);
  const named = (await ownerLookup(request, SIGN_OWNER)).skins.find((one) => one.name === NEW1)?.textures ?? {};
  expect(named[SIGN_TEXTURE] ?? 'original').toBe('original');
  // The instance shows no override of it.
  await expect.poll(async () => (await itemOf(page, sign)).overrides, { timeout: 10_000 }).toBe(0);
  expect(errors).toEqual([]);
  await clean(request, SIGN_OWNER);
});

const statusLog = (page) => page.evaluate(() => window.SCOBAEdit.statusLog().shown);

/**
 * New Skin 1 of an owner, made by a person: it names the texture's largest `fast` variant, whatever its numbers
 * (R-HD-90: a problem hides nothing, and a skin may name it). An Upscale Skin leaves no such variant in its skin
 * (R-HD-162), so the skin is copied and set.
 */
async function namedByHand(request, owner, asset) {
  await clean(request, owner);
  const { factor, size } = await largest(request, asset);
  const variant = `${MODEL}@${size}`;
  const [had] = (await textureBody(request, asset)).textures;
  if (!had.variants.some((one) => one.id === variant)) {
    const asked = await texturePost(request, 'request', { asset, input: 'original', model: MODEL, factor });
    expect(asked.status(), await asked.text()).toBe(200);
  }
  await made(request, variant, asset);
  const copied = await texturePost(request, 'skin', { owner, action: 'copy', name: null, from: 'original' });
  expect(copied.status(), await copied.text()).toBe(200);
  expect((await copied.json()).made).toBe(NEW1);
  const set = await texturePost(request, 'skin', { owner, action: 'set', name: NEW1, asset, variant });
  expect(set.status(), await set.text()).toBe(200);
  return { factor, size };
}

test('negative: a variant of the skin with a problem not accepted is not shown: its slot keeps the original, said once; no error', async ({ page, request }) => {
  test.setTimeout(120_000);
  // The stand-in repeats pixels: across the crate's wrap-around edge its variant misses the seam limit (R-HD-91).
  const { factor, size } = await namedByHand(request, CRATE_OWNER, CRATE_TEXTURE);
  // An Upscale Skin does not name it (R-HD-162): the crate has this one texture, so the upscale asks for nothing
  // and is refused with the problem. No second skin is made.
  const upscale = await texturePost(request, 'skin', { owner: CRATE_OWNER, action: 'upscale', name: null, from: 'original', model: MODEL, factor });
  expect(upscale.status(), await upscale.text()).toBe(400);
  expect((await upscale.json()).error).toContain(`asks for no texture, so no skin is made (${CRATE_TEXTURE}: ${MODEL}@${size} has problems: seam `);
  expect((await ownerLookup(request, CRATE_OWNER)).skins.map((one) => one.name)).toEqual([NEW1]);
  const [state] = (await textureBody(request, CRATE_TEXTURE)).textures;
  const variant = state.variants.find((one) => one.id === `${MODEL}@${size}`);
  expect(variant.problems.map((one) => one.limit)).toEqual(['seam']);
  expect(variant.accepted).toBe('');
  const errors = await open(page);
  const crate = await add(page, CRATE);
  await idle(page);
  const failed = await page.evaluate(([i, s]) => window.scobaeditor.setSkin(i, s).then(() => '', (error) => String(error.message ?? error)), [crate, NEW1]);
  await idle(page);
  // No refusal and no thrown error: the skin is shown; the one texture it names keeps the original, with why.
  expect(failed).toBe('');
  const seam = variant.problems[0];
  const reason = `its upscale failed the seam check (${Number(seam.value.toFixed(2))}, limit ${Number(seam.bound.toFixed(2))}): its edges would show as lines where it repeats`;
  expect(await itemOf(page, crate)).toMatchObject({ skin: NEW1, overrides: 0, unshown: [`${CRATE_TEXTURE}: ${MODEL}@${size}: ${reason}`] });
  // The status line says it in plain words: the file, that it keeps its original, and why.
  const why = `New Skin 1: chestcrate2.dds keeps its original texture. I${reason.slice(1)}.`;
  // The toast shows each message in turn: wait until it has been put up.
  await expect.poll(async () => (await statusLog(page)).filter((line) => line.includes(why)).length, { timeout: 10_000 }).toBe(1);
  // Negative: applied again (a change of the dataset's textures), it is not said a second time.
  await page.evaluate(([i, s]) => window.scobaeditor.setSkin(i, s), [crate, NEW1]);
  await idle(page);
  expect((await statusLog(page)).filter((line) => line.includes(why))).toHaveLength(1);
  expect(errors).toEqual([]);
  await clean(request, CRATE_OWNER);
});

/** The coarse limit (scripts/hdtex/core/limits.py MAX_COARSE_RMSE). */
const COARSE_LIMIT = 1.5;

test('Upscale Skin of Nova: her textures do not tile, so no seam check; each variant shows; one with a problem keeps its original; nothing is thrown', async ({ page, request, worker }) => {
  test.setTimeout(180_000);
  const owner = 'actor:Nova';
  await clean(request, owner);
  const answer = await texturePost(request, 'skin', { owner, action: 'upscale', name: null, from: 'original', model: MODEL, factor: 2 });
  expect(answer.status(), await answer.text()).toBe(200);
  const { upscaled } = await answer.json();
  expect(upscaled.failed).toEqual([]);
  const named = (await ownerLookup(request, owner)).skins.find((one) => one.name === NEW1).textures;
  for (const [asset, id] of Object.entries(named)) await made(request, id, asset);
  // Nova's own textures do not repeat (no triangle of hers spans a whole-number u or v): no seam check binds them.
  const own = Object.keys(named).filter((asset) => asset.startsWith('3d\\materials\\'));
  expect(own.length).toBeGreaterThan(0);
  const usable = {};
  const tiles = {};
  for (const [asset, id] of Object.entries(named)) {
    const [state] = (await textureBody(request, asset)).textures;
    const found = state.variants.find((one) => one.id === id);
    tiles[asset] = state.tiles;
    usable[asset] = !found.stale && (found.problems.length === 0 || Boolean(found.accepted));
    // Negative: a texture that does not repeat never misses the seam limit.
    if (!state.tiles) expect(found.problems.map((one) => one.limit), asset).not.toContain('seam');
  }
  console.log(`nova textures tile: ${JSON.stringify(tiles)}; usable: ${JSON.stringify(usable)}`);
  for (const asset of own) expect(tiles[asset], asset).toBe(false);
  // A person refuses one, by hand, in this worker's own store: it misses a limit and is not accepted. Its slot keeps the original.
  const refused = '3d\\materials\\novaface04.dds';
  const folder = join(worker.store, 'ghost', 'variants');
  const [dir] = readdirSync(folder).filter((one) => one.startsWith('novaface04.dds-'));
  const entryFile = join(folder, dir, MODEL, 'entry.json');
  const entry = JSON.parse(readFileSync(entryFile, 'utf8'));
  writeFileSync(entryFile, JSON.stringify({ ...entry, numbers: { ...entry.numbers, coarse_rmse: 99 } }));
  const judged = await texturePost(request, 'judge', { assets: [refused] });
  expect(judged.status(), await judged.text()).toBe(200);
  usable[refused] = false;
  const good = Object.keys(usable).filter((asset) => usable[asset]);
  const bad = Object.keys(usable).filter((asset) => !usable[asset]);
  expect(bad, JSON.stringify(usable)).toEqual([refused]);
  const errors = await open(page);
  const nova = await addRecord(page, 'actors', 'Nova');
  await idle(page);
  await setSkin(page, nova, NEW1);
  const shown = await itemOf(page, nova);
  // The slots of the usable textures hold an override; each of the others is named in unshown, and keeps the original.
  const slots = shown.textureSlots;
  const overridden = slots.filter((asset) => good.includes(asset)).length;
  expect({ skin: shown.skin, overrides: shown.overrides, unshown: [...shown.unshown].sort() }).toEqual({
    skin: NEW1,
    overrides: overridden,
    unshown: [`${refused}: ${named[refused]}: its upscale failed the coarse_rmse check (99, limit ${COARSE_LIMIT}): from far away its brightness or colour would be wrong`],
  });
  expect(overridden).toBeGreaterThan(0);
  expect(errors).toEqual([]);
  await clean(request, owner);
});
