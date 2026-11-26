// The input map (R-VIEW-154): which mouse button, modifiers or key does
// each action of the view, and the rates of the camera drags. One stored
// setting, `viewer.input`, holds what the person changed; everything not
// stored is the default below, which is the viewer's behaviour before the
// map. features/controls, pick, select and the key handlers decide only
// through here; the controls window (features/controls/panel.ts) edits it.
//
// A mouse binding matches a press when its button is pressed and every
// one of its modifiers is held; other modifiers may be held too. Of the
// press actions that match, the one with the most modifiers wins; among
// equals, the first in PRESS_ACTIONS. With the default map that is the
// viewer's rule before the map: Alt + left on a unit moves it, Ctrl +
// left with a selection turns, Alt + middle looks.
// A key binding matches with exactly its Ctrl, Alt and Meta (Meta also
// meets a Ctrl, for macOS), by KeyboardEvent.code with exactly its Shift,
// or by the character it types (`key`). A typed letter needs its Shift
// exactly too; a typed sign does not (on many layouts "/" needs Shift).
// The double click that opens textures is the browser's dblclick, left
// button only; it is not in the map.

export type Button = 'left' | 'middle' | 'right';
export type Mod = 'ctrl' | 'alt' | 'shift' | 'meta';
const BUTTONS: readonly Button[] = ['left', 'middle', 'right'];
const MODS: readonly Mod[] = ['ctrl', 'alt', 'shift', 'meta'];
const BUTTON_CODE: Record<Button, number> = { left: 0, middle: 1, right: 2 };

export interface MouseBinding {
  readonly button: Button;
  readonly mods: readonly Mod[];
}
export interface KeyBinding {
  readonly code: string;
  /** The character it types; a press that types it matches whatever its code. */
  readonly key?: string;
  readonly mods: readonly Mod[];
}

/** A press on the view that starts a drag (features/controls, features/select). */
export const PRESS_ACTIONS = ['move', 'rect', 'face', 'grab', 'look', 'orbit', 'pan'] as const;
/** A click without a drag (features/pick). */
export const CLICK_ACTIONS = ['select', 'addSelect', 'menu'] as const;
export const KEY_ACTIONS = ['remove', 'copy', 'cut', 'paste', 'loop', 'edges', 'original', 'cancel'] as const;
export type PressAction = (typeof PRESS_ACTIONS)[number];
export type ClickAction = (typeof CLICK_ACTIONS)[number];
export type KeyAction = (typeof KEY_ACTIONS)[number];
export type MouseAction = PressAction | ClickAction;

export const ACTION_LABEL: Record<MouseAction | KeyAction, string> = {
  move: 'Move a unit (on a unit)',
  rect: 'Select rectangle (off a unit)',
  face: 'Turn the selected units',
  grab: 'Grab the ground',
  look: 'Mouse-look',
  orbit: 'Orbit',
  pan: 'Pan',
  select: 'Select',
  addSelect: 'Add to or take from the selection',
  menu: 'Animation menu',
  remove: 'Remove the selected',
  copy: 'Copy',
  cut: 'Cut',
  paste: 'Paste',
  loop: 'Menu "loop" choice',
  edges: 'Triangle edges',
  original: 'Show Original skin while held',
  cancel: 'Cancel a unit move or turn',
};

export interface Rates {
  /** Radians per pixel of an orbit or mouse-look drag. */
  orbit: number;
  /** Camera distances per pixel of a pan drag. */
  pan: number;
  /** The share of each camera movement while the precision modifier is held. */
  preciseShare: number;
  /** The precision modifier. */
  precise: Mod;
  invertOrbitX: boolean;
  invertOrbitY: boolean;
  invertPan: boolean;
  /** Pixels and milliseconds that make a press a drag (core/press.ts, R-VIEW-142). */
  dragSlop: number;
  dragHoldMs: number;
  fastSlop: number;
}

export interface InputMap {
  readonly mouse: Readonly<Record<MouseAction, MouseBinding>>;
  readonly keys: Readonly<Record<KeyAction, KeyBinding>>;
  readonly rates: Readonly<Rates>;
}

