// Ghost in the shared texture window (core/texturewindow.ts, SPEC-VIEWER-GHOST 8):
// the bare texture viewer page (/texture-viewer.html), handed every texture
// file a model's materials name, decoded, with what draws with it. Opened by
// a double-click on an instance, an instance row, or a gallery row (actors
// and models). Needs GHOST_PATH. The window's state, the page's hdtex API and
// measured boxes decide; how it looks is an operator check.
import { allowErrors, test, expect } from '../fixtures.mjs';
import { open, add, frameItem } from '../ghost.mjs';

const win = (page) => page.evaluate(() => window.sc2viewer.textureWindow());
const textureFrame = (page) => page.frames().find((frame) => frame.url().includes('/texture-viewer.html'));

/** The page's own state once it shows `user` and the textures were handed to it. */
async function inside(page, user) {
  await expect
    .poll(async () => {
      const frame = textureFrame(page);
      if (!frame) return 'no frame';
      return frame.evaluate(() => (window.hdtex ? window.hdtex.state().user : 'loading')).catch((error) => error.message);
    })
    .toBe(user);
  await expect.poll(async () => (await win(page)).originals, { timeout: 20_000 }).toBe('done');
  return textureFrame(page).evaluate(() => ({ ...window.hdtex.state(), entries: window.hdtex.entries(), problems: window.hdtex.problems(), textures: window.hdtex.textures() }));
}

/** Boxes of the window, its frame, and the page's list rows and card, in page pixels. */
async function layout(page) {
  const frame = textureFrame(page);
  const [windowBox, frameBox] = [await page.locator('#texture-window').boundingBox(), await page.locator('#texture-frame').boundingBox()];
  const inner = await frame.evaluate(() => ({
    rows: [...document.querySelectorAll('#list .row')].map((r) => r.getBoundingClientRect()).map((b) => ({ top: b.top, bottom: b.bottom, height: b.height })),
    cards: document.getElementById('cards').getBoundingClientRect().toJSON(),
    width: innerWidth,
  }));
  return { windowBox, frameBox, ...inner };
}

/** The layout checks: the frame fills the window body; rows have height and do not overlap. */
function expectSound({ windowBox, frameBox, rows, cards, width }) {
  expect(frameBox.x).toBeGreaterThanOrEqual(windowBox.x - 1);
  expect(frameBox.x + frameBox.width).toBeLessThanOrEqual(windowBox.x + windowBox.width + 1);
  expect(frameBox.height).toBeGreaterThan(windowBox.height * 0.8);
  expect(rows.length).toBeGreaterThan(0);
  for (const row of rows) expect(row.height).toBeGreaterThan(10);
  for (let i = 1; i < rows.length; i++) expect(rows[i].top, `row ${i} starts below row ${i - 1}`).toBeGreaterThanOrEqual(rows[i - 1].bottom - 0.5);
  expect(cards.width).toBeGreaterThan(100);
  expect(cards.right).toBeLessThanOrEqual(width + 1);
}

/** The facts on the page's card of the entry shown now, as "name: value". */
const cardFacts = (page) => textureFrame(page).evaluate(() => [...document.querySelectorAll('#cards dt')].map((dt) => `${dt.textContent}: ${dt.nextElementSibling ? dt.nextElementSibling.textContent : ''}`));

async function closeWindow(page) {
  await page.locator('#texture-window .window-close').click();
  await expect(page.locator('#texture-window')).toBeHidden();
}

