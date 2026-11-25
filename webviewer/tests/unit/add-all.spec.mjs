import { test, expect } from '../fixtures.mjs';
import { source } from './source.mjs';

// "add all" without a browser: the layout (src/page/features/addall/layout.ts)
// on items of known sizes, and the landmark names of the SC2 lists
// (src/games/sc2/page/names.ts). That the page adds the units, the engine
// stands them where the layout put them, and the camera frames the block:
// tests/e2e/add-all.spec.mjs and landmarks.spec.mjs.

const GAP = 0.5; // layout.ts
const layout = () => source('src/page/features/addall/layout.ts');

let nextId = 1;
/** An item of ground size `size` (bounds diameter x data scale x scale), at the origin. */
const item = (size, { scale = 1, data = [1, 1, 1], x = 0, y = 0 } = {}) => ({
  id: nextId++,
  x,
  y,
  scale,
  model: { bounds: { r: size / 2 / Math.max(data[0], data[1]) / scale } },
  placement: { scale: data },
});
const scene = { setPosition: (it, x, y) => Object.assign(it, { x, y }) };

/** The ground box of layout cells, each a square of its size. */
const box = (cells) => ({
  x0: Math.min(...cells.map((l) => l.x - l.size / 2)),
  x1: Math.max(...cells.map((l) => l.x + l.size / 2)),
  y0: Math.min(...cells.map((l) => l.y - l.size / 2)),
  y1: Math.max(...cells.map((l) => l.y + l.size / 2)),
});

function expectNoOverlap(cells) {
  for (let i = 0; i < cells.length; i++) {
    for (let j = i + 1; j < cells.length; j++) {
      const [a, b] = [cells[i], cells[j]];
      const reach = (a.size + b.size) / 2;
      expect(Math.abs(a.x - b.x) >= reach - 1e-9 || Math.abs(a.y - b.y) >= reach - 1e-9, `${a.id} and ${b.id} overlap`).toBe(true);
    }
  }
}

test('smallest first; the size is the bounds diameter as drawn; each item stands where its cell is; no overlap', async () => {
  const { arrange } = await layout();
  const list = [item(3), item(1, { scale: 2 }), item(2, { data: [1.5, 1, 1] }), item(1)];
  const cells = arrange(scene, list);
  expect(cells.map((l) => l.size)).toEqual([1, 1, 2, 3]);
  for (let i = 1; i < cells.length; i++) expect(cells[i].size).toBeGreaterThanOrEqual(cells[i - 1].size);
  for (const l of cells) expect(list.find((it) => it.id === l.id)).toMatchObject({ x: l.x, y: l.y });
  expectNoOverlap(cells);
  // On an empty scene the block is around the origin.
  const b = box(cells);
  expect(b.x0 < 0 && b.x1 > 0 && b.y0 < 0 && b.y1 > 0).toBe(true);
});

test('size outliers get clusters of their own: at most three, in size order, each cell its largest size plus the gap', async () => {
  const { arrange } = await layout();
  // Like Melee Zerg: many about 4.6, an Overlord of 85, a Hive of 158.
  const sizes = [...Array(40)].map((_, i) => 3 + (i % 7) * 0.5).concat([85, 158]);
  const cells = arrange(scene, sizes.map((s) => item(s)));
  const ks = cells.map((l) => l.cluster);
  for (let j = 1; j < ks.length; j++) expect(ks[j]).toBeGreaterThanOrEqual(ks[j - 1]);
  const clusters = [...new Set(ks)];
  expect(clusters.length).toBeGreaterThanOrEqual(2);
  expect(clusters.length).toBeLessThanOrEqual(3);
  for (const k of clusters) {
    const members = cells.filter((l) => l.cluster === k);
    for (const l of members) expect(l.cell).toBeCloseTo(Math.max(...members.map((m) => m.size)) + GAP, 9);
  }
  // Negative: the largest does not set the cell of the smallest cluster.
  expect(cells[0].cell).toBeLessThan(158 / 4);
  // Least area: less than one grid of the largest cell.
  const area = clusters.reduce((sum, k) => {
    const members = cells.filter((l) => l.cluster === k);
    return sum + members.length * members[0].cell ** 2;
  }, 0);
  expect(area).toBeLessThan(cells.length * (158 + GAP) ** 2);
  expectNoOverlap(cells);
});

