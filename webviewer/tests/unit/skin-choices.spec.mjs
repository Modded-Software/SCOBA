import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test, expect } from '../fixtures.mjs';
import { source } from './source.mjs';

// What the upscale dialog offers, read from the states the pipeline wrote
// (src/page/features/skins/choices.ts, SPEC-VIEWER 17.5, R-VIEW-116, 117),
// and what a skin names for a texture (shared/textures.ts namedIn), without a
// browser. The pipeline decides every refusal; these only read them. That
// the dialog shows them and sends a request: tests/e2e/texture-variants.spec.mjs.

const choices = () => source('src/page/features/skins/choices.ts');

const HEAD = { factors: [2, 4], maxSide: 4096, models: [{ id: 'pbrify', title: 'PBRify' }, { id: 'fast', title: 'Fast' }, { id: 'seedvr2', title: 'SeedVR2' }], limits: [] };

const variant = (id, fields = {}) => ({ id, input: 'original', title: id, recipe: id.split('@')[0], models: {}, size: 2048, own: 2048, stale: false, numbers: [], problems: [], accepted: '', sha256: 'x', ...fields });

const at = (size, reason = '') => ({ size, reason });
const ADDS_NOTHING = '4x of a side of 1024 gives 1024 here (the largest side is 1024); that adds nothing';

/** A judged colour texture of 1024: from the original pbrify 2x only and fast both; from fast@2048, fast to 4096. */
const COLOUR = {
  asset: 'a.dds',
  kind: 'model',
  users: [],
  tiles: false,
  judged: true,
  reason: '',
  colour: true,
  variants: [variant('fast@2048'), variant('pbrify@2048', { stale: true }), variant('seedvr2@2048', { problems: [{ limit: 'x', value: 1, bound: 0 }] })],
  asks: [
    { input: 'original', models: { pbrify: { reason: '', factors: { 2: at(2048), 4: at(4096, 'too large for the GPU at 4096') } }, fast: { reason: '', factors: { 2: at(2048), 4: at(4096) } }, seedvr2: { reason: 'too large for the GPU', factors: {} } } },
    { input: 'fast@2048', models: { fast: { reason: '', factors: { 2: at(4096), 4: at(4096) } } } },
  ],
  requests: {},
  bake: null,
  bakeProblem: '',
  packaged: null,
};
/** A data texture (no colour plane): only fast is offered. */
const DATA = { ...COLOUR, asset: 'n.dds', colour: false, variants: [], asks: [{ input: 'original', models: { fast: { reason: '', factors: { 2: at(1024), 4: at(1024, ADDS_NOTHING) } }, pbrify: { reason: 'no colour plane', factors: {} }, seedvr2: { reason: 'no colour plane', factors: {} } } }] };

test('the inputs are the original, then each variant that may be shown; a stale one or one with a problem not accepted is no input', async () => {
  const { inputsOf } = await choices();
  expect(inputsOf(COLOUR)).toEqual(['original', 'fast@2048']);
  const accepted = { ...COLOUR, variants: [variant('seedvr2@2048', { problems: [{ limit: 'x', value: 1, bound: 0 }], accepted: 'looked at' })] };
  expect(inputsOf(accepted)).toEqual(['original', 'seedvr2@2048']);
});

test('each model of the dataset, with the pipeline\'s reason; one not offered from an input names that input', async () => {
  const { modelChoices } = await choices();
  expect(modelChoices(COLOUR, HEAD, 'original')).toEqual([
    { value: 'pbrify', label: 'PBRify', reason: '' },
    { value: 'fast', label: 'Fast', reason: '' },
    { value: 'seedvr2', label: 'SeedVR2', reason: 'too large for the GPU' },
  ]);
  expect(modelChoices(COLOUR, HEAD, 'fast@2048').map((c) => c.reason)).toEqual(['not offered from fast@2048', '', 'not offered from fast@2048']);
  // Negative: on a data texture only fast can be chosen; the others say why.
  expect(modelChoices(DATA, HEAD, 'original').map((c) => [c.value, c.reason])).toEqual([['pbrify', 'no colour plane'], ['fast', ''], ['seedvr2', 'no colour plane']]);
  // Negative: not read yet, or a texture that cannot be upscaled: every model is refused with that reason.
  expect(modelChoices({ ...COLOUR, judged: false }, HEAD, 'original').every((c) => c.reason === 'not read yet')).toBe(true);
  expect(modelChoices({ ...COLOUR, reason: 'too small' }, HEAD, 'original').every((c) => c.reason === 'too small')).toBe(true);
});

