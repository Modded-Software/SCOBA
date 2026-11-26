// The controls window (R-VIEW-154): the small gear button at the bottom
// right of the view opens it, above the button; a second click closes it. It lists every action of the input map (core/input.ts) with its
// binding, and the rates. A click on a binding listens: the next press of
// a mouse button on it (with the modifiers held), or the next key, is the
// new binding; Escape while listening for a mouse binding stops listening.
// "default" on a row puts back that binding; "reset all" clears the stored
// map. The mouse sensitivity (R-VIEW-150) is here too. Every change is
// written at once to the stored setting `viewer.input` (or
// `viewer.mouse.sensitivity`) and acts from the next press.

import type { FeatureContext } from '../../core/context';
import { byId, make } from '../../core/dom';
import {
  ACTION_LABEL,
  bindingText,
  CLICK_ACTIONS,
  DEFAULT_INPUT,
  DOUBLE_ACTIONS,
  KEY_ACTIONS,
  keyBindingOf,
  mouseBindingOf,
  PRESS_ACTIONS,
  RATE_RANGE,
  resolveInput,
  type InputSetting,
  type KeyAction,
  type MouseAction,
  type Rates,
} from '../../core/input';
import { MOUSE_SENSITIVITY_RANGE, settings } from '../../core/settings';

/** What the tests read: the action listening for its binding, and the rows as shown. */
export interface ControlsPanelState {
  open: boolean;
  listening: string | null;
  rows: Record<string, string>;
}

const NUMBER_RATES = ['orbit', 'pan', 'preciseShare', 'dragSlop', 'dragHoldMs', 'fastSlop'] as const;
const FLAG_RATES = ['invertOrbitX', 'invertOrbitY', 'invertPan', 'invertZoom', 'zoomToPointer'] as const;
const RATE_LABEL: Record<(typeof NUMBER_RATES)[number] | (typeof FLAG_RATES)[number] | 'precise', string> = {
  orbit: 'Orbit and look, radians per pixel',
  pan: 'Pan, distances per pixel',
  preciseShare: 'Share while the precision modifier is held',
  precise: 'Precision modifier',
  dragSlop: 'A slow press drags after, pixels',
  dragHoldMs: 'And after, ms',
  fastSlop: 'A fast press drags after, pixels',
  invertOrbitX: 'Invert orbit and look left and right',
  invertOrbitY: 'Invert orbit and look up and down',
  invertPan: 'Invert pan',
  invertZoom: 'Invert the wheel zoom',
  zoomToPointer: 'Zoom to the pointer',
};

