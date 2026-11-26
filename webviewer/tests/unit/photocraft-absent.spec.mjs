// PhotoCraft not installed (R-PC-13, SPEC-PHOTOCRAFT 7): a second server,
// started with PHOTOCRAFT_HOME naming a folder that is not there, starts, says
// so in its health answer, serves no editor site, and answers every edit
// route with 503 and the reason. The other routes still answer.
import { join } from 'node:path';
import { test, expect, ownServer } from '../fixtures.mjs';

test.describe.configure({ mode: 'serial', timeout: 180_000 });

let server;
let home;

test.beforeAll(async ({ worker }, testInfo) => {
  home = join(worker.root, 'no-photocraft-home');
  server = await ownServer(worker, testInfo.parallelIndex, 'no-photocraft', { PHOTOCRAFT_HOME: home });
});

test.afterAll(async () => {
  if (server) await server.stop();
});

test('the health answer says there is no install and names the command; the editor site answers 404', async () => {
  const health = await (await fetch(`${server.url}/api/health`)).json();
  expect(health.photocraft.installed).toBe(false);
  expect(health.photocraft.pins).toEqual([]);
  expect(health.photocraft.reason).toContain(home);
  expect(health.photocraft.reason).toContain('make install-photocraft');
  for (const path of ['/photocraft/', '/photocraft/index.html']) expect((await fetch(`${server.url}${path}`)).status, path).toBe(404);
});

test('every edit route answers 503 with the reason; the texture routes still answer', async () => {
  const query = new URLSearchParams({ dataset: 'stock' });
  const routes = [
    ['GET', `/api/sc2/textures/edit?${query}`],
    ['POST', `/api/sc2/textures/edit/open?${query}`],
    ['GET', `/api/sc2/textures/edit/0123456789abcdef?${query}`],
    ['GET', '/api/sc2/textures/edit/0123456789abcdef/scratch'],
    ['PUT', '/api/sc2/textures/edit/0123456789abcdef/scratch'],
    ['POST', `/api/sc2/textures/edit/0123456789abcdef/transfer?${query}`],
    ['POST', `/api/sc2/textures/edit/0123456789abcdef/discard?${query}`],
    // Ghost has the texture service too (R-VIEW-152): its edit routes are held back the same way.
    ['GET', '/api/ghost/textures/edit?dataset=build'],
  ];
  for (const [method, route] of routes) {
    const answer = await fetch(`${server.url}${route}`, { method, ...(method === 'GET' ? {} : { body: '{}', headers: { 'content-type': 'application/json' } }) });
    expect(answer.status, `${method} ${route}`).toBe(503);
    const body = await answer.json();
    expect(body.error).toBe('PhotoCraft is not installed');
    expect(body.reason).toContain('make install-photocraft');
  }
  // Negative: the other routes of the texture service are not held back.
  const states = await fetch(`${server.url}/api/sc2/textures?${new URLSearchParams({ dataset: 'stock', asset: 'assets\\textures\\marine_diffuse_blood.dds' })}`);
  expect(states.status).toBe(200);
  // Negative: a game the server does not have answers 404, not 503.
  expect((await fetch(`${server.url}/api/nogame/textures/edit?dataset=build`)).status).toBe(404);
});
