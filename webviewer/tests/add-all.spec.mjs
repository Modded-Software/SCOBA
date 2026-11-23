import { test, expect } from '@playwright/test';
import { api, facets as facetsOf } from './api.mjs';

// The family filter (EditorCategories ObjectFamily; Melee is the ladder and
// multiplayer data) and "add all": one instance of every listed unit, after a
// confirm dialog, laid out by size (src/page/features/addall).

function watch(page) {
  const problems = [];
  page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
  page.on('console', (m) => {
    if (m.type() === 'error') problems.push('console: ' + m.text());
  });
  page.on('response', (r) => {
    if (r.status() >= 400) problems.push(`http ${r.status()}: ${r.url()}`);
  });
  return problems;
}

async function open(page) {
  await page.goto('/');
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
}

const units = async (page, query) => (await page.request.get(api.records('units', { limit: '500', ...query }))).json();
const state = (page) => page.evaluate(() => window.sc2viewer.state());
const run = (page) => page.evaluate(() => window.SC2App.addAllState());
const count = (page) => page.locator('#unit-count').textContent();

test('api: the family facet lists Melee; family=Melee returns Melee units only', async ({ page }) => {
  const facets = await facetsOf(page.request);
  console.log('families', JSON.stringify(facets.families));
  expect(facets.families).toContain('Melee');
  const all = await units(page, {});
  const melee = await units(page, { family: 'Melee' });
  console.log('all', all.total, 'melee', melee.total);
  expect(melee.total).toBeGreaterThan(50);
  expect(melee.total).toBeLessThan(all.total);
  for (const unit of melee.items) expect(unit.family).toBe('Melee');
  // Negative: another family has no Melee unit; no family param is no filter.
  const campaign = await units(page, { family: 'Campaign' });
  expect(campaign.total).toBeGreaterThan(0);
  for (const unit of campaign.items) expect(unit.family).not.toBe('Melee');
  expect((await units(page, { family: '' })).items.every((u) => !u.family)).toBe(true);
});

test('ui: the family select filters the list, and "any family" takes the filter off', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const all = await units(page, {});
  await expect.poll(() => count(page)).toBe(`${all.total} units`);
  await page.selectOption('#family', 'is:Melee');
  const melee = await units(page, { family: 'Melee' });
  await expect.poll(() => count(page)).toBe(`${melee.total} units`);
  // With race Zerg on top.
  await page.locator('#races button[data-race="Zerg"]').click();
  const zerg = await units(page, { family: 'Melee', race: 'Zerg' });
  await expect.poll(() => count(page)).toBe(`${zerg.total} units`);
  // Negative: back to any family.
  await page.locator('#races button[data-race=""]').click();
  await page.selectOption('#family', 'any');
  await expect.poll(() => count(page)).toBe(`${all.total} units`);
  expect(problems).toEqual([]);
});

/** Filter the list to a few Melee units: search "zergling". */
async function filterFew(page) {
  await page.selectOption('#family', 'is:Melee');
  await page.fill('#unit-search', 'zergling');
  const listed = await units(page, { family: 'Melee', q: 'zergling' });
  await expect.poll(() => count(page)).toBe(`${listed.total} units`);
  expect(listed.total).toBeGreaterThan(1);
  return listed;
}

test('add all: the dialog asks with the count; "add" adds every listed unit, laid out by size', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const listed = await filterFew(page);
  await page.locator('#add-all').click();
  await expect(page.locator('#add-all-dialog')).toBeVisible();
  await expect(page.locator('#add-all-dialog .question')).toHaveText(`Are you sure you want to add ${listed.total} units to the map?`);
  await page.locator('#add-all-yes').click();
  await expect.poll(async () => (await run(page)).running === false && (await run(page)).asked === listed.total, { timeout: 30_000 }).toBe(true);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 30_000 });
  const r = await run(page);
  const s = await state(page);
  console.log('run', JSON.stringify({ asked: r.asked, added: r.added, failed: r.failed }), 'layout', JSON.stringify(r.layout.map((l) => [l.id, +l.size.toFixed(2), +l.x.toFixed(2), +l.y.toFixed(2)])));
  expect(r.failed).toEqual([]);
  expect(r.added).toBe(listed.total);
  // Every listed unit is in the scene once.
  expect(s.items.map((i) => i.unit).sort()).toEqual(listed.items.map((u) => u.id).sort());
  // Smallest first.
  for (let i = 1; i < r.layout.length; i++) expect(r.layout[i].size).toBeGreaterThanOrEqual(r.layout[i - 1].size);
  // The size is the drawn bounds diameter: from what the renderer holds.
  for (const l of r.layout) {
    const item = s.items.find((i) => i.id === l.id);
    expect(l.size).toBeCloseTo(2 * item.boundsRadius * Math.max(item.dataScale[0], item.dataScale[1]) * item.scale, 4);
    // The engine stands the unit where the layout put it.
    expect(item.location[0]).toBeCloseTo(l.x, 4);
    expect(item.location[1]).toBeCloseTo(l.y, 4);
  }
  // No two cells overlap: centres at least half the sum of the sizes apart on x or y.
  for (let i = 0; i < r.layout.length; i++) {
    for (let j = i + 1; j < r.layout.length; j++) {
      const [a, b] = [r.layout[i], r.layout[j]];
      const reach = (a.size + b.size) / 2;
      expect(Math.abs(a.x - b.x) >= reach - 1e-6 || Math.abs(a.y - b.y) >= reach - 1e-6, `${a.id} and ${b.id} overlap`).toBe(true);
    }
  }
  expect(problems).toEqual([]);
});

