import { test, expect } from '@playwright/test';

// Batch draw order (gap G2): opaque batches first in file order, then
// blended batches by material priority ascending (higher on top), equal
// priorities in file order. Rule: WhiteoutFlakes TransparentOrder (ref
// draworder.ts). Survey: scripts/priority-survey.sh. The order checked is
// the one the last frame issued (M3ModelInstance.drawnOrder).

async function open(page) {
  const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.text().startsWith('viewer:') || m.type() === 'error') errors.push(m.text());
  });
  await page.goto('/');
  await expect.poll(() => errors.join(' | ') || page.evaluate(() => Boolean(window.sc2viewer && window.sc2viewer.ready)), { timeout: 10_000 }).toBe(true);
  return errors;
}

async function drawn(page, id) {
  await page.evaluate((u) => window.sc2viewer.addUnit(u, { x: 0, y: 0 }), id);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 15_000 });
  await page.evaluate(() => new Promise((resolve) => setTimeout(resolve, 200)));
  const item = (await page.evaluate(() => window.sc2viewer.state())).items.at(-1);
  expect(item.loaded).toBe(true);
  expect(item.drawn).toBe(true);
  console.log(`${id}: ` + item.drawOrder.map((d) => `#${d.fileOrder} ${d.material} blend ${d.blendMode} prio ${d.priority}`).join(' | '));
  return item.drawOrder;
}

/** The rule, checked on an issued order. */
function expectRule(order) {
  // Every batch drawn once.
  expect([...order.map((d) => d.fileOrder)].sort((a, b) => a - b)).toEqual(order.map((_, i) => i));
  const firstBlended = order.findIndex((d) => d.blendMode !== 0);
  const opaque = firstBlended < 0 ? order : order.slice(0, firstBlended);
  const blended = firstBlended < 0 ? [] : order.slice(firstBlended);
  // No opaque batch after a blended one.
  for (const d of blended) expect(d.blendMode, `#${d.fileOrder} after the first blended batch`).not.toBe(0);
  // Opaque in file order.
  for (let i = 1; i < opaque.length; i++) expect(opaque[i].fileOrder).toBeGreaterThan(opaque[i - 1].fileOrder);
  // Blended by priority, ties in file order.
  for (let i = 1; i < blended.length; i++) {
    const [a, b] = [blended[i - 1], blended[i]];
    expect(b.priority).toBeGreaterThanOrEqual(a.priority);
    if (a.priority === b.priority) expect(b.fileOrder).toBeGreaterThan(a.fileOrder);
  }
  return { opaque, blended };
}

test('Nexus: blended batches stored at priorities 2, 4, 0 are drawn 0, 2, 4', async ({ page }) => {
  const errors = await open(page);
  const order = await drawn(page, 'Nexus');
  const { blended } = expectRule(order);
  expect(blended.map((d) => d.priority)).toEqual([0, 2, 4]);
  // The file had them in another order: the sort did something.
  expect(blended.map((d) => d.fileOrder)).not.toEqual([...blended.map((d) => d.fileOrder)].sort((a, b) => a - b));
  expect(errors).toEqual([]);
});

test('Probe: an opaque batch stored after a blended one is drawn before it', async ({ page }) => {
  const errors = await open(page);
  const order = await drawn(page, 'Probe');
  const { opaque, blended } = expectRule(order);
  expect(blended.map((d) => d.priority)).toEqual([0, 1]);
  // Some opaque batch comes later in the file than some blended batch.
  expect(Math.max(...opaque.map((d) => d.fileOrder))).toBeGreaterThan(Math.min(...blended.map((d) => d.fileOrder)));
  expect(errors).toEqual([]);
});

for (const [id, priorities] of [
  ['ForceField', [5, 10, 10]],
  ['Marine', []],
]) {
  test(`negative: ${id}, already in order, is drawn in file order`, async ({ page }) => {
    const errors = await open(page);
    const order = await drawn(page, id);
    const { blended } = expectRule(order);
    expect(blended.map((d) => d.priority)).toEqual(priorities);
    // Nothing moved, the tie at 10 included.
    expect(order.map((d) => d.fileOrder)).toEqual(order.map((_, i) => i));
    expect(errors).toEqual([]);
  });
}
