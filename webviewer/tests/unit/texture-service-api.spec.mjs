import { test, expect } from '../fixtures.mjs';
import { execFileSync } from 'node:child_process';
import { api } from '../api.mjs';
import { cleanOwner, colourTexture, madeVariant, makeSkin, ownerOf, post, stateOf } from '../skins.mjs';

// The texture service's routes, without a browser (SPEC-VIEWER 17.1, 17.2):
// a state is read from the pipeline's state index (R-VIEW-111), a failed
// request shows as failed, and the judge route has the pipeline read a
// texture nobody asked for by name. Each worker's server made its state
// index when it started (fixtures.mjs). The 250 ms bound of R-VIEW-111 is not
// a test: a time the test measures depends on the load of the run
// (SPEC-VIEWER 11). What the page does with the states:
// tests/e2e/texture-service.spec.mjs.

/** No test asks for this texture or judges it: nobody read it. */
const UNREAD = 'assets\\textures\\ultralisk_diffuse.dds';
/** A skin every test dataset has. */
const SHARED = 'assets\\textures\\marine_diffuse_blood.dds';
const NONE = 'assets\\textures\\no_such_texture.dds';
/** A skin of 1024: its result takes seconds to encode. No other test asks for it. */
const STOPPED = 'assets\\textures\\leviathan_diffuse.dds';

const statesUrl = (dataset, assets) => {
  const query = new URLSearchParams({ dataset });
  for (const asset of assets) query.append('asset', asset);
  return `/api/sc2/textures?${query}`;
};
const judge = (request, dataset, data) => request.post(`/api/sc2/textures/judge?${new URLSearchParams({ dataset })}`, { data });

test('negative: no state read fails beside pipeline processes that write the index and end', async ({ request }) => {
  test.setTimeout(120_000);
  // Each skin change is a process that opens the index, writes a row and ends. Ending as the file's last user it
  // holds the file whole for a moment: a reader without a busy wait got "database is locked" there.
  const OWNER = 'unit:Marine';
  const skin = (data) => request.post(`/api/sc2/textures/skin?${new URLSearchParams({ dataset: 'stock' })}`, { data: { owner: OWNER, ...data } });
  let writing = true;
  const writes = (async () => {
    try {
      for (let turn = 0; turn < 4; turn++) {
        for (const data of [{ action: 'copy', name: 'locktest', from: 'original' }, { action: 'delete', name: 'locktest' }]) {
          const answer = await skin(data);
          expect(answer.status(), await answer.text()).toBe(200);
        }
      }
    } finally {
      writing = false;
    }
  })();
  const failed = [];
  let reads = 0;
  const reader = async () => {
    while (writing) {
      const answer = await request.get(statesUrl('stock', [SHARED]));
      reads++;
      if (answer.status() !== 200) failed.push(`${answer.status()} ${await answer.text()}`);
    }
  };
  await Promise.all([writes, reader(), reader(), reader(), reader()]);
  console.log(`${reads} reads beside 8 skin changes; failed: ${failed.length}`);
  expect(failed).toEqual([]);
  expect(reads).toBeGreaterThan(200);
  // Negative: an owner the index does not hold is an answer, not an error: 200 and null.
  const none = await request.get(`/api/sc2/textures/owner?${new URLSearchParams({ dataset: 'stock', owner: 'unit:NoSuchUnit' })}`);
  expect(none.status()).toBe(200);
  expect((await none.json()).owner).toBeNull();
  // The last change deleted it: the owner has no such skin.
  const owner = await (await request.get(`/api/sc2/textures/owner?${new URLSearchParams({ dataset: 'stock', owner: OWNER })}`)).json();
  expect(owner.owner.skins.map((one) => one.name)).not.toContain('locktest');
});

test('the server listed every dataset in a new state index when it started; a name that is no texture is unknown', async ({ request }) => {
  for (const dataset of ['scoba', 'stock', 'fx']) {
    const answer = await request.get(statesUrl(dataset, [SHARED, NONE]));
    expect(answer.status(), dataset).toBe(200);
    const body = await answer.json();
    expect(body.textures.map((texture) => texture.asset), dataset).toEqual([SHARED]);
    expect(body.textures[0].kind, dataset).toBe('model');
    expect(body.models.map((model) => model.id), dataset).toEqual(['pbrify', 'fast', 'seedvr2']);
    // Negative: it holds no row for a name that is no texture.
    expect(body.unknown, dataset).toEqual([NONE]);
  }
});