test('the factors are the dataset\'s, each with the side it gives and the pipeline\'s reason', async () => {
  const { factorChoices, ownerFactorChoices } = await choices();
  expect(factorChoices(COLOUR, HEAD, 'original', 'fast')).toEqual([
    { value: '2', label: '2x: 2048', reason: '' },
    { value: '4', label: '4x: 4096', reason: '' },
  ]);
  expect(factorChoices(COLOUR, HEAD, 'original', 'pbrify').map((c) => [c.label, c.reason])).toEqual([['2x: 2048', ''], ['4x: 4096', 'too large for the GPU at 4096']]);
  // Negative: a model not offered gives no factor.
  expect(factorChoices(COLOUR, HEAD, 'fast@2048', 'seedvr2')).toEqual([{ value: '2', label: '2x', reason: 'not offered' }, { value: '4', label: '4x', reason: 'not offered' }]);
  expect(ownerFactorChoices(HEAD).map((c) => c.label)).toEqual(['2x', '4x']);
});

test('an owner upscale asks for each texture that can have the factor, with its side; a data texture gets fast; the rest keep what the skin shows, with why', async () => {
  const { ownerPlan } = await choices();
  const owner = { owner: 'unit:X', title: 'X', layer: 'unit', textures: ['a.dds', 'n.dds', 'u.dds', 'gone.dds'], below: [], skins: [{ name: 'hd', textures: { 'a.dds': 'fast@2048' } }], shows: {}, bake: null, held: false };
  const states = new Map([['a.dds', COLOUR], ['n.dds', DATA], ['u.dds', { ...COLOUR, asset: 'u.dds', judged: false }]]);
  const unread = [{ asset: 'u.dds', reason: 'not read yet' }, { asset: 'gone.dds', reason: 'no state' }];
  expect(ownerPlan(owner, 'original', states, 'pbrify', 2)).toEqual({ data: 1, kept: unread, asked: [{ asset: 'a.dds', size: 2048 }, { asset: 'n.dds', size: 1024 }] });
  // From the skin: a.dds starts from fast@2048, which offers fast to 4096 and no pbrify.
  expect(ownerPlan(owner, 'hd', states, 'pbrify', 2)).toEqual({ data: 1, kept: [{ asset: 'a.dds', reason: 'pbrify is not offered' }, ...unread], asked: [{ asset: 'n.dds', size: 1024 }] });
  expect(ownerPlan(owner, 'hd', states, 'fast', 4)).toEqual({ data: 0, kept: [{ asset: 'n.dds', reason: ADDS_NOTHING }, ...unread], asked: [{ asset: 'a.dds', size: 4096 }] });
  // Negative: a factor no texture can have asks for nothing; the dialog then cannot be sent.
  expect(ownerPlan(owner, 'original', states, 'pbrify', 4).asked).toEqual([]);
  // Negative: a skin the owner does not have is refused.
  expect(() => ownerPlan(owner, 'nosuch', states, 'fast', 2)).toThrow('unit:X has no skin "nosuch"');
});

test('a skin names a variant per texture; Original and a texture the skin does not name show the original', async () => {
  const { namedIn, hasSkin } = await source('src/shared/textures.ts');
  const owner = { owner: 'unit:X', skins: [{ name: 'hd', textures: { 'a.dds': 'fast@2048' } }] };
  expect(namedIn(owner, 'hd', 'a.dds')).toBe('fast@2048');
  expect(namedIn(owner, 'hd', 'b.dds')).toBe('original');
  expect(namedIn(owner, 'original', 'a.dds')).toBe('original');
  expect([hasSkin(owner, 'hd'), hasSkin(owner, 'original'), hasSkin(owner, 'nosuch')]).toEqual([true, true, false]);
  // Negative: a skin the owner does not have names nothing; it is no Original.
  expect(() => namedIn(owner, 'nosuch', 'a.dds')).toThrow('unit:X has no skin "nosuch"');
});

test('Save to Skin offers the instance\'s skin first when the owner has it; else a new skin, made from Original', async () => {
  const { firstSaveInto, namedInto } = await source('src/shared/textures.ts');
  const owner = { owner: 'unit:X', skins: [{ name: 'hd', textures: { 'a.dds': 'fast@2048' } }] };
  expect(firstSaveInto(owner, 'hd')).toEqual({ kind: 'existing', skin: 'hd' });
  expect(namedInto(owner, { kind: 'existing', skin: 'hd' }, 'a.dds')).toBe('fast@2048');
  // Negative: Original, no instance, and a missing skin are no existing target.
  for (const shown of ['original', null, 'new']) expect(firstSaveInto(owner, shown), String(shown)).toEqual({ kind: 'new' });
  expect(namedInto(owner, { kind: 'new' }, 'a.dds')).toBe('original');
});

test('the skin name rule agrees with the pipeline on every row of hdtex.core skin_names.json', async () => {
  const { skinNameRefusal } = await source('src/shared/textures.ts');
  const root = process.env['REPO_ROOT'];
  expect(root, 'REPO_ROOT, exported by webviewer/scripts/paths.sh').toBeTruthy();
  const { names } = JSON.parse(readFileSync(join(root, 'scripts', 'hdtex', 'core', 'skin_names.json'), 'utf8'));
  expect(names.some((row) => row.ok) && names.some((row) => !row.ok)).toBe(true);
  for (const row of names) expect(skinNameRefusal(row.name) === '', JSON.stringify(row.name)).toBe(row.ok);
});
