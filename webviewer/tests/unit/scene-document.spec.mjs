import { test, expect } from '../fixtures.mjs';
import { sceneItem, sceneText } from '../scene.mjs';
import { source } from './source.mjs';

// The scene document check (src/shared/scene.ts, SPEC-VIEWER 10.2), without a
// browser: every stored scene and every imported file passes it. That the
// page refuses an import and changes nothing is tests/e2e/scenes.spec.mjs.

const scene = () => source('src/shared/scene.ts');
const MARINE = sceneItem({ category: 'units', record: 'Marine', variant: null }, { x: 1, y: 2, rot: 30, sequence: 0, options: { team: 3, skin: 'hd' } });
const TREE = sceneItem({ category: 'doodads', record: 'ZerusTree', variant: 4 }, { x: -3 });
const FILE = sceneItem({ file: 'protoss\\zealot\\zealot.m3' });

test('a good document passes whole, every field as it was', async () => {
  const { parseSceneDocument } = await scene();
  const text = sceneText([MARINE, TREE, FILE]);
  expect(parseSceneDocument(JSON.parse(text))).toEqual(JSON.parse(text));
});

test('negative: a document that fails is refused by its first fault, by path', async () => {
  const { parseSceneDocument, SceneError, ITEMS_MAX } = await scene();
  const bad = [
    [[], /^not an object$/],
    [sceneText([MARINE], { version: 2 }), /^version: 2 is not 1$/],
    [sceneText([MARINE], { format: 'other' }), /^format: not "viewer-scene"$/],
    [sceneText([MARINE], { extra: 1 }), /^extra: unknown field$/],
    [sceneText([MARINE], { id: 'scene-1' }), /^id: not "s-"/],
    [sceneText([], { name: '' }), /^name: not 1 to 80 characters$/],
    [sceneText([], { name: ' padded' }), /^name: has spaces at an end$/],
    [sceneText([], { created: 'yesterday' }), /^created: not an ISO 8601 UTC time$/],
    [sceneText([], { items: {} }), /^items: not a list$/],
    [sceneText(Array(ITEMS_MAX + 1).fill(MARINE)), new RegExp(`^items: more than ${ITEMS_MAX}$`)],
    [sceneText([{ ...MARINE, scale: 0 }]), /^items\[0\]\.scale: not above 0$/],
    [sceneText([MARINE, { ...TREE, x: '3' }]), /^items\[1\]\.x: not a finite number$/],
    [sceneText([{ ...MARINE, pick: 2 }]), /^items\[0\]\.pick: not from 0 to 1$/],
    [sceneText([{ ...MARINE, dataset: 'Bad Id' }]), /^items\[0\]\.dataset: not an id/],
    [sceneText([{ ...MARINE, sequence: -2 }]), /^items\[0\]\.sequence: not an integer from -1 to 100000$/],
    [sceneText([{ ...MARINE, source: { ...MARINE.source, variant: 1.5 } }]), /^items\[0\]\.source\.variant: not an integer/],
    [sceneText([{ ...MARINE, source: { file: '' } }]), /^items\[0\]\.source\.file: not 1 to 1000 characters$/],
    [sceneText([{ ...MARINE, options: { team: [1, 'x', {}] }, colour: 1 }]), /^items\[0\]\.colour: unknown field$/],
    [sceneText([{ game: 'sc2' }]), /^items\[0\]\.dataset: missing$/],
  ];
  for (const [document, fault] of bad) {
    const value = typeof document === 'string' ? JSON.parse(document) : document;
    let error = null;
    try {
      parseSceneDocument(value);
    } catch (e) {
      error = e;
    }
    expect(error, String(document).slice(0, 60)).toBeInstanceOf(SceneError);
    expect(error.message, String(document).slice(0, 60)).toMatch(fault);
  }
});

test('a taken name gets the next free number; an empty one is "scene"; a long one keeps room for the number', async () => {
  const { freeName, NAME_MAX } = await scene();
  expect(freeName('  bases  ', [])).toBe('bases');
  expect(freeName('scene 1', ['scene 1'])).toBe('scene 1 (2)');
  expect(freeName('scene 1', ['scene 1', 'scene 1 (2)'])).toBe('scene 1 (3)');
  expect(freeName('   ', [])).toBe('scene');
  const long = 'x'.repeat(NAME_MAX + 5);
  expect(freeName(long, [])).toHaveLength(NAME_MAX);
  const numbered = freeName(long, ['x'.repeat(NAME_MAX)]);
  expect(numbered.length).toBeLessThanOrEqual(NAME_MAX);
  expect(numbered).toMatch(/ \(2\)$/);
  // Negative: a free name is not numbered.
  expect(freeName('zerg', ['scene 1'])).toBe('zerg');
});

test('a new scene is empty, named as asked without end spaces, and passes the check', async () => {
  const { emptyScene, newSceneId, parseSceneDocument, SCENE_ID_RULE } = await scene();
  const made = emptyScene(' scene 1 ', new Date('2026-11-23T12:00:00.000Z'));
  expect(made).toMatchObject({ name: 'scene 1', items: [], created: '2026-11-23T12:00:00.000Z', modified: '2026-11-23T12:00:00.000Z' });
  expect(parseSceneDocument(made)).toEqual(made);
  let n = 0;
  const id = newSceneId(() => (n++ % 36) / 36);
  expect(id).toBe('s-0123456789abcdef');
  expect(SCENE_ID_RULE.test(newSceneId())).toBe(true);
});
