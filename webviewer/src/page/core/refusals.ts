// Refused stored settings (SPEC-VIEWER 10.3, R-VIEW-73). A stored key the
// page cannot use stops the start; nothing is put in its place. The panel
// lists each key, what is stored and why it is refused. "Clear refused
// settings" removes exactly those keys and reloads: the page then starts
// with the declared defaults for them (core/settings.ts).
//
// Two checks find them: main.ts reads every key before the page starts
// (refusedSettings), and core/datasets.ts checks the game and dataset
// choices against the server (SettingsRefused).

import { make } from './dom';
import { clearRefused, type RefusedSetting } from './settings';

/** Thrown at start when stored settings are refused; the start shows the panel. */
export class SettingsRefused extends Error {
  readonly refused: readonly RefusedSetting[];
  constructor(refused: readonly RefusedSetting[]) {
    super(`stored settings refused: ${refused.map((one) => `${one.key}: ${one.reason}`).join('; ')}`);
    this.name = 'SettingsRefused';
    this.refused = refused;
  }
}

/** Show the panel in place of the page: the refused keys and one way out. */
export function showRefusedSettings(refused: readonly RefusedSetting[], reload: () => void = () => location.reload()): HTMLElement {
  const rows = refused.map((one) => {
    const row = make('li', {}, [make('code', { className: 'refused-key', textContent: one.key }), make('code', { className: 'refused-stored', textContent: one.stored }), make('span', { className: 'refused-reason', textContent: one.reason })]);
    row.dataset['key'] = one.key;
    return row;
  });
  const clear = make('button', { type: 'button', id: 'settings-refused-clear', textContent: 'Clear refused settings', title: 'Remove these stored settings and reload; the page then uses their defaults' });
  clear.addEventListener('click', () => {
    clearRefused(refused.map((one) => one.key));
    reload();
  });
  const panel = make('section', { id: 'settings-refused', role: 'alertdialog' }, [
    make('h2', { textContent: 'Stored settings refused' }),
    make('p', { textContent: 'The page did not start: these stored settings cannot be used. Nothing was put in their place.' }),
    make('ul', {}, rows),
    clear,
  ]);
  document.body.append(panel);
  console.error(`viewer: ${new SettingsRefused(refused).message}`);
  return panel;
}
