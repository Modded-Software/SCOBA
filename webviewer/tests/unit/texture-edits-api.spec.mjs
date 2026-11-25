import { existsSync } from 'node:fs';
import { readFile, stat } from 'node:fs/promises';
import http from 'node:http';
import { join } from 'node:path';
import { test, expect } from '../fixtures.mjs';
import { changeScratch, checkedSession, editUrl, hostUrl, layersOf, openSession, painted, sessionOf, sessionsOf } from '../edits.mjs';
import { colourTexture, stateOf } from '../skins.mjs';

// The edit routes, without a browser (SPEC-PHOTOCRAFT 7, 8, 12): a session is
// opened, its scratch is read and written, a scratch another program changed
// is checked and turns the session edited, a transfer makes the variant, and
// a discard removes the session. The scratch is changed by the commands of
// PhotoCraft's own renderer. No other spec uses these owners' textures.

const DATASET = 'stock';
const PNG = '\x89PNG';
const BOUND = 1024 * 1024 * 1024;

test.describe.configure({ timeout: 180_000 });

/** A PUT that declares `length` bytes and sends none: the reply to its header alone. */
function declaredPut(url, length) {
  return new Promise((resolve, reject) => {
    const sent = http.request(url, { method: 'PUT', headers: { 'content-type': 'application/octet-stream', 'content-length': String(length) } });
    sent.on('error', reject);
    sent.on('response', (reply) => {
      let text = '';
      reply.setEncoding('utf8').on('data', (part) => (text += part));
      reply.on('end', () => {
        sent.destroy();
        resolve({ status: reply.statusCode, text });
      });
    });
    sent.flushHeaders();
  });
}

test('a session is opened with a base per plane and a scratch of one group per plane; a second open answers it; what is no session is refused', async ({ request }) => {
  const asset = await colourTexture(request, DATASET, 'unit:Marauder');
  const session = await openSession(request, DATASET, asset);
  expect(session).toMatchObject({ asset, variant: 'original', state: 'unchanged', reason: '', changed: [], leftOut: [], checking: false, checkError: '', transfers: [] });
  expect(session.session).toMatch(/^[0-9a-f]{16}$/);
  expect(session.planes.length).toBeGreaterThan(0);
  expect(Object.keys(session.rendered).sort()).toEqual([...session.planes].sort());
  // The scratch on disk: one top-level group per plane, in order, each with one layer `base`.
  const layers = await layersOf(session.scratch);
  expect(layers.size).toEqual(session.size);
  expect(layers.top).toEqual(session.planes.map((plane) => `Group ${plane}`));
  for (const plane of session.planes) expect(layers.children[plane], plane).toEqual(['Pixel base']);

  // The scratch route gives that file, and names the document for the editor.
  const scratch = await request.get(hostUrl(session.session, '/scratch'));
  expect(scratch.status()).toBe(200);
  expect(scratch.headers()['x-photocraft-name']).toBe('scratch.psd');
  const bytes = await scratch.body();
  expect(bytes.equals(await readFile(session.scratch))).toBe(true);
  expect(bytes.subarray(0, 4).toString('latin1')).toBe('8BPS');
  for (const kind of ['base', 'rendered']) {
    for (const plane of session.planes) {
      const picture = await request.get(hostUrl(session.session, `/${kind}/${plane}`));
      expect(picture.status(), `${kind}/${plane}`).toBe(200);
      expect(picture.headers()['content-type']).toBe('image/png');
      expect((await picture.body()).subarray(0, 4).toString('latin1')).toBe(PNG);
    }
  }

  // A second open answers the same session and writes nothing.
  const before = (await stat(session.scratch)).mtimeMs;
  expect((await openSession(request, DATASET, asset)).session).toBe(session.session);
  expect((await stat(session.scratch)).mtimeMs).toBe(before);
  expect((await sessionsOf(request, DATASET)).map((one) => one.session)).toContain(session.session);
  expect(await sessionOf(request, DATASET, session.session)).toEqual(session);

  // Negative: what is no variant of the texture is refused, and leaves no session.
  const count = (await sessionsOf(request, DATASET)).length;
  const none = await request.post(editUrl(DATASET, '/open'), { data: { asset, variant: 'fast@1024' } });
  expect(none.status(), await none.text()).toBe(400);
  expect((await none.json()).error).toContain('has no variant fast@1024');
  expect((await request.post(editUrl(DATASET, '/open'), { data: { asset } })).status()).toBe(400);
  expect((await request.post(editUrl(DATASET, '/open'), { data: { asset: 'assets\\textures\\no_such_texture.dds', variant: 'original' } })).status()).toBe(400);
  expect((await sessionsOf(request, DATASET)).length).toBe(count);
  // Negative: a name that is no session id is 400, a session that is not there 404, a plane the session lacks 400.
  expect((await request.get(editUrl(DATASET, '/NOT-A-SESSION'))).status()).toBe(400);
  expect((await request.get(editUrl(DATASET, '/0123456789abcdef'))).status()).toBe(404);
  expect((await request.get(hostUrl('0123456789abcdef', '/scratch'))).status()).toBe(404);
  expect((await request.get(hostUrl(session.session, '/base/no-such-plane'))).status()).toBe(400);
  expect((await request.get(hostUrl(session.session, '/scratch/more'))).status()).toBe(404);
  // Negative: the methods are fixed, and a session's state needs its dataset.
  expect((await request.get(editUrl(DATASET, '/open'))).status()).toBe(405);
  expect((await request.post(editUrl(DATASET), { data: {} })).status()).toBe(405);
  expect((await request.post(hostUrl(session.session, '/scratch'), { data: {} })).status()).toBe(405);
  expect((await request.get(hostUrl(session.session, ''))).status()).toBe(400);
  // Negative: a game without a texture service has no edit route.
  expect((await request.get('/api/ghost/textures/edit?dataset=build')).status()).toBe(404);
});

