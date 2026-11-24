// StarCraft: Ghost actors with motions in the page (SPEC-VIEWER-GHOST 9,
// "In the page"): the motion set's clips reach the nod format, play, and a
// clip that does not load is reported. Needs GHOST_PATH. Engine state only.
import { test, expect } from '@playwright/test';
import { open, addRecord, probe, itemOf } from './ghost.mjs';

const recordOf = async (request, id) => (await request.get(`/api/ghost/record/actors?${new URLSearchParams({ dataset: 'build', id })}`)).json();
// The build's zergling set holds Nova's side of a paired death: a clip for
// her bones, not the zergling's. The viewer leaves it out and names it.
const FOREIGN = { name: 'deathblown', clip: 'nova_death_byZergling.nad' };
/** The motion names the zergling plays: its set's, without the foreign clip. */
const playable = (record) => record.motions.filter((m) => m.clip !== FOREIGN.clip).map((m) => m.name);
/** The largest distance between two lists of positions. */
const apart = (a, b) => Math.max(...a.map((p, v) => Math.max(...p.map((x, k) => Math.abs(x - b[v][k])))));

test('an actor with a motion set: its clips play, the pose moves with the playhead and stays finite', async ({ page, request }) => {
  const errors = await open(page);
  const record = await recordOf(request, 'zerg_critter');
  const id = await addRecord(page, 'actors', 'zerg_critter');
  const item = await itemOf(page, id);
  expect(item.sequences).toEqual(playable(record));
  expect(item.sequences.length).toBeGreaterThan(1);
  // The rest sequence is stand, when the set has one.
  const stand = item.sequences.findIndex((s) => s.toLowerCase() === 'stand');
  if (stand >= 0) expect(item.sequence).toBe(stand);
  const clip = stand >= 0 ? stand : 0;
  await probe(page, 'holdAt', id, clip, 0);
  const length = (await itemOf(page, id)).sequenceLength;
  expect(length).toBeGreaterThan(0);
  const start = (await probe(page, 'positions', id, 7)).skinned;
  await probe(page, 'holdAt', id, clip, length / 2);
  const middle = (await probe(page, 'positions', id, 7)).skinned;
  expect(await probe(page, 'poseFinite', id)).toBe(true);
  console.log('anim', JSON.stringify({ clip: item.sequences[clip], length, moved: apart(start, middle) }));
  expect(apart(start, middle), 'the pose moves between two playheads').toBeGreaterThan(1e-3);
  // Negative: the same playhead gives the same pose.
  await probe(page, 'holdAt', id, clip, 0);
  expect(apart(start, (await probe(page, 'positions', id, 7)).skinned)).toBeLessThan(1e-6);
  // Past the end the last key holds: still finite.
  await probe(page, 'holdAt', id, clip, length * 3);
  expect(await probe(page, 'poseFinite', id)).toBe(true);
  expect(errors).toEqual([]);
});

test('key joins: the curve in frames meets the next key more often than the curve in 0..1', async ({ page }) => {
  const errors = await open(page);
  const id = await addRecord(page, 'actors', 'zerg_critter');
  const joins = await probe(page, 'joins', id);
  // Raw values, for the open question of the key time (SPEC-VIEWER-GHOST 4.2).
  console.log('joins', JSON.stringify(joins));
  expect(joins.frames.hold + joins.frames.miss).toBeGreaterThan(0);
  expect(joins.frames.hold + joins.frames.miss).toBe(joins.unit.hold + joins.unit.miss);
  expect(joins.frames.hold).toBeGreaterThan(joins.unit.hold);
  expect(errors).toEqual([]);
});

test('one model file, two actors: each has the motions of its own set', async ({ page, request }) => {
  const errors = await open(page);
  const [a, b] = [await recordOf(request, 'zerg_critter'), await recordOf(request, 'zergling_burrowed')];
  const ida = await addRecord(page, 'actors', 'zerg_critter', -2);
  const idb = await addRecord(page, 'actors', 'zergling_burrowed', 2);
  const [ia, ib] = [await itemOf(page, ida), await itemOf(page, idb)];
  expect(ia.path.toLowerCase()).toBe(ib.path.toLowerCase());
  expect(ia.sequences).toEqual(playable(a));
  expect(ib.sequences).toEqual(playable(b));
  // Negative: the two sets differ, and neither instance took the other's.
  expect(ia.sequences).not.toEqual(ib.sequences);
  expect(errors).toEqual([]);
});

test('a clip that does not load is left out and reported; the others play', async ({ page, request }) => {
  const errors = await open(page);
  const record = await recordOf(request, 'zerg_critter');
  const dropped = record.motions[0];
  await page.route('**/api/ghost/asset?*', (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get('kind') === 'animation' && url.searchParams.get('ref') === dropped.clip) return route.fulfill({ status: 404, body: 'gone' });
    return route.continue();
  });
  const warnings = [];
  page.on('console', (m) => {
    if (m.text().includes('clips left out')) warnings.push(m.text());
  });
  const id = await addRecord(page, 'actors', 'zerg_critter');
  const item = await itemOf(page, id);
  expect(item.sequences).toEqual(playable(record).slice(1));
  // Negative: one sequence of the dropped name fewer (names repeat in a set).
  const count = (list) => list.filter((n) => n === dropped.name).length;
  expect(count(item.sequences)).toBe(count(playable(record)) - 1);
  await expect(page.locator('#status')).toContainText('2 clip(s) left out');
  expect(warnings.join(' ')).toContain(`${dropped.name} (${dropped.clip}): HTTP 404`);
  expect(errors).toEqual([]);
});

test("a clip for another model's bones is left out and named with the bone it lacks", async ({ page, request }) => {
  const errors = await open(page);
  const record = await recordOf(request, 'zerg_critter');
  expect(record.motions).toContainEqual(expect.objectContaining(FOREIGN));
  const warnings = [];
  page.on('console', (m) => {
    if (m.text().includes('clips left out')) warnings.push(m.text());
  });
  const id = await addRecord(page, 'actors', 'zerg_critter');
  const item = await itemOf(page, id);
  expect(item.sequences).not.toContain(FOREIGN.name);
  await expect(page.locator('#status')).toContainText('1 clip(s) left out');
  expect(warnings.length).toBe(1);
  console.log('foreign', warnings[0]);
  expect(warnings[0]).toContain(`${FOREIGN.name} (${FOREIGN.clip}): clip ${FOREIGN.name}: track `);
  expect(warnings[0]).toMatch(/names bone \d+; the model has \d+/);
  expect(errors).toEqual([]);
});
