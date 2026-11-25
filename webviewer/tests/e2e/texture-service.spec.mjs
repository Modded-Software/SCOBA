import { allowErrors, test, expect } from '../fixtures.mjs';
import { idle, itemOf, open, state } from '../page.mjs';

// The texture service as the page meets it (SPEC-VIEWER 17.1, 17.2): an
// instance never waits for a state (R-VIEW-110), and the states the page asks
// for are read from the index, the same each time (R-VIEW-111). The routes
// without a page: tests/unit/texture-service-api.spec.mjs. The 250 ms bound
// of R-VIEW-111 is not a test: a time the test measures depends on the load
// of the run (SPEC-VIEWER 11).

/** A states call of the page: `/api/sc2/textures?...`, not the routes below it. */
const STATES = /\/api\/sc2\/textures\?/;
/** A skin of scoba's remastered Marine. */
const MARINE = 'assets\\textures\\marine_remastered_diff.dds';

const isIdle = (page) => page.evaluate(() => window.sc2viewer.idle());
const addMarine = (page) => page.evaluate(() => window.sc2viewer.addUnit('Marine', { x: 0, y: 0, pick: 0.5, sequence: -1 }));

/** The instance is in the scene, drawn, and takes a click: a pixel of the view is its picture, and a click there selects it. */
async function usable(page, id) {
  await page.evaluate(() => window.sc2viewer.view({ yaw: -Math.PI / 2, pitch: 0.5, distance: 6, target: [0, 0, 0.5] }));
  let at = null;
  await expect.poll(async () => (at = await page.evaluate((i) => window.sc2viewer.itemPixel(i), id)), { timeout: 15_000 }).not.toBeNull();
  await page.mouse.click(at[0], at[1]);
  expect((await state(page)).pick.selection).toEqual([id]);
}

test('an instance is added, drawn and takes a click while the texture states do not answer; its skin follows when they do', async ({ page }) => {
  await open(page);
  let asked = 0;
  let release = () => undefined;
  const held = new Promise((resolve) => {
    release = resolve;
  });
  await page.route(STATES, async (route) => {
    asked++;
    await held;
    await route.continue();
  });
  // The add answers with the states call out and unanswered.
  const id = await addMarine(page);
  await expect.poll(() => asked).toBe(1);
  expect(await itemOf(page, id)).toMatchObject({ skin: 'original', overrides: 0 });
  await usable(page, id);
  // Negative: its skin is not shown yet, and the view says so: it is not idle, and the call is still the one.
  expect(await isIdle(page)).toBe(false);
  expect((await itemOf(page, id)).largestTexture).toBe(0);
  expect(asked).toBe(1);

  release();
  await idle(page);
  // The remastered Marine's own textures are 2048.
  expect((await itemOf(page, id)).largestTexture).toBe(2048);
});

test('an instance is added, drawn and takes a click when the texture states fail; the failure is on the status line', async ({ page }) => {
  allowErrors(/^http 500 GET .*\/api\/sc2\/textures\?/, /^console\.error: Failed to load resource: the server responded with a status of 500/, 'the texture states of scoba: the store is away');
  await open(page);
  await page.route(STATES, (route) => route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ error: 'the store is away' }) }));
  const id = await addMarine(page);
  await expect(page.locator('#status')).toContainText('the texture states of scoba: the store is away');
  await usable(page, id);
  expect(await itemOf(page, id)).toMatchObject({ skin: 'original', overrides: 0 });
  // Negative: it offers no skin, and nothing is left loading.
  expect(await page.evaluate((i) => window.sc2viewer.skinChoices(i), id)).toEqual({ owner: 'unit:Marine', choices: [], state: null, following: false });
  await idle(page);
});

test("the states of one model's textures are read from the index, the same each time", async ({ page, request }) => {
  await open(page);
  // The call the page itself makes for a Marine: every texture its model names.
  const call = page.waitForRequest(STATES);
  await addMarine(page);
  const url = new URL((await call).url());
  const assets = url.searchParams.getAll('asset');
  expect(assets).toContain(MARINE);
  expect(assets.length).toBeGreaterThan(3);
  // The server keeps nothing between reads: each opens the index anew, and
  // each answers every texture asked for.
  const answers = [];
  for (let turn = 0; turn < 5; turn++) {
    const answer = await request.get(url.pathname + url.search);
    expect(answer.status()).toBe(200);
    const body = await answer.json();
    expect(body.textures.map((texture) => texture.asset).sort()).toEqual([...assets].sort());
    expect(body.unknown).toEqual([]);
    answers.push(JSON.stringify(body));
  }
  expect(new Set(answers).size).toBe(1);
});