/** What the person changed: any part of the map; the rest is the default. */
export interface InputSetting {
  mouse?: Partial<Record<MouseAction, MouseBinding>>;
  keys?: Partial<Record<KeyAction, KeyBinding>>;
  rates?: Partial<Rates>;
}

export const DEFAULT_INPUT: InputMap = {
  mouse: {
    move: { button: 'left', mods: ['alt'] },
    rect: { button: 'left', mods: ['alt'] },
    face: { button: 'left', mods: ['ctrl'] },
    grab: { button: 'left', mods: [] },
    look: { button: 'middle', mods: ['alt'] },
    orbit: { button: 'middle', mods: [] },
    pan: { button: 'right', mods: [] },
    select: { button: 'left', mods: [] },
    addSelect: { button: 'left', mods: ['shift'] },
    menu: { button: 'right', mods: [] },
  },
  keys: {
    remove: { code: 'Delete', mods: [] },
    copy: { code: 'KeyC', key: 'c', mods: ['ctrl'] },
    cut: { code: 'KeyX', key: 'x', mods: ['ctrl'] },
    paste: { code: 'KeyV', key: 'v', mods: ['ctrl'] },
    loop: { code: 'KeyL', key: 'l', mods: ['ctrl'] },
    edges: { code: 'Slash', key: '/', mods: ['ctrl'] },
    original: { code: 'Period', key: '.', mods: ['ctrl'] },
    cancel: { code: 'Escape', mods: [] },
  },
  rates: {
    orbit: 0.004,
    pan: 0.0006,
    preciseShare: 0.25,
    precise: 'ctrl',
    invertOrbitX: false,
    invertOrbitY: false,
    invertPan: false,
    dragSlop: 2,
    dragHoldMs: 150,
    fastSlop: 12,
  },
};

/** The allowed range of each number rate. */
export const RATE_RANGE: Readonly<Record<string, readonly [number, number]>> = {
  orbit: [0.0005, 0.03],
  pan: [0.00005, 0.005],
  preciseShare: [0.02, 1],
  dragSlop: [0, 40],
  dragHoldMs: [0, 2000],
  fastSlop: [1, 200],
};

const isRecord = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v);

function parseMods(value: unknown, what: string): Mod[] {
  if (!Array.isArray(value)) throw new Error(`${what}: the modifiers are not a list`);
  const mods = value.map((m: unknown) => {
    if (typeof m !== 'string' || !(MODS as readonly string[]).includes(m)) throw new Error(`${what}: "${String(m)}" is not a modifier`);
    return m as Mod;
  });
  if (new Set(mods).size !== mods.length) throw new Error(`${what}: a modifier twice`);
  return MODS.filter((m) => mods.includes(m));
}

function parseMouse(value: unknown, what: string): MouseBinding {
  if (!isRecord(value)) throw new Error(`${what} is not a mouse binding`);
  const unknown = Object.keys(value).find((k) => k !== 'button' && k !== 'mods');
  if (unknown) throw new Error(`${what}: unknown key "${unknown}"`);
  const button = value['button'];
  if (typeof button !== 'string' || !(BUTTONS as readonly string[]).includes(button)) throw new Error(`${what}: "${String(button)}" is not a button`);
  return { button: button as Button, mods: parseMods(value['mods'], what) };
}

function parseKey(value: unknown, what: string): KeyBinding {
  if (!isRecord(value)) throw new Error(`${what} is not a key binding`);
  const unknown = Object.keys(value).find((k) => k !== 'code' && k !== 'key' && k !== 'mods');
  if (unknown) throw new Error(`${what}: unknown key "${unknown}"`);
  const code = value['code'];
  const key = value['key'];
  if (typeof code !== 'string' || !/^[A-Za-z0-9]+$/.test(code)) throw new Error(`${what}: "${String(code)}" is not a key code`);
  if (key !== undefined && (typeof key !== 'string' || key.length !== 1)) throw new Error(`${what}: the typed key is not one character`);
  return key === undefined ? { code, mods: parseMods(value['mods'], what) } : { code, key: key.toLowerCase(), mods: parseMods(value['mods'], what) };
}

