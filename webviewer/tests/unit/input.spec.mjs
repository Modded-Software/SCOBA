import { test, expect } from '../fixtures.mjs';
import { source } from './source.mjs';

// The input map (src/page/core/input.ts, R-VIEW-154), without a browser.
// The default map decides every press as the viewer did before the map; a
// stored change acts and the old binding stops acting; a stored map with a
// fault is refused, naming it. The page side (the controls window, a
// rebound drag in the view): tests/e2e/input.spec.mjs.

const input = () => source('src/page/core/input.ts');
const mouse = (button, mods = []) => ({ button, ctrlKey: mods.includes('ctrl'), altKey: mods.includes('alt'), shiftKey: mods.includes('shift'), metaKey: mods.includes('meta') });
const key = (k, code, mods = []) => ({ key: k, code, ...mouse(0, mods) });
const LEFT = 0;
const MIDDLE = 1;
const RIGHT = 2;

test('the default map decides each press as before the map', async () => {
  const { pressAction, resolveInput } = await input();
  const map = resolveInput(null);
  const off = { onUnit: false, selected: false };
  const cases = [
    [mouse(LEFT), off, 'grab'],
    [mouse(LEFT, ['ctrl']), off, 'grab'],
    [mouse(LEFT, ['ctrl']), { onUnit: false, selected: true }, 'face'],
    [mouse(LEFT, ['alt']), { onUnit: true, selected: false }, 'move'],
    [mouse(LEFT, ['alt']), off, 'rect'],
    [mouse(LEFT, ['alt', 'shift']), off, 'rect'],
    [mouse(LEFT, ['ctrl', 'alt']), { onUnit: true, selected: true }, 'move'],
    [mouse(MIDDLE), off, 'orbit'],
    [mouse(MIDDLE, ['alt']), off, 'look'],
    [mouse(MIDDLE, ['ctrl', 'alt']), off, 'look'],
    [mouse(RIGHT), off, 'pan'],
    [mouse(RIGHT, ['ctrl']), off, 'pan'],
  ];
  const got = cases.map(([e, at]) => pressAction(map, e, at));
  expect(got).toEqual(cases.map((c) => c[2]));
});

test('the default clicks: select, add with Shift, the menu on the right button; middle is no click', async () => {
  const { clickAction, resolveInput } = await input();
  const map = resolveInput(null);
  const got = [mouse(LEFT), mouse(LEFT, ['alt']), mouse(LEFT, ['shift']), mouse(RIGHT), mouse(RIGHT, ['shift']), mouse(MIDDLE)].map((e) => clickAction(map, e));
  expect(got).toEqual(['select', 'select', 'addSelect', 'menu', 'menu', null]);
});

test('the double press: the second press the browser counts, on the binding of open; left when nothing is stored', async () => {
  const { opens, parseInput, resolveInput } = await input();
  const second = (button, mods = [], detail = 2) => ({ ...mouse(button, mods), detail });
  const map = resolveInput(null);
  expect(map.mouse.open).toEqual({ button: 'left', mods: [] });
  // As the browser's dblclick: left, with any modifiers held.
  expect([opens(map, second(LEFT)), opens(map, second(LEFT, ['ctrl']))]).toEqual([true, true]);
  // Negative: a first press, a third press, another button.
  expect([opens(map, second(LEFT, [], 1)), opens(map, second(LEFT, [], 3)), opens(map, second(MIDDLE)), opens(map, second(RIGHT))]).toEqual([false, false, false, false]);
  const rebound = resolveInput(parseInput({ mouse: { open: { button: 'middle', mods: ['shift'] } } }));
  expect(opens(rebound, second(MIDDLE, ['shift']))).toBe(true);
  // Negative: the left button no longer opens, nor the middle one without Shift.
  expect([opens(rebound, second(LEFT)), opens(rebound, second(MIDDLE))]).toEqual([false, false]);
});

test('the wheel flags are off when nothing is stored, and a stored one is read', async () => {
  const { parseInput, resolveInput } = await input();
  const { rates } = resolveInput(null);
  expect([rates.invertZoom, rates.zoomToPointer]).toEqual([false, false]);
  const stored = resolveInput(parseInput({ rates: { zoomToPointer: true } })).rates;
  expect([stored.invertZoom, stored.zoomToPointer]).toEqual([false, true]);
});

test('a stored binding acts, and the default it replaced no longer does', async () => {
  const { pressAction, parseInput, resolveInput } = await input();
  const map = resolveInput(parseInput({ mouse: { pan: { button: 'left', mods: ['shift'] } } }));
  const off = { onUnit: false, selected: false };
  expect(pressAction(map, mouse(LEFT, ['shift']), off)).toBe('pan');
  // Negative: the right button no longer pans, and a plain left still grabs.
  expect(pressAction(map, mouse(RIGHT), off)).toBe(null);
  expect(pressAction(map, mouse(LEFT), off)).toBe('grab');
});

