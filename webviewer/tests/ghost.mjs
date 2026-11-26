// What the Ghost page specs share (ghost-page, ghost-anim, ghost-look):
// open the page, add Ghost files and records, reach the nod probes and
// the pick. Engine state only.
import { expect } from './fixtures.mjs';

export async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.scobaeditor && window.scobaeditor.ready)), { timeout: 20_000 }).toBe(true);
  return errors;
}

/**
 * The viewer's report on the zergling models (a data fact, not a fault): their
 * motion set holds Nova's side of a paired death, a clip for her bones, which
 * names bone 32 of a model with 32 (0 to 31). It is left out and named
 * (ghost-anim.spec.mjs). A spec that loads a zergling allows it (allowErrors).
 */
export const FOREIGN_CLIP = /clips left out: .*deathblown \(nova_death_byZergling\.nad\): clip deathblown: track \d+ names bone 32; the model has 32/;

/** The one dataset, and the crate: one material, one texture file (SPEC-VIEWER-GHOST 9). */
export const DATASET = 'build';
export const CRATE = '3D/Models/crate.nod';
export const CRATE_OWNER = 'model:3d\\models\\crate.nod';
export const CRATE_TEXTURE = '3d\\materials\\chestcrate2.dds';
/** Why Ghost bakes nothing (R-HD-154, R-VIEW-151). */
export const NO_BAKE = 'baking is not enabled for StarCraft: Ghost';

const query = (more = {}) => new URLSearchParams({ dataset: DATASET, ...more });
/** POST one texture route of Ghost (SPEC-VIEWER 17.2). */
export const texturePost = (request, route, data) => request.post(`/api/ghost/textures/${route}?${query()}`, { data });
/** The state of one Ghost texture, with the head. */
export const textureBody = async (request, asset) => (await request.get(`/api/ghost/textures?${query({ asset })}`)).json();
/** One Ghost owner, or null. */
export const ownerLookup = async (request, owner) => (await (await request.get(`/api/ghost/textures/owner?${query({ owner })}`)).json()).owner;

export const add = (page, path, x = 0) => page.evaluate(([p, at]) => window.scobaeditor.add(p, { game: 'ghost', x: at, y: 0, rot: 0 }), [path, x]);
export const addRecord = (page, category, id, x = 0) => page.evaluate(([c, i, at]) => window.scobaeditor.addRecord(c, i, { game: 'ghost', x: at, y: 0, rot: 0 }), [category, id, x]);
export const probe = (page, name, ...args) => page.evaluate(([n, a]) => window.scobaeditor.probe('nod', n, ...a), [name, args]);
export const itemOf = async (page, id) => (await page.evaluate(() => window.scobaeditor.state())).items.find((i) => i.id === id);
/** The id of the item the pick finds at a page pixel, or null. */
export const hitId = (page, [x, y]) => page.evaluate(([px, py]) => window.SCOBAEdit.itemAt(px, py)?.id ?? null, [x, y]);
/** Two frames drawn, so the pick buffer and lastDrawn hold this state. */
export const frames = (page) => page.evaluate(() => new Promise((resolve) => requestAnimationFrame(() => requestAnimationFrame(resolve))));

/** The camera on one item, from the front and a little above, the whole rest box in view. */
export async function frameItem(page, id) {
  const item = await itemOf(page, id);
  const [min, max] = item.vertexBox;
  const target = [item.x + (min[0] + max[0]) / 2, item.y + (min[1] + max[1]) / 2, (min[2] + max[2]) / 2];
  const size = Math.max(max[0] - min[0], max[1] - min[1], max[2] - min[2]);
  await page.evaluate((v) => window.scobaeditor.view(v), { yaw: -Math.PI / 2, pitch: 0.35, distance: size * 1.6 + 0.5, target });
  await frames(page);
}

/**
 * Pick at points well inside each triangle of one group of an item as
 * drawn (rest pose, no turn, scale 1): how many find the item and how
 * many do not.
 */
export async function triangleHits(page, id, group) {
  const { skinned } = await probe(page, 'positions', id);
  const corners = await probe(page, 'triangles', id, group);
  const item = await itemOf(page, id);
  const points = [];
  for (const [a, b, c] of corners) {
    for (const [u, v] of [[0.2, 0.2], [0.6, 0.2], [0.2, 0.6], [0.33, 0.33]]) {
      points.push([0, 1, 2].map((k) => skinned[a][k] * (1 - u - v) + skinned[b][k] * u + skinned[c][k] * v + (k === 0 ? item.x : k === 1 ? item.y : 0)));
    }
  }
  const counts = await page.evaluate(
    ([pts, own]) => {
      let hit = 0;
      let miss = 0;
      for (const p of pts) {
        const s = window.scobaeditor.screenOf(p);
        if (!s) continue;
        if (window.SCOBAEdit.itemAt(Math.round(s[0]), Math.round(s[1]))?.id === own) hit++;
        else miss++;
      }
      return { hit, miss };
    },
    [points, id],
  );
  return { ...counts, triangles: corners.length };
}