test('a request whose process is gone shows as failed; asked again, the reply shows the new request and its variant is made', async ({ request }) => {
  test.setTimeout(120_000);
  // The largest size fast may make from the original, as the pipeline says.
  const judged = await judge(request, 'stock', { assets: [STOPPED] });
  expect(judged.status(), await judged.text()).toBe(200);
  const sizes = (await judged.json()).textures[0].asks.find((one) => one.input === 'original').models.fast.sizes;
  const SIZE = Math.max(...Object.entries(sizes).filter(([, why]) => why === '').map(([at]) => Number(at)));
  const VARIANT = `fast@${SIZE}`;
  const RECIPE = 'fast';
  const read = async () => (await (await request.get(statesUrl('stock', [STOPPED]))).json()).textures[0];
  const made = (state) => state.variants.find((variant) => variant.id === VARIANT);
  const ask = () => request.post(`/api/sc2/textures/request?${new URLSearchParams({ dataset: 'stock' })}`, { data: { asset: STOPPED, input: 'original', model: 'fast', size: SIZE } });
  const running = ['queued', 'upscaling', 'encoding'];

  const asked = await ask();
  expect(asked.status(), await asked.text()).toBe(200);
  const open = (await asked.json()).textures[0];
  // Negative: while its process runs, the request does not show as failed, and it has no variant.
  expect(made(open), 'the request was done before it could be stopped').toBeUndefined();
  expect(running).toContain(open.requests[RECIPE].state);
  // The request is a process of its own (and its launcher): both are stopped, as a crash or a kill would.
  const pids = execFileSync('pgrep', ['-f', 'hd_textures\\.py request .*leviathan_diffuse']).toString().trim().split('\n').map(Number);
  expect(pids.length).toBeGreaterThan(0);
  for (const pid of pids) process.kill(pid, 'SIGKILL');

  // Nobody was left to write that it failed: the server sees that the process is gone.
  await expect.poll(async () => (await read()).requests[RECIPE]?.state).toBe('failed');
  const gone = await read();
  expect(gone.requests[RECIPE].reason).toMatch(/process \d+\) stopped before it was done; ask again/);
  // It may be asked again: the state offers fast at that size from the original.
  expect(gone.asks.find((one) => one.input === 'original').models.fast).toMatchObject({ reason: '', sizes: { [SIZE]: '' } });
  expect(made(gone)).toBeUndefined();

  // Asked again: the reply holds the new request, not the one that is gone.
  const again = await ask();
  expect(again.status(), await again.text()).toBe(200);
  const fresh = (await again.json()).textures[0];
  if (!made(fresh)) expect(running).toContain(fresh.requests[RECIPE].state);
  await expect.poll(async () => {
    const now = await read();
    return now.requests[RECIPE]?.state === 'failed' ? now.requests[RECIPE].reason : Boolean(made(now));
  }, { timeout: 60_000 }).toBe(true);
  expect((await read()).requests[RECIPE]).toBeUndefined();
});

test('the judge route has the pipeline read a texture nobody asked for; before it the texture offers no request', async ({ request }) => {
  test.setTimeout(60_000);
  const read = async () => (await (await request.get(statesUrl('stock', [UNREAD]))).json()).textures[0];
  // Negative: listed, and not read: nothing to ask for and no reason.
  expect(await read()).toMatchObject({ asset: UNREAD, judged: false, asks: [], reason: '', variants: [] });

  // Negative: a name that is no texture is refused with the pipeline's reason, and nothing is read.
  const refused = await judge(request, 'stock', { assets: [UNREAD, NONE] });
  expect(refused.status(), await refused.text()).toBe(400);
  expect((await refused.json()).error).toContain(`stock has no texture ${NONE}`);
  expect((await read()).judged).toBe(false);

  const answer = await judge(request, 'stock', { assets: [UNREAD] });
  expect(answer.status(), await answer.text()).toBe(200);
  const body = await answer.json();
  expect(body.unknown).toEqual([]);
  expect(body.textures).toHaveLength(1);
  expect(body.textures[0]).toMatchObject({ asset: UNREAD, judged: true, reason: '' });
  const fromOriginal = body.textures[0].asks.find((one) => one.input === 'original');
  expect(fromOriginal.models.pbrify.reason).toBe('');
  expect(fromOriginal.models.fast.reason).toBe('');
  // A later read holds it.
  expect(await read()).toMatchObject({ judged: true, asks: body.textures[0].asks });

  // Negative: a body without a list, and a read of the route, are refused.
  expect((await judge(request, 'stock', { assets: 'x' })).status()).toBe(400);
  expect((await judge(request, 'stock', { assets: [] })).status()).toBe(400);
  expect((await request.get(`/api/sc2/textures/judge?${new URLSearchParams({ dataset: 'stock' })}`)).status()).toBe(405);
});

