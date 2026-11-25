import { test, expect } from '../fixtures.mjs';
import { api } from '../api.mjs';
import { frames, idle, open, state } from '../page.mjs';

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

const units = async (page, query) => (await page.request.get(api.records('units', { limit: '500', ...query }))).json();
const run = (page) => page.evaluate(() => window.SC2App.addAllState());
const count = (page) => page.locator('#count-units').textContent();

test('ui: the family select filters the list, and "any family" takes the filter off', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const all = await units(page, {});
  await expect.poll(() => count(page)).toBe(`${all.total} units`);
  await page.selectOption('#filter-units-family', 'is:Melee');
  const melee = await units(page, { family: 'Melee' });
  await expect.poll(() => count(page)).toBe(`${melee.total} units`);
  // With race Zerg on top.
  await page.locator('#filter-units-race button[data-race="Zerg"]').click();
  const zerg = await units(page, { family: 'Melee', race: 'Zerg' });
  await expect.poll(() => count(page)).toBe(`${zerg.total} units`);
  // Negative: back to any family.
  await page.locator('#filter-units-race button[data-race=""]').click();
  await page.selectOption('#filter-units-family', 'any');
  await expect.poll(() => count(page)).toBe(`${all.total} units`);
  expect(problems).toEqual([]);
});

/** Filter the list to a few Melee units: search "zergling". */
async function filterFew(page) {
  await page.selectOption('#filter-units-family', 'is:Melee');
  await page.fill('#search-units', 'zergling');
  const listed = await units(page, { family: 'Melee', q: 'zergling' });
  await expect.poll(() => count(page)).toBe(`${listed.total} units`);
  expect(listed.total).toBeGreaterThan(1);
  return listed;
}

test('add all: the dialog asks with the count; "add" adds every listed unit, laid out by size', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const listed = await filterFew(page);
  await page.locator('#add-all-units').click();
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
  // The layout got the loaded models: each size is the drawn bounds diameter
  // from what the renderer holds, and the engine stands the unit where the
  // layout put it. The layout's rule: tests/unit/add-all.spec.mjs.
  for (const l of r.layout) {
    const item = s.items.find((i) => i.id === l.id);
    expect(l.size).toBeCloseTo(2 * item.boundsRadius * Math.max(item.dataScale[0], item.dataScale[1]) * item.scale, 4);
    expect(item.location[0]).toBeCloseTo(l.x, 4);
    expect(item.location[1]).toBeCloseTo(l.y, 4);
  }
  expect(problems).toEqual([]);
});

/** Click "add all", confirm, wait for the run and the loads; the run state. */
async function addAllRun(page, total) {
  await page.locator('#add-all-units').click();
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

test('add all again: the new block is laid out beside the units already on the map; nothing moves', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  const listed = await filterFew(page);
  const runs = [];
  for (let i = 0; i < 2; i++) {
    const r = await addAllRun(page, listed.total);
    expect(r.failed).toEqual([]);
    runs.push(r.layout);
  }
  const s = await state(page);
  expect(s.items.length).toBe(2 * listed.total);
  // The second run was given the first block: their boxes do not meet.
  // Where beside them it goes: tests/unit/add-all.spec.mjs.
  const [old, add] = runs.map(box);
  expect(add.x0 >= old.x1 || add.x1 <= old.x0 || add.y0 >= old.y1 || add.y1 <= old.y0).toBe(true);
  // Negative: earlier units stay where their run put them; the engine agrees.
  const all = runs.flat();
  for (const l of all) {
    const item = s.items.find((it) => it.id === l.id);
    expect(item.x).toBeCloseTo(l.x, 6);
    expect(item.y).toBeCloseTo(l.y, 6);
    expect(item.location[0]).toBeCloseTo(l.x, 4);
    expect(item.location[1]).toBeCloseTo(l.y, 4);
  }
  expect(problems).toEqual([]);
});

test('negative: add all, then cancel or Escape, adds nothing', async ({ page }) => {
  const problems = watch(page);
  await open(page);
  await filterFew(page);
  for (const [how, act] of [
    ['cancel', () => page.locator('#add-all-no').click()],
    ['Escape', () => page.keyboard.press('Escape')],
  ]) {
    await page.locator('#add-all-units').click();
    await expect(page.locator('#add-all-dialog'), how).toBeVisible();
    await act();
    await expect(page.locator('#add-all-dialog'), how).toBeHidden();
    // The page has handled the answer and loads nothing.
    await frames(page);
    await idle(page);
    expect((await state(page)).items, how).toEqual([]);
    expect((await run(page)).asked, how).toBe(0);
  }
  expect(problems).toEqual([]);
});