function parseRates(value: unknown): Partial<Rates> {
  if (!isRecord(value)) throw new Error('the rates are not an object');
  const rates: Partial<Rates> = {};
  for (const [name, v] of Object.entries(value)) {
    const base = Reflect.get(DEFAULT_INPUT.rates, name);
    if (base === undefined) throw new Error(`the rates: unknown key "${name}"`);
    if (name === 'precise') {
      if (typeof v !== 'string' || !(MODS as readonly string[]).includes(v) || v === 'shift') throw new Error('the precision modifier is not ctrl, alt or meta');
      rates.precise = v as Mod;
    } else if (typeof base === 'boolean') {
      if (typeof v !== 'boolean') throw new Error(`the rate ${name} is not true or false`);
      Reflect.set(rates, name, v);
    } else {
      const range = RATE_RANGE[name];
      if (!range) throw new Error(`the rate ${name} has no range`);
      const [low, high] = range;
      if (typeof v !== 'number' || !Number.isFinite(v) || v < low || v > high) throw new Error(`the rate ${name} is not a number from ${low} to ${high}`);
      Reflect.set(rates, name, v);
    }
  }
  return rates;
}

/** The stored setting, checked (core/settings.ts). */
export function parseInput(value: unknown): InputSetting {
  if (!isRecord(value)) throw new Error('the input map is not an object');
  const unknown = Object.keys(value).find((k) => k !== 'mouse' && k !== 'keys' && k !== 'rates');
  if (unknown) throw new Error(`the input map: unknown key "${unknown}"`);
  const out: InputSetting = {};
  const mouse = value['mouse'];
  if (mouse !== undefined) {
    if (!isRecord(mouse)) throw new Error('the mouse bindings are not an object');
    out.mouse = {};
    for (const [action, binding] of Object.entries(mouse)) {
      if (!(action in DEFAULT_INPUT.mouse)) throw new Error(`no mouse action "${action}"`);
      out.mouse[action as MouseAction] = parseMouse(binding, `the binding of ${action}`);
    }
  }
  const keys = value['keys'];
  if (keys !== undefined) {
    if (!isRecord(keys)) throw new Error('the key bindings are not an object');
    out.keys = {};
    for (const [action, binding] of Object.entries(keys)) {
      if (!(action in DEFAULT_INPUT.keys)) throw new Error(`no key action "${action}"`);
      out.keys[action as KeyAction] = parseKey(binding, `the key of ${action}`);
    }
  }
  if (value['rates'] !== undefined) out.rates = parseRates(value['rates']);
  return out;
}

/** The whole map: the stored changes over the default. */
export function resolveInput(stored: InputSetting | null): InputMap {
  return {
    mouse: { ...DEFAULT_INPUT.mouse, ...(stored?.mouse ?? {}) },
    keys: { ...DEFAULT_INPUT.keys, ...(stored?.keys ?? {}) },
    rates: { ...DEFAULT_INPUT.rates, ...(stored?.rates ?? {}) },
  };
}

/** Whether modifier `m` is held during `e`. */
export const held = (e: MouseEvent | KeyboardEvent, m: Mod): boolean => (m === 'ctrl' ? e.ctrlKey : m === 'alt' ? e.altKey : m === 'shift' ? e.shiftKey : e.metaKey);

/** Whether a mouse event is `binding`: its button, with every modifier of the binding held. */
export function mouseMatches(binding: MouseBinding, e: MouseEvent): boolean {
  return e.button === BUTTON_CODE[binding.button] && binding.mods.every((m) => held(e, m));
}

/** Of `actions` that match `e`, the one with the most modifiers; among equals the first. */
function best<A extends MouseAction>(map: InputMap, actions: readonly A[], e: MouseEvent): A | null {
  let found: A | null = null;
  for (const action of actions) {
    if (!mouseMatches(map.mouse[action], e)) continue;
    if (found === null || map.mouse[action].mods.length > map.mouse[found].mods.length) found = action;
  }
  return found;
}

