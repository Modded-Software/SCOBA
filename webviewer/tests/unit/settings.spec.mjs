import { test, expect } from '../fixtures.mjs';
import { source } from './source.mjs';

// The stored settings (src/page/core/settings.ts, SPEC-VIEWER 10.3, R-VIEW-73),
// without a browser: each key's check, and what refusedSettings and
// clearRefused do with a store. That a refusal stops the start with the panel
// is tests/e2e/settings-refused.spec.mjs.

const settings = () => source('src/page/core/settings.ts');

/** A localStorage of its own for one test: the same calls the page uses. */
function useStore(entries = {}) {
  const map = new Map(Object.entries(entries));
  globalThis.localStorage = {
    get length() {
      return map.size;
    },
    key: (i) => [...map.keys()][i] ?? null,
    getItem: (k) => (map.has(k) ? map.get(k) : null),
    setItem: (k, v) => {
      map.set(k, String(v));
    },
    removeItem: (k) => {
      map.delete(k);
    },
  };
  return map;
}

/** The reason `text` is refused under `key`, or null: it is not. */
async function reasonOf(key, text) {
  const { refusedSettings } = await settings();
  useStore({ [key]: text });
  const refused = refusedSettings();
  expect(refused.length, `${key} ${text}`).toBeLessThanOrEqual(1);
  return refused.length ? refused[0].reason : null;
}

const MARK = { id: 1, name: 'x', yaw: 0, pitch: 0, distance: 9, target: [0, 0, 0] };
const SKY = { id: 'sky1', name: 'Sky', file: 'a.m3', game: 'sc2', dataset: 'scoba' };
const GROUND = { game: 'sc2', dataset: 'scoba', category: 'terrain', id: 'Dirt', name: 'Dirt', texture: 'dirt.dds' };

// [key, stored text, reason (a pattern), or null: it is good]
const CASES = [
  ['viewer.camera', 'not json', /JSON/],
  ['viewer.camera', JSON.stringify({ yaw: 1, pitch: 0.5, distance: -3, target: [0, 0, 0] }), /^the camera has distance -3$/],
  ['viewer.camera', JSON.stringify({ yaw: 'x', pitch: 0.5, distance: 9, target: [0, 0, 0] }), /^the camera is not a view$/],
  ['viewer.camera', JSON.stringify({ yaw: 1, pitch: 0.5, distance: 9, target: [0, 0] }), /^the camera: the target is not 3 numbers$/],
  ['viewer.camera', JSON.stringify({ yaw: 1, pitch: 0.5, distance: 9 }), /^the camera: no "target"$/],
  ['viewer.camera', JSON.stringify({ yaw: 1, pitch: 0.5, distance: 9, target: [0, 0, 0], roll: 0 }), /^the camera: unknown key "roll"$/],
  ['viewer.camera', JSON.stringify({ yaw: 0.7, pitch: 0.9, distance: 31, target: [12, -5, 0] }), null],
  ['viewer.landmarks', JSON.stringify({ list: [{ ...MARK, distance: -1 }], selected: null }), /distance -1/],
  ['viewer.landmarks', JSON.stringify({ list: 'no', selected: null }), /^no landmark list$/],
  ['viewer.landmarks', JSON.stringify({ list: [MARK], selected: 5 }), /^the chosen landmark 5 is not one of them$/],
  ['viewer.landmarks', JSON.stringify({ list: [MARK], selected: 1, extra: true }), /^the landmarks: unknown key "extra"$/],
  ['viewer.landmarks', JSON.stringify({ list: [MARK, MARK], selected: null }), /^an id is used twice$/],
  ['viewer.landmarks', JSON.stringify({ list: [{ ...MARK, id: 0 }], selected: null }), /^not a landmark$/],
  ['viewer.landmarks', JSON.stringify({ list: [MARK], selected: 1 }), null],
  ['viewer.landmarks', JSON.stringify({ list: [MARK], selected: 0 }), null],
  ['viewer.view', JSON.stringify({ grid: true, sky: null }), /^the view: no "ground"$/],
  ['viewer.view', JSON.stringify({ grid: 'yes', sky: null, ground: null }), /^no grid setting$/],
  ['viewer.view', JSON.stringify({ grid: true, sky: { ...SKY, game: 'Bad Id' }, ground: null }), /^the backdrop names no game and dataset$/],
  ['viewer.view', JSON.stringify({ grid: true, sky: null, ground: { ...GROUND, texture: '' } }), /^the ground is not a ground record$/],
  ['viewer.view', JSON.stringify({ grid: false, sky: SKY, ground: GROUND }), null],
  ['viewer.drawers', JSON.stringify({ gallery: true, instances: 1 }), /^not two drawer flags$/],
  ['viewer.drawers', JSON.stringify({ gallery: true, instances: false }), null],
  ['viewer.edits.offered', JSON.stringify({ 'NOT-A-SESSION': '{}' }), /^"NOT-A-SESSION" is not an edit session$/],
  ['viewer.edits.offered', JSON.stringify({ '0123456789abcdef': 7 }), /^the offered planes of 0123456789abcdef are not text$/],
  ['viewer.edits.offered', JSON.stringify({ '0123456789abcdef': '{"color":"aa"}' }), null],
  ['viewer.game', '42', /^not a game id$/],
  ['viewer.game', '"ghost"', null],
  ['viewer.scene', '42', /^not a scene id$/],
  ['viewer.scene', 'not json', /JSON/],
  ['viewer.scene', '"s-abc123"', null],
  ['viewer.dataset.sc2', '"Bad Id"', /^not a dataset id$/],
  ['viewer.dataset.sc2', '"fx"', null],
  ['viewer.dataset.Bad Game', '"fx"', /^the page has no such setting$/],
  ['viewer.nosuch', '1', /^the page has no such setting$/],
];