test('a double-click on a Ghost instance opens the shared texture window on its textures, with what draws with them', async ({ page }) => {
  const errors = await open(page);
  const id = await add(page, '3D/Models/crate.nod');
  await frameItem(page, id);
  const at = await page.evaluate((i) => window.sc2viewer.itemPixel(i), id);
  await page.mouse.dblclick(at[0], at[1]);
  await expect(page.locator('#texture-window')).toBeVisible();
  await expect(page.locator('#texture-window .window-title')).toContainText('crate.nod');
  const shown = await inside(page, 'crate.nod');
  expect(await win(page)).toMatchObject({ open: true, user: 'crate.nod', file: '3D/Models/crate.nod', dataset: 'build' });
  expect(shown.embed).toBe(true);
  expect(shown.problems).toEqual([]);
  // One texture file: its colour plane first, every entry an original alone.
  const [entry] = shown.entries;
  expect(entry.plane).toBe('color');
  expect(new Set(shown.entries.map((e) => e.texture)).size).toBe(1);
  // Ghost has no texture service: no state names a kind (texview categoryOf, R-VIEW-100).
  for (const e of shown.entries) expect(e.category).toBe('kind not known');
  expect(entry.texture).toMatch(/\.dds$/i);
  expect(entry.facts).toEqual([['material chestCrate2', expect.stringMatching(/^(shader \S+|no shader) · drawn solid · groups 0 · \d+ triangles$/)]]);
  // The entry's picture is the decoded texture at the size listed.
  const size = await textureFrame(page).evaluate(async (src) => {
    const image = new Image();
    image.src = src;
    await image.decode();
    return [image.naturalWidth, image.naturalHeight];
  }, entry.image);
  expect(size).toEqual(entry.size);
  expect(await cardFacts(page)).toContainEqual(expect.stringMatching(/^material chestCrate2: .*drawn solid/));
  expectSound(await layout(page));
  expect(errors).toEqual([]);
});

test('negative: Ghost has no texture service: no state, no request, no skin, no Upscale, no ground texture (R-VIEW-100)', async ({ page }) => {
  const asked = [];
  page.on('request', (r) => {
    if (/\/api\/[^/]+\/textures/.test(new URL(r.url()).pathname)) asked.push(r.url());
  });
  const errors = await open(page);
  const id = await add(page, '3D/Models/crate.nod');
  expect(await page.evaluate((i) => window.sc2viewer.skinChoices(i), id)).toEqual({ owner: null, choices: [], state: null, following: false });
  await page.locator(`#scene li[data-id="${id}"] .head .name`).dblclick();
  const shown = await inside(page, 'crate.nod');
  expect(shown.entries.length).toBeGreaterThan(0);
  for (const e of shown.entries) expect(e.asset, e.id).toBeNull();
  expect(shown.textures).toEqual([]);
  const frame = textureFrame(page);
  await expect(frame.locator('#cards .upscale, #cards select')).toHaveCount(0);
  await expect(frame.locator('#list .badge')).toHaveCount(0);
  // The Ghost tab: no ground texture to choose.
  await page.locator('#game-tabs button[data-game="ghost"]').click();
  await expect(page.locator('#ground-button')).toBeHidden();
  expect(asked).toEqual([]);
  expect(errors).toEqual([]);
});

test('gallery rows open it: an actor of the actors pane and a file of the models pane; the scene stays empty', async ({ page }) => {
  const errors = await open(page);
  await page.locator('#game-tabs button[data-game="ghost"]').click();
  await page.fill('#search-actors', 'zerg_critter');
  await page.locator('#actors li[data-id="zerg_critter"]').dblclick();
  const actor = await inside(page, 'zerg_critter');
  expect((await win(page)).file).toBe('3D/Models/zergling.nod');
  expect(actor.entries.length).toBeGreaterThan(0);
  for (const e of actor.entries) expect(e.facts.length, e.texture).toBeGreaterThan(0);
  expectSound(await layout(page));
  // The models pane: the same file, by its own id.
  await closeWindow(page);
  await page.locator('#tab-models').click();
  await page.fill('#search-models', 'zergling');
  const row = page.locator('#models li[data-id]', { has: page.locator('.name', { hasText: /^zergling(\.nod)?$/i }) }).first();
  await expect(row).toBeVisible();
  const modelId = await row.getAttribute('data-id');
  await row.dblclick();
  const model = await inside(page, modelId);
  expect((await win(page)).file).toBe('3D/Models/zergling.nod');
  expect(model.entries.map((e) => e.texture)).toEqual(actor.entries.map((e) => e.texture));
  // Negative: a double-click adds nothing to the scene.
  expect((await page.evaluate(() => window.sc2viewer.state())).items).toEqual([]);
  expect(errors).toEqual([]);
});

