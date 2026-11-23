// Landmarks: named camera views to jump back to (the view tools drop-down).
// - "origin" (looking at 0, 0, 0) is always there and cannot be deleted.
// - The pin button saves the current view as a landmark, after asking a name.
// - "add all" adds one per run, framing its new block and named after the
//   list filters.
// - Each landmark of the list has a trash button; it asks before deleting.
// - The landmarks and the one chosen are a setting (core/settings.ts).
// Framing a ground box and the filter names: frame.ts.

import { app, type CoreApi, type Landmark, type LandmarksApi } from '../../core/app';
import { byId, make } from '../../core/dom';
import { readSetting, settings, writeSetting, type Restore } from '../../core/settings';
import { ConfirmDialog } from '../../ui/components/dialog';
import { Dropdown } from '../../ui/components/dropdown';
import { filterName, frameBox } from './frame';

const ORIGIN_ID = 0;
const ORIGIN: Landmark = { id: ORIGIN_ID, name: 'origin (0, 0, 0)', target: [0, 0, 0], yaw: -Math.PI / 2, pitch: 0.5, distance: 9 };
const TRASH = '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M6 1h4l1 1h3v2H2V2h3zM3 5h10l-1 10H4zm3 2v6h1V7zm3 0v6h1V7z"/></svg>';

const copy = (l: Landmark): Landmark => ({ ...l, target: [...l.target] });

export function installLandmarks(core: CoreApi): LandmarksApi {
  const { camera } = core;
  const button = byId('landmarks-button');
  const pinButton = byId('landmark-pin');
  const listNode = byId('landmarks-list');

  const list: Landmark[] = [ORIGIN];
  let nextId = ORIGIN_ID + 1;
  /** The landmark chosen last, or null. */
  let selected: number | null = null;
  /** How the stored landmarks loaded (core/settings.ts). */
  let restore: Restore = 'none';

  function load(): void {
    const stored = readSetting(settings.landmarks);
    restore = stored.restore;
    if (!stored.value) return;
    list.push(...stored.value.list);
    nextId = Math.max(ORIGIN_ID, ...stored.value.list.map((l) => l.id)) + 1;
    selected = stored.value.selected;
  }

  function save(): void {
    writeSetting(settings.landmarks, { list: list.filter((l) => l.id !== ORIGIN_ID).map(copy), selected });
  }

  // ---- the drop-down list ----

  const dropdown = new Dropdown({ root: byId('landmarks'), button, list: listNode });
  const closeList = (): void => dropdown.close();

  function render(): void {
    const chosen = list.find((l) => l.id === selected);
    button.textContent = chosen ? chosen.name : 'landmarks';
    listNode.replaceChildren(
      ...list.map((l) => {
        const go = make('button', { className: 'go', textContent: l.name, title: 'go to this view' });
        go.addEventListener('click', () => {
          goToLandmark(l.id);
          closeList();
        });
        const row = make('li', {}, [go]);
        row.dataset.id = String(l.id);
        row.classList.toggle('selected', l.id === selected);
        if (l.id !== ORIGIN_ID) {
          const trash = make('button', { className: 'trash', title: `delete "${l.name}"`, innerHTML: TRASH });
          trash.addEventListener('click', () => {
            closeList();
            askDelete(l).catch(app().reportFailure);
          });
          row.append(trash);
        }
        return row;
      }),
    );
  }

  /** Add a landmark; a taken name gets " (2)", " (3)"... It becomes the chosen one. Returns its id. */
  function addLandmark(view: Omit<Landmark, 'id'>): number {
    let name = view.name;
    for (let n = 2; list.some((l) => l.name === name); n++) name = `${view.name} (${n})`;
    const landmark: Landmark = { id: nextId++, name, target: [...view.target], yaw: view.yaw, pitch: view.pitch, distance: view.distance };
    list.push(landmark);
    selected = landmark.id;
    save();
    render();
    return landmark.id;
  }

  function goToLandmark(id: number): void {
    const l = list.find((x) => x.id === id);
    if (!l) throw new Error(`no landmark ${id}`);
    app().view({ target: [...l.target], yaw: l.yaw, pitch: l.pitch, distance: l.distance });
    selected = id;
    save();
    render();
  }

  /** Delete a landmark. The camera stays; a deleted chosen one leaves none chosen. */
  function removeLandmark(id: number): void {
    if (id === ORIGIN_ID) throw new Error('the origin landmark cannot be deleted');
    const at = list.findIndex((l) => l.id === id);
    if (at < 0) throw new Error(`no landmark ${id}`);
    list.splice(at, 1);
    if (selected === id) selected = null;
    save();
    render();
  }

  // ---- dialogs: name a new landmark, confirm a delete ----

  const question = make('div', { className: 'question' });
  const deleteDialog = new ConfirmDialog({ id: 'landmark-delete-dialog', title: 'delete landmark', yesText: 'delete', content: [question] });

  async function askDelete(landmark: Landmark): Promise<void> {
    question.textContent = `Delete the landmark "${landmark.name}"?`;
    const asking = deleteDialog.ask();
    deleteDialog.no.focus();
    if (await asking) removeLandmark(landmark.id);
  }

  const nameBox = make('input', { id: 'landmark-name', type: 'text', autocomplete: 'off', spellcheck: false, maxLength: 60 });
  const nameDialog = new ConfirmDialog({ id: 'landmark-name-dialog', title: 'new landmark: this view', yesText: 'save', content: [nameBox] });
  nameDialog.yes.id = 'landmark-save';
  nameDialog.no.id = 'landmark-cancel';
  const nameOk = (): boolean => nameBox.value.trim().length > 0;
  nameBox.addEventListener('input', () => {
    nameDialog.yes.disabled = !nameOk();
  });
  nameBox.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && nameOk()) nameDialog.settle(true);
  });

  /** The pin button: ask a name, then keep the view as it was when the button was pressed. */
  async function pin(): Promise<void> {
    const view = { target: [...camera.target] satisfies Landmark['target'], yaw: camera.yaw, pitch: camera.pitch, distance: camera.distance };
    let n = 1;
    while (list.some((l) => l.name === `landmark ${n}`)) n++;
    nameBox.value = `landmark ${n}`;
    nameDialog.yes.disabled = false;
    const asking = nameDialog.ask();
    nameBox.focus();
    nameBox.select();
    if (await asking) addLandmark({ name: nameBox.value.trim(), ...view });
  }
  pinButton.addEventListener('click', () => {
    closeList();
    pin().catch(app().reportFailure);
  });

  load();
  render();

  return {
    addLandmark,
    goToLandmark,
    removeLandmark,
    /** For the tests: the landmarks, the chosen one, and how the stored ones loaded. */
    landmarkState: () => ({ list: list.map(copy), selected, restore }),
    frameBox,
    filterName,
    landmarks: () => list.map(copy),
  };
}