test('negative: equal sizes make one cluster; no item makes no layout', async () => {
  const { arrange } = await layout();
  const cells = arrange(scene, [item(2), item(2), item(2), item(2)]);
  expect(new Set(cells.map((l) => l.cluster))).toEqual(new Set([0]));
  // A near-square grid: 4 items, 2 x 2.
  expect(new Set(cells.map((l) => l.x)).size).toBe(2);
  expect(new Set(cells.map((l) => l.y)).size).toBe(2);
  expect(arrange(scene, [])).toEqual([]);
});

test('with units already there the block goes next to them, a gap away: below a wide footprint, right of a deep one; they do not move', async () => {
  const { arrange } = await layout();
  for (const [others, side] of [
    [[item(2, { x: -10, y: 0 }), item(2, { x: 10, y: 0 })], 'below'],
    [[item(2, { x: 0, y: -10 }), item(2, { x: 0, y: 10 })], 'right'],
  ]) {
    const before = others.map((o) => [o.x, o.y]);
    const cells = arrange(scene, [item(1), item(1.5), item(3)], others);
    expect(others.map((o) => [o.x, o.y]), 'negative: the others stay').toEqual(before);
    const old = box(others.map((o) => ({ id: o.id, x: o.x, y: o.y, size: 2 })));
    const add = box(cells);
    const below = old.y0 - add.y1;
    const right = add.x0 - old.x1;
    if (side === 'below') {
      expect(below, side).toBeGreaterThanOrEqual(GAP - 1e-9);
      expect(below, side).toBeLessThanOrEqual(3 * GAP);
      expect(add.x0 < old.x1 && add.x1 > old.x0, 'lined up on x').toBe(true);
    } else {
      expect(right, side).toBeGreaterThanOrEqual(GAP - 1e-9);
      expect(right, side).toBeLessThanOrEqual(3 * GAP);
      expect(add.y0 < old.y1 && add.y1 > old.y0, 'lined up on y').toBe(true);
    }
  }
});

test('three runs in a row stay together and never overlap', async () => {
  const { arrange } = await layout();
  const placed = [];
  const cells = [];
  for (let run = 0; run < 3; run++) {
    const list = [item(1), item(2), item(2.5), item(4)];
    const made = arrange(scene, list, placed);
    cells.push(...made);
    placed.push(...list);
  }
  expectNoOverlap(cells);
  // Together: the whole is no wider and no deeper than three blocks side by side plus gaps.
  const all = box(cells);
  const one = box(cells.slice(0, 4));
  expect(all.x1 - all.x0).toBeLessThanOrEqual(3 * (one.x1 - one.x0) + 3 * GAP);
  expect(all.y1 - all.y0).toBeLessThanOrEqual(3 * (one.y1 - one.y0) + 3 * GAP);
});

test('landmark names from the filters: race, family, kind as a plural, then the search', async () => {
  const { filterName, listName } = await source('src/games/sc2/page/names.ts');
  const cases = [
    [{}, 'All Units'],
    [{ q: '', race: '', kind: '' }, 'All Units'],
    [{ q: '', race: 'Terran', kind: 'Unit', family: 'Campaign' }, 'Terran Campaign Units'],
    [{ q: '', race: 'Zerg', kind: '', family: 'Melee' }, 'Zerg Melee Units'],
    [{ q: 'drone', race: 'Zerg', kind: 'Unit', family: 'Melee' }, 'Zerg Melee Units "drone"'],
    [{ q: '', race: '', kind: 'Structure', family: '' }, 'Structures (no family)'],
    [{ q: '', race: 'Protoss', kind: 'Hero' }, 'Protoss Heroes'],
    [{ q: '', race: '', kind: 'Other' }, 'Other Units'],
    [{ q: 'zergling', race: '', kind: '', family: 'Melee' }, 'Melee Units "zergling"'],
  ];
  for (const [query, name] of cases) expect(filterName(query), JSON.stringify(query)).toBe(name);
  expect(listName('units', { race: 'Zerg', family: 'Melee', q: 'drone' })).toBe('Zerg Melee Units "drone"');
  expect(listName('doodads', {})).toBe('All Doodads');
  expect(listName('doodads', { tileset: 'Char', type: 'Environment', q: 'rock' })).toBe('Char Environment Doodads "rock"');
  expect(listName('terrain', { q: 'dirt' })).toBe('terrain "dirt"');
  expect(listName('terrain', {})).toBe('All terrain');
});