test('an instance row opens it; a cutout texture shows its alpha plane', async ({ page }) => {
  const errors = await open(page);
  const id = await add(page, '3D/Models/AR_Plant_Vine_01.nod');
  await page.locator(`#scene li[data-id="${id}"] .head .name`).dblclick();
  const shown = await inside(page, 'AR_Plant_Vine_01.nod');
  const cut = shown.entries.filter((e) => e.facts.some(([, v]) => v.includes('drawn cutout')));
  expect(cut.length, JSON.stringify(shown.entries.map((e) => [e.texture, e.plane, e.facts]))).toBeGreaterThan(0);
  const planes = shown.entries.filter((e) => e.texture === cut[0].texture).map((e) => e.plane);
  expect(planes).toEqual(['color', 'alpha']);
  expect(errors).toEqual([]);
});

test('materials not drawn: the reason, on the texture card or in the problems when there is no texture', async ({ page }) => {
  allowErrors('3_3_2_Room01_FieldPanel02.nod: not drawn: group 0 AR_ScanFieldSquare_blu: shader dynamic is not drawn', 'pCannon_collide.nod: not drawn: group 0 collide: found by no step of the material lookup');
  const errors = await open(page);
  const cases = [
    ['3D/Models/3_3_2_Room01_FieldPanel02.nod', 'not drawn: shader dynamic is not drawn'],
    ['3D/Models/pCannon_collide.nod', 'not drawn: found by no step of the material lookup'],
    ['3D/Models/swdemoSKY.nod', 'not drawn: hidden by its shader'],
  ];
  for (const [file, words] of cases) {
    const id = await add(page, file);
    await page.locator(`#scene li[data-id="${id}"] .head .name`).dblclick();
    const user = file.split('/').pop();
    const shown = await inside(page, user);
    const said = [...shown.entries.flatMap((e) => e.facts.map(([, v]) => v)), ...shown.problems];
    expect(said.some((s) => s.includes(words)), `${file}: ${JSON.stringify(said)}`).toBe(true);
    // Negative: a material without a texture file has no entry, only its problem line.
    for (const p of shown.problems.filter((s) => s.includes(': no texture file'))) {
      const material = p.slice(0, p.indexOf(': no texture file'));
      expect(shown.entries.some((e) => e.facts.some(([n]) => n === `material ${material}`))).toBe(false);
    }
    await closeWindow(page);
    await page.evaluate((i) => window.sc2viewer.remove(i), id);
  }
  expect(errors).toEqual([]);
});

test('negative: a texture that does not load is named in the problems; the instance keeps its own', async ({ page }) => {
  allowErrors(/^http 404 GET .*\/api\/ghost\/asset\?.*kind=texture/, /^console\.error: Failed to load resource: the server responded with a status of 4\d\d/);
  const errors = await open(page);
  const id = await add(page, '3D/Models/crate.nod');
  let gone = 0;
  await page.route('**/api/ghost/asset?*', (route) => {
    if (new URL(route.request().url()).searchParams.get('kind') === 'texture') {
      gone++;
      return route.fulfill({ status: 404, body: 'gone' });
    }
    return route.continue();
  });
  await page.locator(`#scene li[data-id="${id}"] .head .name`).dblclick();
  const shown = await inside(page, 'crate.nod');
  expect(shown.entries).toEqual([]);
  expect(shown.problems).toEqual([expect.stringMatching(/\.dds \(404\)$/i)]);
  expect(gone).toBe(1);
  const groups = await page.evaluate((i) => window.sc2viewer.probe('nod', 'groups', i), id);
  expect(groups[0].textureLoaded).toBe(true);
  expect(errors).toEqual([]);
});
