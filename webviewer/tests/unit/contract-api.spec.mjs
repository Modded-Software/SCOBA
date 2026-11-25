// The contract tests (SPEC-VIEWER 11, R-VIEW-91), protocol part: one suite,
// run once for every game /api/games lists as available. Each game answers
// every shared route in its shape; paging walks a list without repeats; an
// unknown id, category or dataset gives 404. Nothing here names a game's own
// records or files. A game not available is skipped with its reason
// (ghost-unavailable.spec covers that case). The page part is
// e2e/contract.spec.mjs.
import { test, expect } from '../fixtures.mjs';

const PAGE = 7;

const get = async (request, url) => {
  const response = await request.get(url);
  expect(response.status(), url).toBe(200);
  return response.json();
};

test('protocol: every available game answers the shared routes in their shapes', async ({ request }) => {
  const { games } = await get(request, '/api/games');
  const available = games.filter((g) => g.available);
  expect(available.length, 'two games under test (R-VIEW-91)').toBeGreaterThanOrEqual(2);
  for (const g of games.filter((x) => !x.available)) console.log(`contract: ${g.id} skipped: ${g.reason}`);
  for (const { id: game } of available) {
    const datasets = await get(request, `/api/${game}/datasets`);
    expect(datasets.datasets.map((d) => d.id), game).toContain(datasets.default);
    const dataset = datasets.default;
    const categories = await get(request, `/api/${game}/categories?${new URLSearchParams({ dataset })}`);
    expect(categories.length, game).toBeGreaterThan(0);
    for (const c of categories) {
      expect(Object.keys(c).sort(), `${game} ${c.id}`).toEqual(expect.arrayContaining(['id', 'label', 'noun', 'rows', 'filters']));
      if (c.rows !== 'records') continue;
      // Paging: three pages, no id twice, each page the size asked while the list lasts.
      const seen = new Set();
      let total = null;
      for (let offset = 0; offset < PAGE * 3; offset += PAGE) {
        const page = await get(request, `/api/${game}/records/${c.id}?${new URLSearchParams({ dataset, offset: String(offset), limit: String(PAGE) })}`);
        total ??= page.total;
        expect(page.total, `${game} ${c.id}: the total does not change between pages`).toBe(total);
        expect(page.items.length).toBe(Math.max(0, Math.min(PAGE, total - offset)));
        for (const row of page.items) {
          expect(typeof row.id === 'string' && typeof row.name === 'string' && typeof row.placeable === 'boolean', JSON.stringify(row)).toBe(true);
          expect(seen.has(row.id), `${game} ${c.id}: ${row.id} twice`).toBe(false);
          seen.add(row.id);
        }
      }
      const [one] = seen;
      if (one !== undefined) {
        const body = await get(request, `/api/${game}/record/${c.id}?${new URLSearchParams({ dataset, id: one })}`);
        expect([body.id, body.dataset], `${game} ${c.id}`).toEqual([one, dataset]);
      }
      // Negative: an unknown id is 404.
      expect((await request.get(`/api/${game}/record/${c.id}?${new URLSearchParams({ dataset, id: 'no-such-record-xyzzy' })}`)).status(), game).toBe(404);
    }
    // Negative: an unknown category and an unknown dataset are 404.
    expect((await request.get(`/api/${game}/records/no-such-category?${new URLSearchParams({ dataset })}`)).status(), game).toBe(404);
    expect((await request.get(`/api/${game}/categories?dataset=no-such-dataset`)).status(), game).toBe(404);
  }
});