test('each stored key is checked: a bad value names its fault; a good one is not refused (negative)', async () => {
  for (const [key, text, reason] of CASES) {
    const got = await reasonOf(key, text);
    if (reason === null) expect(got, `${key} ${text}`).toBeNull();
    else expect(got, `${key} ${text}`).toMatch(reason);
  }
});

test('refused keys are listed sorted with their stored text; keys of another page are not looked at', async () => {
  const { refusedSettings } = await settings();
  useStore({
    'viewer.view': JSON.stringify({ grid: true, sky: null }),
    'viewer.nosuch': '1',
    'viewer.camera': 'not json',
    'viewer.drawers': JSON.stringify({ gallery: true, instances: false }),
    'other.thing': 'x',
    'sc2viewer.camera': 'not json',
  });
  const refused = refusedSettings();
  expect(refused.map((r) => r.key)).toEqual(['viewer.camera', 'viewer.nosuch', 'viewer.view']);
  expect(refused[1]).toEqual({ key: 'viewer.nosuch', stored: '1', reason: 'the page has no such setting' });
});

test('Clear removes exactly the keys named; a key not of the page is refused', async () => {
  const { clearRefused } = await settings();
  const store = useStore({ 'viewer.camera': 'x', 'viewer.drawers': 'y', 'other.thing': 'z' });
  clearRefused(['viewer.camera']);
  expect([...store.keys()].sort()).toEqual(['other.thing', 'viewer.drawers']);
  expect(() => clearRefused(['other.thing'])).toThrow('"other.thing" is not a key of the page');
  expect(store.get('other.thing'), 'negative: nothing of another page is removed').toBe('z');
});

test('nothing stored reads the declared default; the key used before the settings module is not read', async () => {
  const { readSetting, findSetting, settings: all } = await settings();
  useStore({ 'sc2viewer.camera': JSON.stringify({ yaw: 0.7, pitch: 0.9, distance: 31, target: [12, -5, 0] }) });
  expect(readSetting(all.camera)).toEqual({ yaw: -Math.PI / 2, pitch: 0.5, distance: 9, target: [0, 0, 0.8] });
  expect(findSetting(all.game), 'negative: a setting without a default reads none').toBeNull();
  // The default is a copy: a change to what was read is not the default.
  readSetting(all.camera).target[0] = 99;
  expect(readSetting(all.camera).target[0]).toBe(0);
});

test('a written value reads back; a value that could not be read back is not written', async () => {
  const { readSetting, writeSetting, settings: all } = await settings();
  const store = useStore();
  const view = { yaw: 0.7, pitch: 0.9, distance: 31, target: [12, -5, 0] };
  writeSetting(all.camera, view);
  expect(readSetting(all.camera)).toEqual(view);
  expect(() => writeSetting(all.camera, { ...view, distance: 0 })).toThrow('distance 0');
  expect(JSON.parse(store.get('viewer.camera')), 'negative: the good value stays').toEqual(view);
});
