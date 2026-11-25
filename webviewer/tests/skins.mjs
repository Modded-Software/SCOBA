// The texture service of SC2 (SPEC-VIEWER 17.2), for the tests: states,
// owners, one fast variant per texture, and a clean owner. The tests' store
// is fresh each run, with the runner that needs no GPU (HDTEX_RUNNER=repeat).
import { expect } from './fixtures.mjs';

const query = (dataset, more = {}) => new URLSearchParams({ dataset, ...more });

/** POST one texture route of SC2 in `dataset`. */
export const post = (request, route, dataset, data) => request.post(`/api/sc2/textures/${route}?${query(dataset)}`, { data });

/** The state of one texture. */
export const stateOf = async (request, dataset, asset) => (await (await request.get(`/api/sc2/textures?${query(dataset, { asset })}`)).json()).textures[0];

/** What the server says of one owner. */
export async function ownerOf(request, dataset, owner) {
  const answer = await request.get(`/api/sc2/textures/owner?${query(dataset, { owner })}`);
  expect(answer.status(), await answer.text()).toBe(200);
  const { owner: found } = await answer.json();
  expect(found, `${dataset} holds the owner ${owner}`).not.toBeNull();
  return found;
}

/**
 * The unit's own diffuse texture: `<unit>_diffuse`, with a colour plane, not tiling (the test runner breaks seams).
 * An owner also lists the textures of its effects and decals; a skin of those changes no slot of the model.
 */
export async function colourTexture(request, dataset, owner) {
  const { textures } = await ownerOf(request, dataset, owner);
  const judged = await post(request, 'judge', dataset, { assets: textures });
  expect(judged.status(), await judged.text()).toBe(200);
  const unit = owner.split(':').pop().toLowerCase();
  const found = (await judged.json()).textures.find((state) => state.asset.endsWith(`\\${unit}_diffuse.dds`) && state.colour && !state.tiles && !state.reason);
  expect(found, `${owner}: ${unit}_diffuse.dds among ${textures.join(', ')}`).toBeTruthy();
  return found.asset;
}

/** The assets of an instance's texture slots: what a skin can replace on it. */
export const slotsOf = async (page, id) => (await viewState(page)).items.find((i) => i.id === id).textureSlots;

/** The largest size the pipeline lets `model` make from `input`, read from the judge answer. */
export async function largestSize(request, dataset, asset, model = 'fast', input = 'original') {
  const judged = await post(request, 'judge', dataset, { assets: [asset] });
  expect(judged.status(), await judged.text()).toBe(200);
  const sizes = (await judged.json()).textures[0].asks.find((one) => one.input === input).models[model].sizes;
  return Math.max(...Object.entries(sizes).filter(([, why]) => why === '').map(([at]) => Number(at)));
}

/** The texture's `model` variant from the original at its largest size, made once per run: { state, variant, size }. */
export async function madeVariant(request, dataset, asset, model = 'fast') {
  const size = await largestSize(request, dataset, asset, model);
  const variant = `${model}@${size}`;
  let state = await stateOf(request, dataset, asset);
  if (!state.variants.some((one) => one.id === variant) && !state.requests[model]) {
    const asked = await post(request, 'request', dataset, { asset, input: 'original', model, size });
    expect(asked.status(), await asked.text()).toBe(200);
  }
  await expect
    .poll(async () => {
      state = await stateOf(request, dataset, asset);
      const open = state.requests[model];
      return open && open.state === 'failed' ? open.reason : state.variants.some((one) => one.id === variant);
    }, { timeout: 60_000 })
    .toBe(true);
  return { state, variant, size };
}

/** The owner as a fresh store has it: no bake, no stored skin. No test depends on what another left. */
export async function cleanOwner(request, dataset, owner) {
  const now = await ownerOf(request, dataset, owner);
  if (now.bake) {
    const unbaked = await post(request, 'unbake', dataset, { owner });
    expect(unbaked.status(), await unbaked.text()).toBe(200);
  }
  // An offered New Skin is not stored: nothing to delete (R-HD-137).
  for (const skin of now.skins.filter((one) => one.stored)) {
    const gone = await post(request, 'skin', dataset, { owner, action: 'delete', name: skin.name });
    expect(gone.status(), await gone.text()).toBe(200);
  }
  return ownerOf(request, dataset, owner);
}

/** A skin `name` of `owner`, copied from Original, naming `textures` (asset to variant id). */
export async function makeSkin(request, dataset, owner, name, textures) {
  const made = await post(request, 'skin', dataset, { owner, action: 'copy', name, from: 'original' });
  expect(made.status(), await made.text()).toBe(200);
  for (const [asset, variant] of Object.entries(textures)) {
    const set = await post(request, 'skin', dataset, { owner, action: 'set', name, asset, variant });
    expect(set.status(), await set.text()).toBe(200);
  }
  return ownerOf(request, dataset, owner);
}

/** Open the page; console errors and page errors are collected. */
export async function openPage(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  return errors;
}

export const idle = (page) => page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
export const viewState = (page) => page.evaluate(() => window.sc2viewer.state());

/** What an instance shows: its skin, the overrides in place, its largest texture, the blue glow. */
export async function shown(page, id) {
  const found = (await viewState(page)).items.find((i) => i.id === id);
  return { skin: found.skin, overrides: found.overrides, largest: found.largestTexture, blue: found.blueGlow };
}

export const skinChoices = (page, id) => page.evaluate((i) => window.sc2viewer.skinChoices(i), id);
/** The open skin dialog (id, title, text, buttons); null: none is open. */
export const skinDialog = (page) => page.evaluate(() => window.sc2viewer.skinDialog());
/** The saved skins of an owner as the server stores them: name, textures. */
export const storedSkins = (owner) => owner.skins.filter((one) => one.stored).map(({ name, textures }) => ({ name, textures }));

/** Open the menu's skin list and click the row of `skin` (its pick, or its icon `edit` / `trash`). */
export async function pickRow(page, skin, part = 'pick') {
  await expect(page.locator('#anim-menu button.skin-choice'), 'the instance menu is open').toBeVisible();
  if (await page.locator('#anim-menu ul.skin-list').isHidden()) await page.locator('#anim-menu button.skin-choice').click();
  await page.locator(`#anim-menu ul.skin-list li[data-skin="${skin}"] button.skin-${part}`).click();
}
export async function setSkin(page, id, skin) {
  await page.evaluate(([i, s]) => window.sc2viewer.setSkin(i, s), [id, skin]);
  await idle(page);
}

/** A unit standing still, the grid off, seen from the side. */
export async function place(page, unit, options = {}) {
  const id = await page.evaluate(([u, o]) => window.sc2viewer.addUnit(u, { x: 0, y: 0, pick: 0.5, sequence: -1, ...o }), [unit, options]);
  await idle(page);
  await page.evaluate(() => {
    window.sc2viewer.setGrid(false);
    window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: 0.5, distance: 6, target: [0, 0, 0.5] });
  });
  return id;
}

/** Open the instance's menu by a right click on one of its pixels. */
export async function menu(page, id) {
  const at = await page.evaluate((i) => window.sc2viewer.itemPixel(i), id);
  expect(at, `a pixel of instance ${id} in the view`).toBeTruthy();
  await page.mouse.click(at[0], at[1], { button: 'right' });
  await expect(page.locator('#anim-menu')).toBeVisible();
}
