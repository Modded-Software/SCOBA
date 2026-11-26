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

test('Ask Again of a revision asks for its model without the revision; the pipeline picks the id that serves it', async () => {
  // R-HD-158: `pbrify~2@512` stands beside `pbrify@512`. The request route takes a model, and `pbrify~2` is none.
  const { askOf, recipeOf } = await source('src/shared/textures.ts');
  expect(askOf('a.dds', 'pbrify~2@512')).toEqual({ asset: 'a.dds', input: 'original', model: 'pbrify', size: 512 });
  // The input keeps its revision: it names one kept variant.
  expect(askOf('a.dds', 'pbrify~2@256+seedvr2~3@1024')).toEqual({ asset: 'a.dds', input: 'pbrify~2@256', model: 'seedvr2', size: 1024 });
  // Negative: an id without a revision is asked as it is; a recipe keeps its revision, as the requests are named by it.
  expect(askOf('a.dds', 'fast@2048')).toEqual({ asset: 'a.dds', input: 'original', model: 'fast', size: 2048 });
  expect(recipeOf('pbrify~2@512')).toBe('pbrify~2');
  expect(askOf('a.dds', 'original')).toBeNull();
});

test('the users badge counts model files from 2 up; it is amber when another owner bakes a variant; "named by" lists the bakes first', async () => {
  // R-VIEW-160, R-VIEW-161: read from the state's `users` and `namedBy`; nothing is worked out of files here.
  const { usersBadge, namedByLines } = await source('src/shared/textures.ts');
  const state = (users, namedBy = []) => ({ ...COLOUR, users, namedBy });
  expect(usersBadge(state(['a.m3', 'b.m3']), 'unit:X')).toEqual({ count: 2, title: 'read by 2 model files\na.m3\nb.m3', sharedBake: false });
  // Negative: one model file, or none: no badge.
  expect(usersBadge(state(['a.m3']), 'unit:X')).toBeNull();
  expect(usersBadge(state([]), null)).toBeNull();
  const own = { owner: 'unit:X', skin: 'hd', variant: 'fast@512', baked: true };
  const skins = [{ ...own, baked: false }, { owner: 'unit:Y', skin: 'two', variant: 'fast@256', baked: false }];
  // Negative: the window's own bake and the skins of others are no bake of another owner.
  expect(usersBadge(state(['a.m3', 'b.m3'], [own, ...skins]), 'unit:X').sharedBake).toBe(false);
  const other = { owner: 'unit:Z', skin: 'up', variant: 'fast@512', baked: true };
  const more = { owner: 'model:a.m3', skin: 'old', variant: 'fast@256', baked: true };
  expect(usersBadge(state(['a.m3', 'b.m3'], [own, ...skins, other]), 'unit:X')).toEqual({
    count: 2,
    title: 'read by 2 model files\na.m3\nb.m3\nbaked by 1 other owner\nunit:Z',
    sharedBake: true,
  });
  expect(usersBadge(state(['a.m3', 'b.m3'], [more, other]), 'unit:X').title).toBe('read by 2 model files\na.m3\nb.m3\nbaked by 2 other owners\nmodel:a.m3\nunit:Z');
  // One model file, and another owner bakes it (a unit over its model file's bake): the badge says so, with no count.
  expect(usersBadge(state(['a.m3'], [more]), 'unit:X')).toEqual({ count: null, title: 'baked by 1 other owner\nmodel:a.m3', sharedBake: true });
  // A window on no owner: every bake is another's.
  expect(usersBadge(state(['a.m3', 'b.m3'], [own]), null).sharedBake).toBe(true);

  expect(namedByLines(state([], [own, ...skins, other]))).toEqual(['unit:X · hd · fast@512 · baked', 'unit:Z · up · fast@512 · baked', 'unit:X · hd · fast@512', 'unit:Y · two · fast@256']);
  // Negative: nobody names it: no line.
  expect(namedByLines(state([]))).toEqual([]);
});

test('the Delete Variant dialog lists the other owners that name the variant, the bakes first; none: it says so', async () => {
  // R-VIEW-162: read from the state's `namedBy`; the dialog only words it.
  const { removalWarning } = await source('src/shared/textures.ts');
  const state = (namedBy) => ({ ...COLOUR, namedBy });
  const own = { owner: 'unit:X', skin: 'hd', variant: 'fast@512', baked: true };
  const skin = { owner: 'unit:Y', skin: 'two', variant: 'fast@512', baked: false };
  const bake = { owner: 'unit:Z', skin: 'up', variant: 'fast@512', baked: true };
  const otherSize = { owner: 'unit:W', skin: 'small', variant: 'fast@256', baked: true };
  expect(removalWarning(state([own, skin, bake, otherSize]), 'fast@512', 'unit:X')).toEqual({
    head: '2 skins or bakes of other owners name it:',
    lines: ['unit:Z · up (baked)', 'unit:Y · two'],
  });
  expect(removalWarning(state([own, skin]), 'fast@512', 'unit:X')).toEqual({ head: '1 skin or bake of another owner names it:', lines: ['unit:Y · two'] });
  // A window on no owner: every entry is another's.
  expect(removalWarning(state([own]), 'fast@512', null).lines).toEqual(['unit:X · hd (baked)']);
  // Negative: the window's own owner and another variant of the texture are not listed; nobody: it says so.
  expect(removalWarning(state([own, otherSize]), 'fast@512', 'unit:X')).toEqual({ head: 'No other owner names it.', lines: [] });
  expect(removalWarning(state([]), 'fast@512', 'unit:X')).toEqual({ head: 'No other owner names it.', lines: [] });
});

test('the skin name rule agrees with the pipeline on every row of hdtex.core skin_names.json', async () => {
  const { skinNameRefusal } = await source('src/shared/textures.ts');
  const root = process.env['REPO_ROOT'];
  expect(root, 'REPO_ROOT, exported by webviewer/scripts/paths.sh').toBeTruthy();
  const { names } = JSON.parse(readFileSync(join(root, 'scripts', 'hdtex', 'core', 'skin_names.json'), 'utf8'));
  expect(names.some((row) => row.ok) && names.some((row) => !row.ok)).toBe(true);
  for (const row of names) expect(skinNameRefusal(row.name) === '', JSON.stringify(row.name)).toBe(row.ok);
});