test('negative: the request route refuses seedvr2 on a data texture and a size the input cannot reach; nothing is queued', async ({ request }) => {
  test.setTimeout(60_000);
  const { textures } = await ownerOf(request, 'scoba', 'unit:Infestor');
  const judged = (await (await post(request, 'judge', 'scoba', { assets: textures })).json()).textures;
  const data = judged.find((state) => !state.colour && !state.reason);
  expect(data, 'a data texture of the Infestor').toBeTruthy();
  const seed = await post(request, 'request', 'scoba', { asset: data.asset, input: 'original', model: 'seedvr2', size: 2048 });
  expect(seed.status(), await seed.text()).toBe(400);
  expect((await stateOf(request, 'scoba', data.asset)).requests.seedvr2).toBeUndefined();
  const sizes = data.asks.find((one) => one.input === 'original').models.fast.sizes;
  const unreachable = Object.entries(sizes).find(([, why]) => why !== '');
  const tooBig = unreachable ? Number(unreachable[0]) : 8192;
  const big = await post(request, 'request', 'scoba', { asset: data.asset, input: 'original', model: 'fast', size: tooBig });
  expect(big.status(), `size ${tooBig}: ${await big.text()}`).toBe(400);
  expect((await stateOf(request, 'scoba', data.asset)).variants.some((one) => one.id === `fast@${tooBig}`)).toBe(false);
});

test('negative: a bake of a skin that does not exist is refused and changes nothing; so is a body that names an owner and an asset', async ({ request }) => {
  test.setTimeout(120_000);
  const OWNER = 'unit:Medic';
  const asset = await colourTexture(request, 'scoba', OWNER);
  const made = await madeVariant(request, 'scoba', asset);
  await cleanOwner(request, 'scoba', OWNER);
  await makeSkin(request, 'scoba', OWNER, 'hd', { [asset]: made.variant });
  const refused = await post(request, 'bake', 'scoba', { owner: OWNER, skin: 'no-such-skin' });
  expect(refused.status(), await refused.text()).toBe(400);
  expect((await refused.json()).error).toMatch(/no skin/);
  expect((await ownerOf(request, 'scoba', OWNER)).bake).toBeNull();
  // Negative: refused before the pipeline runs.
  const both = await post(request, 'bake', 'scoba', { owner: OWNER, skin: 'hd', asset, variant: 'fast@1024' });
  expect(both.status()).toBe(400);
  expect((await ownerOf(request, 'scoba', OWNER)).bake).toBeNull();
});

test('the server serves the texture page and its script; the old texture viewer routes are gone', async ({ request }) => {
  const page = await request.get('/texture-viewer.html');
  expect(page.status()).toBe(200);
  expect(page.headers()['content-type']).toContain('text/html');
  expect(await page.text()).toContain('/vendor/texview.js');
  const script = await request.get('/vendor/texview.js');
  expect(script.status()).toBe(200);
  expect(script.headers()['content-type']).toContain('text/javascript');
  // Negative: the routes of the old compare page, the old HD list and the old HD files answer 404.
  for (const name of ['textures', 'textures/', 'textures/img/original.png', 'hd-textures', 'hd-asset?path=x']) {
    const path = api.x(name);
    expect((await request.get(path)).status(), path).toBe(404);
  }
  // Negative: the pick and default routes of the texture sets are gone (17.8), and a file asked by chain and size is no variant.
  const query = new URLSearchParams({ dataset: 'scoba' });
  for (const part of ['pick', 'default']) {
    const answer = await request.post(`/api/sc2/textures/${part}?${query}`, { data: { asset: 'assets\\textures\\marine_diffuse_blood.dds', pick: 'original' } });
    expect(answer.status(), part).toBe(404);
  }
  const byChain = await request.get(`/api/sc2/textures/file?${new URLSearchParams({ dataset: 'scoba', asset: 'assets\\textures\\marine_diffuse_blood.dds', chain: 'soft', size: '2048' })}`);
  expect(byChain.status()).toBe(400);
});
