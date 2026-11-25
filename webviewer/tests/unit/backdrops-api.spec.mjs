import { test, expect } from '../fixtures.mjs';
import { api } from '../api.mjs';

// The backdrop route (SPEC-VIEWER 8): the skyboxes of the game. That the page
// shows and draws one: tests/e2e/ground-sky.spec.mjs.

test('the skybox list holds every skybox file of the game', async ({ request }) => {
  const body = await (await request.get(api.backdrops('limit=500'))).json();
  expect(body.total).toBeGreaterThanOrEqual(60);
  expect(body.items).toHaveLength(body.total);
  // Like every list route, a request with no limit gets the first 60 (SPEC-VIEWER 8).
  const first = await (await request.get(api.backdrops())).json();
  expect(first.total).toBe(body.total);
  expect(first.items).toEqual(body.items.slice(0, 60));
  const ids = body.items.map((s) => s.id);
  expect(new Set(ids).size).toBe(ids.length);
  const aiur = body.items.find((s) => s.id === 'AiurSkybox');
  expect(aiur).toMatchObject({ name: 'Aiur Skybox', model: 'AiurSkybox' });
  expect(aiur.file.toLowerCase()).toMatch(/assets\\skyboxes\\aiurskybox\\aiurskybox\.m3$/);
  // Negative: the map's AiurSkyboxFlipped model names a file that only the
  // map build creates (scripts/skybox_flip.py); with no file it is not listed.
  expect(ids).not.toContain('AiurSkyboxFlipped');
  for (const sky of body.items) expect(sky.file.toLowerCase()).toMatch(/\\assets\\skyboxes\\.+\.m3$/);
  // A listed file is a real M3.
  const file = await request.get(api.file(aiur.file));
  expect((await file.body()).subarray(0, 4).toString('latin1')).toBe('43DM');
  // Search narrows it.
  const char = await (await request.get(api.backdrops('q=char'))).json();
  expect(char.items.length).toBeGreaterThan(0);
  expect(char.items.every((s) => (s.name + ' ' + s.id).toLowerCase().includes('char'))).toBe(true);
});