test('a PUT writes the scratch and answers; a scratch written again with the same planes stays unchanged; a bad id and a body past the bound change no file', async ({ request, worker }) => {
  const asset = await colourTexture(request, DATASET, 'unit:Roach');
  const session = await openSession(request, DATASET, asset);
  const was = await readFile(session.scratch);
  const time = (await stat(session.scratch, { bigint: true })).mtimeNs;

  // Negative: refused writes. The file is the one that was there, and no part file is left.
  const bad = await request.put(hostUrl('NOT-A-SESSION', '/scratch'), { data: was, headers: { 'content-type': 'application/octet-stream' } });
  expect(bad.status()).toBe(400);
  const absent = await request.put(hostUrl('0123456789abcdef', '/scratch'), { data: was, headers: { 'content-type': 'application/octet-stream' } });
  expect(absent.status()).toBe(404);
  expect(existsSync(join(worker.store, 'sc2', 'edits', '0123456789abcdef'))).toBe(false);
  const large = await declaredPut(`${worker.url}${hostUrl(session.session, '/scratch')}`, BOUND + 1);
  expect(large.status, large.text).toBe(413);
  expect(JSON.parse(large.text).error).toContain(`at most ${BOUND} bytes`);
  expect((await stat(session.scratch, { bigint: true })).mtimeNs).toBe(time);
  expect((await readFile(session.scratch)).equals(was)).toBe(true);

  // The write: answered once the file is in place.
  const written = await request.put(hostUrl(session.session, '/scratch'), { data: was, headers: { 'content-type': 'application/octet-stream' } });
  expect(written.status(), await written.text()).toBe(200);
  expect(await written.json()).toEqual({ bytes: was.length });
  expect((await stat(session.scratch, { bigint: true })).mtimeNs).not.toBe(time);
  expect((await readFile(session.scratch)).equals(was)).toBe(true);
  // Negative (detecting): a file with another time and the same planes is checked, and does not turn edited.
  const now = await checkedSession(request, DATASET, session.session);
  expect(now).toMatchObject({ state: 'unchanged', changed: [], reason: '' });
  expect(now.scratchChanged).toBeGreaterThan(session.scratchChanged);
});