/** Click "add all", confirm, wait for the run and the loads; the run state. */
async function addAllRun(page, total) {
  await page.locator('#add-all').click();
  await page.locator('#add-all-yes').click();
  await expect.poll(async () => {
    const r = await run(page);
    return r.running === false && r.asked === total && r.added + r.failed.length === total;
  }, { timeout: 30_000 }).toBe(true);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 30_000 });
  return run(page);
}

/** Ground box of layout cells (each a square of its size). */
function box(layout) {
  return {
    x0: Math.min(...layout.map((l) => l.x - l.size / 2)),
    x1: Math.max(...layout.map((l) => l.x + l.size / 2)),
    y0: Math.min(...layout.map((l) => l.y - l.size / 2)),
    y1: Math.max(...layout.map((l) => l.y + l.size / 2)),
  };
}

test('add all again: each new block goes next to the units already on the map, nothing overlaps, nothing moves', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const listed = await filterFew(page);
  const GAP = 0.5; // features/addall/layout.ts
  const runs = [];
  for (let i = 0; i < 3; i++) {
    const r = await addAllRun(page, listed.total);
    expect(r.failed).toEqual([]);
    runs.push(r.layout);
    console.log(`run ${i + 1}: box ${JSON.stringify(box(r.layout), (k, v) => (typeof v === 'number' ? +v.toFixed(2) : v))}`);
  }
  const s = await state(page);
  expect(s.items.length).toBe(3 * listed.total);

  // The first block, on an empty map, is around the origin.
  const first = box(runs[0]);
  expect(first.x0 < 0 && first.x1 > 0 && first.y0 < 0 && first.y1 > 0).toBe(true);

  for (let i = 1; i < runs.length; i++) {
    const old = box(runs.slice(0, i).flat());
    const add = box(runs[i]);
    // Apart on one axis by at most a few gaps (next to it, not across the map),
    // and lined up on the other (side by side, not diagonal).
    const below = old.y0 - add.y1;
    const right = add.x0 - old.x1;
    const apart = Math.max(below, right);
    console.log(`run ${i + 1}: below ${below.toFixed(2)}, right ${right.toFixed(2)}`);
    expect(apart).toBeGreaterThanOrEqual(0);
    expect(apart).toBeLessThanOrEqual(3 * GAP);
    if (below >= right) expect(add.x0 < old.x1 && add.x1 > old.x0).toBe(true);
    else expect(add.y0 < old.y1 && add.y1 > old.y0).toBe(true);
  }

  // Negative: no two cells overlap, across all runs.
  const all = runs.flat();
  for (let i = 0; i < all.length; i++) {
    for (let j = i + 1; j < all.length; j++) {
      const [a, b] = [all[i], all[j]];
      const reach = (a.size + b.size) / 2;
      expect(Math.abs(a.x - b.x) >= reach - 1e-6 || Math.abs(a.y - b.y) >= reach - 1e-6, `${a.id} and ${b.id} overlap`).toBe(true);
    }
  }
  // Negative: earlier units stay where their run put them; the engine agrees.
  for (const l of all) {
    const item = s.items.find((it) => it.id === l.id);
    expect(item.x).toBeCloseTo(l.x, 6);
    expect(item.y).toBeCloseTo(l.y, 6);
    expect(item.location[0]).toBeCloseTo(l.x, 4);
    expect(item.location[1]).toBeCloseTo(l.y, 4);
  }
  expect(problems).toEqual([]);
});

for (const [how, act] of [
  ['cancel', (page) => page.locator('#add-all-no').click()],
  ['Escape', (page) => page.keyboard.press('Escape')],
]) {
  test(`negative: add all, then ${how}, adds nothing`, async ({ page }) => {
    const problems = watch(page);
    await open(page);
    await filterFew(page);
    await page.locator('#add-all').click();
    await expect(page.locator('#add-all-dialog')).toBeVisible();
    await act(page);
    await expect(page.locator('#add-all-dialog')).toBeHidden();
    await page.evaluate(() => new Promise((resolve) => setTimeout(resolve, 300)));
    expect((await state(page)).items).toEqual([]);
    expect((await run(page)).asked).toBe(0);
    expect(problems).toEqual([]);
  });
}