/**
 * The drag a press starts, or null. `onUnit`: an instance is under the
 * pointer (move, else rect); `selected`: something is selected (face).
 */
export function pressAction(map: InputMap, e: MouseEvent, at: { onUnit: boolean; selected: boolean }): PressAction | null {
  const open = PRESS_ACTIONS.filter((a) => !(a === 'move' && !at.onUnit) && !(a === 'rect' && at.onUnit) && !(a === 'face' && !at.selected));
  return best(map, open, e);
}

/** The click a press without a drag is, or null; the modifiers at the press decide. */
export const clickAction = (map: InputMap, pressed: MouseEvent): ClickAction | null => best(map, CLICK_ACTIONS, pressed);

/** Whether a key event is `binding`. */
export function keyMatches(binding: KeyBinding, e: KeyboardEvent): boolean {
  const ctrl = binding.mods.includes('ctrl');
  const meta = binding.mods.includes('meta');
  // Meta meets a Ctrl binding (macOS); a binding with Meta itself wants Meta.
  const ctrlOk = ctrl ? e.ctrlKey || (e.metaKey && !meta) : !e.ctrlKey;
  const metaOk = meta ? e.metaKey : !e.metaKey || (ctrl && !e.ctrlKey);
  if (!ctrlOk || !metaOk || binding.mods.includes('alt') !== e.altKey) return false;
  const shift = binding.mods.includes('shift') === e.shiftKey;
  if (binding.key !== undefined && e.key.toLowerCase() === binding.key) return shift || !/^[a-z]$/.test(binding.key);
  return e.code === binding.code && shift;
}

const MOD_KEY: Record<Mod, string> = { ctrl: 'Control', alt: 'Alt', shift: 'Shift', meta: 'Meta' };

/** Whether a key event is the key of `binding`, whatever modifiers are held (the cancel key: a move holds Alt). */
export const keyIs = (binding: KeyBinding, e: KeyboardEvent): boolean => e.code === binding.code || (binding.key !== undefined && e.key.toLowerCase() === binding.key);

/** Whether a keyup ends a held key binding: its key, or one of its modifiers (Meta too for a Ctrl), went up. */
export function releasesKey(binding: KeyBinding, e: KeyboardEvent): boolean {
  if (keyIs(binding, e)) return true;
  return binding.mods.some((m) => e.key === MOD_KEY[m] || (m === 'ctrl' && e.key === 'Meta'));
}

const BUTTON_TEXT: Record<Button, string> = { left: 'Left', middle: 'Middle', right: 'Right' };
const MOD_TEXT: Record<Mod, string> = { ctrl: 'Ctrl', alt: 'Alt', shift: 'Shift', meta: 'Meta' };

/** "Ctrl+Alt+Left", "Ctrl+L", "Ctrl+/": a binding as the page shows it. */
export function bindingText(binding: MouseBinding | KeyBinding): string {
  const what = 'button' in binding ? BUTTON_TEXT[binding.button] : (binding.key?.toUpperCase() ?? binding.code.replace(/^(Key|Digit)/, ''));
  return [...binding.mods.map((m) => MOD_TEXT[m]), what].join('+');
}

/** The binding a mouse event is: its button and the modifiers held; null for a button past the third. */
export function mouseBindingOf(e: MouseEvent): MouseBinding | null {
  const button = BUTTONS[e.button];
  return button ? { button, mods: MODS.filter((m) => held(e, m)) } : null;
}

/** The binding a key event is; null for a lone modifier key. */
export function keyBindingOf(e: KeyboardEvent): KeyBinding | null {
  if (['Control', 'Alt', 'Shift', 'Meta'].includes(e.key)) return null;
  const mods = MODS.filter((m) => held(e, m));
  return e.key.length === 1 ? { code: e.code, key: e.key.toLowerCase(), mods } : { code: e.code, mods };
}
