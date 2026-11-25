import { readFile, utimes, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { api } from '../api.mjs';
import { test, expect, ownServer } from '../fixtures.mjs';

// A dataset whose files changed on disk, as the server sees it (SPEC-VIEWER
// 8, R-VIEW-34): the datasets route marks it changed, and only it; the reload
// route rebuilds it from the files, and the change is gone. The server has a
// datasets copy of its own (ownServer): the edit is not put back. The toast
// the page shows: tests/e2e/datasets-toast.spec.mjs.

test.describe.configure({ mode: 'serial', timeout: 300_000 });

let server;
const get = async (path) => (await fetch(`${server.url}${path}`)).json();
const datasets = async () => (await get(api.datasets)).datasets;
const scale = async (dataset) => (await get(api.record('units', 'Marine', dataset))).actorScale;

test.beforeAll(async ({ worker }, testInfo) => {
  server = await ownServer(worker, testInfo.parallelIndex, 'dataset-change');
});

test.afterAll(async () => {
  if (server) await server.stop();
});

test('a changed file marks its dataset changed, and no other; a reload reads it and the mark goes', async () => {
  const file = join(server.datasets, 'fx', 'map', 'Base.SC2Data', 'GameData', 'ActorData.xml');
  const original = await readFile(file, 'utf8');
  expect(original).toContain('<Scale value="2.000000"/>');
  // Negative: nothing changed, nothing marked.
  expect((await datasets()).map((d) => d.changed)).toEqual([false, false, false]);
  expect(await scale('fx')).toEqual([2, 2, 2]);

  await writeFile(file, original.replace('<Scale value="2.000000"/>', '<Scale value="4.000000"/>'));
  const when = new Date('2026-03-03T00:00:00');
  await utimes(file, when, when);
  await expect.poll(async () => (await datasets()).find((d) => d.id === 'fx').changed).toBe(true);
  // Negative: the others did not change, and a changed dataset still answers its old data until reloaded.
  expect((await datasets()).filter((d) => d.id !== 'fx').map((d) => d.changed)).toEqual([false, false]);
  expect(await scale('fx')).toEqual([2, 2, 2]);

  const reloaded = await fetch(`${server.url}${api.reload('fx')}`, { method: 'POST' });
  expect(reloaded.status, await reloaded.text()).toBe(200);
  expect(await scale('fx')).toEqual([4, 4, 4]);
  expect((await datasets()).find((d) => d.id === 'fx').changed).toBe(false);
  // Negative: another dataset kept its data.
  expect(await scale('stock')).toEqual([1, 1, 1]);
});