test('keys: by the typed sign with Shift free, by a letter with Shift exact; Meta meets a Ctrl', async () => {
  const { keyMatches, resolveInput } = await input();
  const { keys } = resolveInput(null);
  const got = {
    edgesUs: keyMatches(keys.edges, key('/', 'Slash', ['ctrl'])),
    edgesShifted: keyMatches(keys.edges, key('/', 'Digit7', ['ctrl', 'shift'])),
    edgesAlt: keyMatches(keys.edges, key('/', 'Slash', ['ctrl', 'alt'])),
    copy: keyMatches(keys.copy, key('c', 'KeyC', ['ctrl'])),
    copyMeta: keyMatches(keys.copy, key('c', 'KeyC', ['meta'])),
    copyShift: keyMatches(keys.copy, key('C', 'KeyC', ['ctrl', 'shift'])),
    copyBare: keyMatches(keys.copy, key('c', 'KeyC')),
    remove: keyMatches(keys.remove, key('Delete', 'Delete')),
  };
  expect(got).toEqual({ edgesUs: true, edgesShifted: true, edgesAlt: false, copy: true, copyMeta: true, copyShift: false, copyBare: false, remove: true });
});

test('the play/pause key: Ctrl+E when nothing is stored', async () => {
  const { keyMatches, parseInput, resolveInput, bindingText, KEY_ACTIONS } = await input();
  const { keys } = resolveInput(null);
  expect(KEY_ACTIONS).toContain('playPause');
  expect(keys.playPause).toEqual({ code: 'KeyE', key: 'e', mods: ['ctrl'] });
  expect(bindingText(keys.playPause)).toBe('Ctrl+E');
  expect(keyMatches(keys.playPause, key('e', 'KeyE', ['ctrl']))).toBe(true);
  // Negative: a bare E, Shift or Alt held too, the media key, another Ctrl letter.
  const others = [key('e', 'KeyE'), key('E', 'KeyE', ['ctrl', 'shift']), key('e', 'KeyE', ['ctrl', 'alt']), key('MediaPlayPause', 'MediaPlayPause'), key('l', 'KeyL', ['ctrl'])];
  expect(others.map((e) => keyMatches(keys.playPause, e))).toEqual([false, false, false, false, false]);
  // No other default key is Ctrl+E.
  const same = Object.entries(keys).filter(([, binding]) => keyMatches(binding, key('e', 'KeyE', ['ctrl']))).map(([action]) => action);
  expect(same).toEqual(['playPause']);
  // Rebound: the new key is it, Ctrl+E no longer.
  const rebound = resolveInput(parseInput({ keys: { playPause: { code: 'KeyP', key: 'p', mods: [] } } })).keys.playPause;
  expect([keyMatches(rebound, key('p', 'KeyP')), keyMatches(rebound, key('e', 'KeyE', ['ctrl']))]).toEqual([true, false]);
});

test('a stored map with a fault is refused, naming it', async () => {
  const { parseInput } = await input();
  const faults = [
    [{ mouse: { pan: { button: 'thumb', mods: [] } } }, /not a button/],
    [{ mouse: { fly: { button: 'left', mods: [] } } }, /no mouse action "fly"/],
    [{ mouse: { pan: { button: 'left', mods: ['hyper'] } } }, /not a modifier/],
    [{ keys: { copy: { code: 'KeyC', key: 'cc', mods: [] } } }, /one character/],
    [{ rates: { orbit: 1 } }, /orbit is not a number from/],
    [{ rates: { precise: 'shift' } }, /precision modifier/],
    [{ rates: { invertPan: 1 } }, /not true or false/],
    [{ rates: { invertZoom: 'yes' } }, /invertZoom is not true or false/],
    [{ rates: { zoomToPointer: 1 } }, /zoomToPointer is not true or false/],
    [{ extra: 1 }, /unknown key "extra"/],
  ];
  const got = faults.map(([value]) => {
    try {
      parseInput(value);
      return 'accepted';
    } catch (error) {
      return error.message;
    }
  });
  faults.forEach(([, pattern], i) => expect(got[i]).toMatch(pattern));
});

test('the binding text', async () => {
  const { bindingText, resolveInput } = await input();
  const map = resolveInput(null);
  expect([bindingText(map.keys.loop), bindingText(map.keys.edges), bindingText(map.mouse.look), bindingText(map.keys.remove)]).toEqual(['Ctrl+L', 'Ctrl+/', 'Alt+Middle', 'Delete']);
});
