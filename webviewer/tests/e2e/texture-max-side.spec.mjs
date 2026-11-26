// The largest side a request may ask for (R-HD-123, SPEC-VIEWER 17.5): a
// server of its own, started with TEXTURE_MAX_SIDE=1024. Its head names the
// side; every factor's side is at most it; a size past it is refused; an
// owner upscale that would ask for nothing is refused by the server, stores
// no skin, and cannot be sent from the dialog. The runner needs no GPU
// (HDTEX_RUNNER=repeat).
import { test, expect, ownServer } from '../fixtures.mjs';
import { menu, place } from '../skins.mjs';

test.describe.configure({ mode: 'serial', timeout: 240_000 });

const MAX = 1024;
/** Units whose textures are looked at for one that 2x cannot enlarge at 1024. */
const CANDIDATES = ['Marine', 'Marauder', 'Zealot', 'Stalker', 'Hydralisk', 'Ultralisk', 'Thor', 'Infestor', 'Medic', 'Zergling'];

let server;

test.beforeAll(async ({ worker }, testInfo) => {
  server = await ownServer(worker, testInfo.parallelIndex, 'max-side', { TEXTURE_MAX_SIDE: String(MAX) });
});

test.afterAll(async () => {
  if (server) await server.stop();
});

const api = (route, more = {}) => `${server.url}/api/sc2/textures${route}?${new URLSearchParams({ dataset: 'scoba', ...more })}`;
const post = (route, data) => fetch(api(`/${route}`), { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(data) });

async function ownerOf(owner) {
  const answer = await fetch(api('/owner', { owner }));
  expect(answer.status, await answer.clone().text()).toBe(200);
  return answer.json();
}

async function judged(textures) {
  const answer = await post('judge', { assets: textures });
  expect(answer.status, await answer.clone().text()).toBe(200);
  return answer.json();
}

/** The factors fast has from a texture's original: the model every texture may take. */
const factorsOf = (state) => state.asks.find((one) => one.input === 'original')?.models.fast?.factors ?? {};

/** The first candidate owner that 2x of fast enlarges no texture of: { owner, states }. */
async function ownerAskingNothing() {
  const seen = [];
  for (const unit of CANDIDATES) {
    const owner = `unit:${unit}`;
    const { owner: found } = await ownerOf(owner);
    if (!found) continue;
    const body = await judged(found.textures);
    const enlarged = body.textures.filter((state) => !state.reason && factorsOf(state)['2']?.reason === '');
    seen.push(`${owner}: ${enlarged.length} of ${body.textures.length}`);
    if (enlarged.length === 0) return { owner, states: body.textures };
  }
  throw new Error(`no candidate owner has only textures 2x cannot enlarge at ${MAX}: ${seen.join('; ')}`);
}

test('the head names the largest side; every factor gives at most it; a size past it is refused', async () => {
  const { owner } = await ownerOf('unit:Marine');
  const body = await judged(owner.textures);
  // The index the store held was written with 4096: at its start the server wrote its states again (index --states).
  expect([body.factors, body.maxSide]).toEqual([[2, 4], MAX]);
  expect(server.output(), 'negative: the states rewrite at the start did not fail').not.toContain('was not brought up to date');
  const sides = body.textures.flatMap((state) => state.asks.flatMap((ask) => Object.values(ask.models).flatMap((model) => Object.values(model.factors))));
  console.log(`sides ${JSON.stringify([...new Set(sides.map((one) => one.size))].sort((a, b) => a - b))}`);
  expect(sides.length).toBeGreaterThan(0);
  for (const one of sides) expect(one.size, JSON.stringify(one)).toBeLessThanOrEqual(MAX);
  // Negative: a size past the largest side is refused, and nothing is queued.
  const state = body.textures.find((one) => !one.reason);
  const refused = await post('request', { asset: state.asset, input: 'original', model: 'fast', size: 2 * MAX });
  expect(refused.status).toBe(400);
  expect((await refused.json()).error).toContain(`${2 * MAX} is no size a factor of fast gives now`);
  const [after] = (await (await fetch(api('', { asset: state.asset }))).json()).textures;
  expect(after.requests.fast).toBeUndefined();
});

test('negative: an owner upscale that asks for nothing is refused, stores no skin, and the dialog cannot send it', async ({ page }) => {
  const { owner } = await ownerAskingNothing();
  const before = await ownerOf(owner);
  expect(before.owner.skins).toEqual([]);
  const refused = await post('skin', { owner, action: 'upscale', name: null, from: 'original', model: 'fast', factor: 2 });
  expect(refused.status).toBe(400);
  expect((await refused.json()).error).toContain('2x asks for no texture, so no skin is made');
  expect((await ownerOf(owner)).owner.skins, 'negative: no empty New Skin N').toEqual([]);

  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto(`${server.url}/`);
  await expect.poll(() => page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 10_000 }).toBe(true);
  const id = await place(page, owner.split(':')[1]);
  await menu(page, id);
  await page.locator('#anim-menu button.skin-upscale').click();
  const dialogState = () => page.evaluate(() => window.scobaeditor.upscaleDialog());
  await expect.poll(async () => (await dialogState()).kind, { timeout: 30_000 }).toBe('owner');
  await page.selectOption('#upscale-dialog select.upscale-model', 'fast');
  await page.selectOption('#upscale-dialog select.upscale-factor', '2');
  const dialog = await dialogState();
  console.log(`owner plan ${JSON.stringify(dialog.lines)}`);
  expect(dialog.lines).toContain('0 textures get a request');
  expect(dialog.lines).toContain(`Each texture gets 2x its side, at most ${MAX}.`);
  expect(dialog.submittable).toBe(false);
  await expect(page.locator('#upscale-dialog button.upscale-submit')).toBeDisabled();
  expect(errors).toEqual([]);
});