export function createControlsPanel({ ui, store, status, testApi }: FeatureContext): void {
  const win = ui.floatingWindow({ id: 'controls-window', title: 'controls' });
  const button = byId('controls-button');
  let listening: MouseAction | KeyAction | null = null;
  const rows: Record<string, string> = {};

  const stored = (): InputSetting => store.read(settings.input);
  function write(next: InputSetting): void {
    store.write(settings.input, next);
    render();
  }

  /** One action's row: its label, its binding (a click listens), and "default". */
  function bindingRow(action: MouseAction | KeyAction, kind: 'mouse' | 'keys'): HTMLElement {
    const map = resolveInput(stored());
    const binding = kind === 'mouse' ? map.mouse[action as MouseAction] : map.keys[action as KeyAction];
    const text = listening === action ? (kind === 'mouse' ? 'Press a button here…' : 'Press a key…') : bindingText(binding);
    rows[action] = text;
    const bind = make('button', { type: 'button', className: 'controls-binding', textContent: text, title: 'click, then press the new binding' });
    bind.dataset['action'] = action;
    bind.addEventListener('click', () => {
      if (listening === null) {
        listening = action;
        render();
      }
    });
    bind.addEventListener('contextmenu', (e) => e.preventDefault());
    bind.addEventListener('mousedown', (e) => {
      if (listening !== action || kind !== 'mouse') return;
      e.preventDefault();
      const got = mouseBindingOf(e);
      if (!got) return;
      listening = null;
      const next = stored();
      write({ ...next, mouse: { ...next.mouse, [action]: got } });
    });
    const reset = make('button', { type: 'button', className: 'controls-default', textContent: 'Default' });
    reset.addEventListener('click', () => {
      const next = stored();
      const part = { ...(kind === 'mouse' ? next.mouse : next.keys) };
      Reflect.deleteProperty(part, action);
      write({ ...next, [kind]: part });
    });
    return make('tr', {}, [make('td', { textContent: ACTION_LABEL[action] }), make('td', {}, [bind]), make('td', {}, [reset])]);
  }

  /** Write one rate, checked against its range: out of range, it is not written and the status says why. */
  function setRate(name: keyof Rates, value: Rates[keyof Rates]): void {
    const range = RATE_RANGE[name];
    if (range && (typeof value !== 'number' || !Number.isFinite(value) || value < range[0] || value > range[1])) {
      status.setStatus(`${RATE_LABEL[name as keyof typeof RATE_LABEL]}: a number from ${range[0]} to ${range[1]}`, { failure: true });
      render();
      return;
    }
    const next = stored();
    write({ ...next, rates: { ...next.rates, [name]: value } });
  }

  function rateRows(): HTMLElement[] {
    const { rates } = resolveInput(stored());
    const out: HTMLElement[] = [];
    for (const name of NUMBER_RATES) {
      const field = make('input', { type: 'number', className: 'controls-rate', value: String(rates[name]), step: 'any' });
      field.dataset['rate'] = name;
      field.addEventListener('change', () => setRate(name, field.valueAsNumber));
      out.push(make('tr', {}, [make('td', { textContent: RATE_LABEL[name] }), make('td', {}, [field])]));
    }
    const precise = make('select', { className: 'controls-rate' }, (['ctrl', 'alt', 'meta'] as const).map((m) => make('option', { value: m, textContent: { ctrl: 'Ctrl', alt: 'Alt', meta: 'Meta' }[m], selected: rates.precise === m })));
    precise.dataset['rate'] = 'precise';
    precise.addEventListener('change', () => setRate('precise', precise.value as Rates['precise']));
    out.push(make('tr', {}, [make('td', { textContent: RATE_LABEL.precise }), make('td', {}, [precise])]));
    for (const name of FLAG_RATES) {
      const box = make('input', { type: 'checkbox', className: 'controls-rate', checked: rates[name] });
      box.dataset['rate'] = name;
      box.addEventListener('change', () => setRate(name, box.checked));
      out.push(make('tr', {}, [make('td', { textContent: RATE_LABEL[name] }), make('td', {}, [box])]));
    }
    const [low, high] = MOUSE_SENSITIVITY_RANGE;
    const sensitivity = make('input', { type: 'number', id: 'controls-sensitivity', value: String(store.read(settings.mouseSensitivity)), step: 'any', min: String(low), max: String(high) });
    sensitivity.addEventListener('change', () => {
      const v = sensitivity.valueAsNumber;
      if (!Number.isFinite(v) || v < low || v > high) status.setStatus(`mouse sensitivity: a number from ${low} to ${high}`, { failure: true });
      else store.write(settings.mouseSensitivity, v);
      render();
    });
    out.push(make('tr', {}, [make('td', { textContent: 'Mouse sensitivity' }), make('td', {}, [sensitivity])]));
    return out;
  }

  function render(): void {
    if (!win.isOpen) return;
    const heading = (text: string): HTMLElement => make('tr', {}, [make('th', { colSpan: 3, textContent: text })]);
    const table = make('table', { id: 'controls-table' }, [
      heading('Mouse'),
      ...[...PRESS_ACTIONS, ...CLICK_ACTIONS, ...DOUBLE_ACTIONS].map((a) => bindingRow(a, 'mouse')),
      heading('Keys'),
      ...KEY_ACTIONS.map((a) => bindingRow(a, 'keys')),
      heading('Rates'),
      ...rateRows(),
    ]);
    const resetAll = make('button', { type: 'button', id: 'controls-reset', textContent: 'Reset all', title: 'every binding and rate back to its default' });
    resetAll.addEventListener('click', () => {
      listening = null;
      store.clear(settings.input);
      render();
    });
    win.body.replaceChildren(table, resetAll);
  }

  // Listening for a key: the next key is the binding, and goes nowhere else.
  window.addEventListener(
    'keydown',
    (e) => {
      if (listening === null || !win.isOpen) return;
      const isKey = (KEY_ACTIONS as readonly string[]).includes(listening);
      if (!isKey) {
        if (e.key !== 'Escape') return;
        listening = null;
      } else {
        const got = keyBindingOf(e);
        if (!got) return;
        const action = listening as KeyAction;
        listening = null;
        const next = stored();
        store.write(settings.input, { ...next, keys: { ...next.keys, [action]: got } });
      }
      e.preventDefault();
      e.stopPropagation();
      render();
    },
    true,
  );

  button.addEventListener('click', () => {
    if (win.isOpen) {
      win.close();
      return;
    }
    // Above the button, at the bottom right; later where it was left (floating window).
    const width = 460;
    const height = Math.min(560, window.innerHeight - 56);
    win.open({ left: Math.max(8, window.innerWidth - width - 8), top: Math.max(8, window.innerHeight - height - 44), width, height });
    render();
  });

  const state = (): ControlsPanelState => ({ open: win.isOpen, listening, rows: { ...rows } });
  testApi.viewer({ controlsPanel: state, inputMap: () => resolveInput(stored()), defaultInput: () => structuredClone(DEFAULT_INPUT) });
}
