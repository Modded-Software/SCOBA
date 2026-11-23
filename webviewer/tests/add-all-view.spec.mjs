import { test, expect } from '@playwright/test';
import { api } from './api.mjs';

// "add all" on a large list with size outliers (Melee Zerg: Hive 158,
// Overlord 85, median 4.6): size clusters, each with its own cell
// (src/page/features/addall/layout.ts clusterStarts). Also records, per run, the block's ground box,
// the camera, and how many new units stand in the uncovered part of the
// canvas (operator 2026-11-21: "once they load in the units disappear"):
// after each run the camera frames the new block, so all of them.

const run = (page) => page.evaluate(() => window.SC2App.addAllState());

async function addAllRun(page, total) {
  await page.locator('#add-all').click();
  await page.locator('#add-all-yes').click();
  await expect.poll(async () => {
    const r = await run(page);
    return r.running === false && r.asked === total && r.added + r.failed.length === total;
  }, { timeout: 120_000 }).toBe(true);
  await page.waitForFunction(() => window.sc2viewer.idle(), null, { timeout: 120_000 });
  return run(page);
}

/** Of these item ids: how many stand (ground point) in the part of the canvas no panel covers, and the camera. */
const onCanvas = (page, ids) => page.evaluate((list) => {
  const v = window.sc2viewer;
  const box = window.SC2App.visibleRect();
  let inside = 0;
  for (const id of list) {
    const p = v.itemScreen(id, 0);
    if (p && p[0] >= box.left && p[0] <= box.right && p[1] >= box.top && p[1] <= box.bottom) inside++;
  }
  const c = v.state().camera;
  return { inside, of: list.length, camera: { target: c.target.map((t) => +t.toFixed(2)), distance: +c.distance.toFixed(2) } };
}, ids);

test('two "add all" runs of Melee Zerg: size clusters, outliers alone, no overlap @slow', async ({ page }) => {
  test.setTimeout(300_000);
  await page.goto('/');
  await page.waitForFunction(() => window.sc2viewer && window.sc2viewer.ready);
  await page.selectOption('#family', 'is:Melee');
  await page.locator('#races button[data-race="Zerg"]').click();
  const listed = await (await page.request.get(api.records('units', { limit: '500', family: 'Melee', race: 'Zerg' }))).json();
  await expect.poll(() => page.locator('#unit-count').textContent()).toBe(`${listed.total} units`);
  for (let i = 1; i <= 2; i++) {
    const r = await addAllRun(page, listed.total);
    const xs = r.layout.map((l) => l.x);
    const ys = r.layout.map((l) => l.y);
    const seen = await onCanvas(page, r.layout.map((l) => l.id));
    if (i === 1) {
      const s = await page.evaluate(() => window.sc2viewer.state());
      const rows = r.layout.map((l) => {
        const it = s.items.find((x) => x.id === l.id);
        return [it.unit, +l.size.toFixed(1), +it.boundsRadius.toFixed(1)];
      });
      const sizes = rows.map((x) => x[1]).sort((a, b) => a - b);
      console.log(`sizes: median ${sizes[sizes.length >> 1]}, p90 ${sizes[Math.floor(sizes.length * 0.9)]}, max ${sizes.at(-1)}`);
      console.log('largest: ' + JSON.stringify(rows.sort((a, b) => b[1] - a[1]).slice(0, 12)));
      const radii = await page.evaluate((ids) => ids.map((id) => window.SC2App.items.find((x) => x.id === id)).map((x) => [x.unit.id, x.unit.radius]), r.layout.map((l) => l.id));
      console.log('unit radius of the largest: ' + JSON.stringify(radii.filter(([u]) => rows.slice(0, 12).some((x) => x[0] === u))));
    }
    const clusters = [...new Set(r.layout.map((l) => l.cluster))].map((k) => {
      const m = r.layout.filter((l) => l.cluster === k);
      return { n: m.length, cell: +m[0].cell.toFixed(1), sizes: `${Math.min(...m.map((l) => l.size)).toFixed(1)}..${Math.max(...m.map((l) => l.size)).toFixed(1)}` };
    });
    console.log(`run ${i}: clusters ${JSON.stringify(clusters)}`);
    console.log(`run ${i}: ${r.added} added, box x ${Math.min(...xs).toFixed(1)}..${Math.max(...xs).toFixed(1)} y ${Math.min(...ys).toFixed(1)}..${Math.max(...ys).toFixed(1)}; on canvas ${seen.inside} of ${seen.of}; camera ${JSON.stringify(seen.camera)}`);
    expect(r.failed).toEqual([]);
    // The camera frames the new block: every new unit is in view.
    expect(seen.inside).toBe(seen.of);

    // Size clusters (operator 2026-11-21): at most three, runs of the sizes
    // in ascending order, each cell its largest size plus the gap.
    const GAP = 0.5; // features/addall/layout.ts
    expect(clusters.length).toBeGreaterThanOrEqual(2);
    expect(clusters.length).toBeLessThanOrEqual(3);
    const ks = r.layout.map((l) => l.cluster);
    for (let j = 1; j < ks.length; j++) expect(ks[j]).toBeGreaterThanOrEqual(ks[j - 1]);
    for (const k of new Set(ks)) {
      const m = r.layout.filter((l) => l.cluster === k);
      for (const l of m) expect(l.cell).toBeCloseTo(Math.max(...m.map((x) => x.size)) + GAP, 6);
    }
    // Negative: the largest unit does not set the cell of the smallest cluster.
    const largest = Math.max(...r.layout.map((l) => l.size));
    const smallCell = r.layout.find((l) => l.cluster === 0).cell;
    expect(smallCell).toBeLessThan(largest / 4);
    // Least area: no single-cell grid (the old rule's worst case) is smaller.
    const area = [...new Set(ks)].reduce((sum, k) => {
      const m = r.layout.filter((l) => l.cluster === k);
      return sum + m.length * m[0].cell ** 2;
    }, 0);
    expect(area).toBeLessThan(r.layout.length * (largest + GAP) ** 2);
    // Negative: no two cells overlap.
    for (let a = 0; a < r.layout.length; a++) {
      for (let b = a + 1; b < r.layout.length; b++) {
        const [p, q] = [r.layout[a], r.layout[b]];
        const reach = (p.cell + q.cell) / 2 - GAP;
        expect(Math.abs(p.x - q.x) >= reach - 1e-6 || Math.abs(p.y - q.y) >= reach - 1e-6, `${p.id} and ${q.id} overlap`).toBe(true);
      }
    }
  }
});