test('a scratch another program changed turns the session edited after its check; its transfer makes one variant; a discard removes the session and keeps the variant', async ({ request }) => {
  const asset = await colourTexture(request, DATASET, 'unit:Baneling');
  const session = await openSession(request, DATASET, asset);
  const made = async () => (await stateOf(request, DATASET, asset)).variants.filter((variant) => /^edit[0-9a-f]{12}@\d+$/.test(variant.id));
  expect(await made()).toEqual([]);

  // Negative: an edit that changes no plane is refused, and makes no variant.
  const nothing = await request.post(editUrl(DATASET, `/${session.session}/transfer`));
  expect(nothing.status(), await nothing.text()).toBe(400);
  expect((await nothing.json()).error).toContain('changes no plane');
  expect(await made()).toEqual([]);

  // Another program writes the scratch: a layer in the colour group. The next read starts its check.
  const plane = session.planes[0];
  await changeScratch(session, painted(session, plane));
  expect((await sessionOf(request, DATASET, session.session)).checking).toBe(true);
  const edited = await checkedSession(request, DATASET, session.session);
  expect(edited).toMatchObject({ state: 'edited', reason: '', changed: [plane], leftOut: [] });
  expect(edited.rendered[plane]).not.toBe(session.rendered[plane]);
  for (const other of session.planes.filter((one) => one !== plane)) expect(edited.rendered[other], other).toBe(session.rendered[other]);
  expect((await sessionsOf(request, DATASET)).find((one) => one.session === session.session).state).toBe('edited');

  // The transfer: its reply shows the request or the variant; then the variant is there, user-made.
  const answer = await request.post(editUrl(DATASET, `/${session.session}/transfer`));
  expect(answer.status(), await answer.text()).toBe(200);
  expect((await answer.json()).texture.asset).toBe(asset);
  await expect.poll(async () => (await sessionOf(request, DATASET, session.session)).state, { timeout: 60_000 }).toBe('transferred');
  const variants = await made();
  expect(variants).toHaveLength(1);
  expect(variants[0]).toMatchObject({ input: 'original', edited: true, stale: false, problems: [], size: Math.max(...session.size) });
  expect(variants[0].models[plane]).toBe('edit');
  expect(variants[0].numbers.map((number) => number.band)).toEqual(variants[0].numbers.map(() => 'none'));
  expect((await sessionOf(request, DATASET, session.session)).transfers).toEqual([variants[0].id]);
  expect((await stateOf(request, DATASET, asset)).requests).toEqual({});
  // Negative: the same scratch again is the same variant.
  const again = await request.post(editUrl(DATASET, `/${session.session}/transfer`));
  expect(again.status(), await again.text()).toBe(200);
  expect((await made()).map((variant) => variant.id)).toEqual([variants[0].id]);

  // A discard removes the session; the variant stays.
  const gone = await request.post(editUrl(DATASET, `/${session.session}/discard`));
  expect(gone.status(), await gone.text()).toBe(200);
  expect(await gone.json()).toEqual({ session: session.session, discarded: true });
  expect(existsSync(session.scratch)).toBe(false);
  expect((await request.get(editUrl(DATASET, `/${session.session}`))).status()).toBe(404);
  expect((await sessionsOf(request, DATASET)).map((one) => one.session)).not.toContain(session.session);
  expect((await made()).map((variant) => variant.id)).toEqual([variants[0].id]);
  // Negative: a session that is gone cannot be discarded again.
  expect((await request.post(editUrl(DATASET, `/${session.session}/discard`))).status()).toBe(404);
});
