import { test, expect } from '../fixtures.mjs';
import { source } from './source.mjs';

// What the upscale dialog offers, read from the states the pipeline wrote
// (src/page/features/skins/choices.ts, SPEC-VIEWER 17.5, R-VIEW-116, 117),
// and what a skin names for a texture (core/skins.ts shownVariant), without a
// browser. The pipeline decides every refusal; these only read them. That
// the dialog shows them and sends a request: tests/e2e/texture-variants.spec.mjs.

const choices = () => source('src/page/features/skins/choices.ts');

const HEAD = { sizes: [1024, 2048, 4096], models: [{ id: 'pbrify', title: 'PBRify' }, { id: 'fast', title: 'Fast' }, { id: 'seedvr2', title: 'SeedVR2' }], limits: [] };

const variant = (id, fields = {}) => ({ id, input: 'original', title: id, recipe: id.split('@')[0], models: {}, size: 2048, own: 2048, stale: false, numbers: [], problems: [], accepted: '', sha256: 'x', ...fields });

/** A judged colour texture: from the original every model, fast to 2048 only; from fast@2048, fast to 4096. */
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
    { input: 'original', models: { pbrify: { reason: '', sizes: { 2048: '', 4096: 'more than 4 times' } }, fast: { reason: '', sizes: { 1024: '', 2048: '', 512: '' } }, seedvr2: { reason: 'too large for the GPU', sizes: {} } } },
    { input: 'fast@2048', models: { fast: { reason: '', sizes: { 4096: '' } } } },
  ],
  requests: {},
  bake: null,
  bakeProblem: '',
  packaged: null,
};
/** A data texture (no colour plane): only fast is offered. */
const DATA = { ...COLOUR, asset: 'n.dds', colour: false, variants: [], asks: [{ input: 'original', models: { fast: { reason: '', sizes: { 2048: '' } }, pbrify: { reason: 'no colour plane', sizes: {} }, seedvr2: { reason: 'no colour plane', sizes: {} } } }] };

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

test('the sizes are the dataset\'s, then any smaller own size, in order; one the pipeline does not list cannot be reached', async () => {
  const { sizeChoices } = await choices();
  expect(sizeChoices(COLOUR, HEAD, 'original', 'fast')).toEqual([
    { value: '512', label: '512', reason: '' },
    { value: '1024', label: '1024', reason: '' },
    { value: '2048', label: '2048', reason: '' },
    { value: '4096', label: '4096', reason: 'cannot be reached' },
  ]);
  expect(sizeChoices(COLOUR, HEAD, 'original', 'pbrify').map((c) => [c.value, c.reason])).toEqual([['1024', 'cannot be reached'], ['2048', ''], ['4096', 'more than 4 times']]);
  // Negative: a model not offered reaches no size.
  expect(sizeChoices(COLOUR, HEAD, 'fast@2048', 'seedvr2').every((c) => c.reason === 'cannot be reached')).toBe(true);
});

test('an owner upscale asks for each texture that can reach the size; a data texture gets fast; the rest keep what the skin shows', async () => {
  const { ownerPlan } = await choices();
  const owner = { owner: 'unit:X', title: 'X', layer: 'unit', textures: ['a.dds', 'n.dds', 'u.dds', 'gone.dds'], below: [], skins: [{ name: 'hd', stored: true, textures: { 'a.dds': 'fast@2048' } }], shows: {}, bake: null, held: false };
  const states = new Map([['a.dds', COLOUR], ['n.dds', DATA], ['u.dds', { ...COLOUR, asset: 'u.dds', judged: false }]]);
  expect(ownerPlan(owner, 'original', states, 'pbrify', 2048)).toEqual({ data: 1, kept: ['u.dds', 'gone.dds'], asked: 2 });
  // From the skin: a.dds starts from fast@2048, which offers fast to 4096 and no pbrify.
  expect(ownerPlan(owner, 'hd', states, 'pbrify', 2048)).toEqual({ data: 1, kept: ['a.dds', 'u.dds', 'gone.dds'], asked: 1 });
  expect(ownerPlan(owner, 'hd', states, 'fast', 4096)).toEqual({ data: 0, kept: ['n.dds', 'u.dds', 'gone.dds'], asked: 1 });
  // Negative: a skin the owner does not have is refused.
  expect(() => ownerPlan(owner, 'nosuch', states, 'fast', 2048)).toThrow('unit:X has no skin "nosuch"');
});

test('a skin names a variant per texture; Original and a texture the skin does not name show the original', async () => {
  const { shownVariant } = await source('src/page/core/skins.ts');
  const owner = { owner: 'unit:X', skins: [{ name: 'hd', textures: { 'a.dds': 'fast@2048' } }] };
  expect(shownVariant(owner, 'hd', 'a.dds')).toBe('fast@2048');
  expect(shownVariant(owner, 'hd', 'b.dds')).toBe('original');
  expect(shownVariant(owner, 'original', 'a.dds')).toBe('original');
  expect(() => shownVariant(owner, 'nosuch', 'a.dds')).toThrow('unit:X has no skin "nosuch"');
});
