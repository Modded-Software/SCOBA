// The landmarks drop-down of the view tools. The landmarks themselves are
// the camera service's (core/landmarks.ts).
// - The pin button saves the current view as a landmark, after asking a name.
// - "add all" adds one per run, framing its new block (features/addall).
// - Each landmark of the list but the origin has a trash button; it asks before deleting.

import type { Feature } from '../../core/context';
import { byId, make } from '../../core/dom';
import type { Landmark } from '../../core/types';
import { ConfirmDialog } from '../../ui/components/dialog';
import { Dropdown } from '../../ui/components/dropdown';

const TRASH = '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M6 1h4l1 1h3v2H2V2h3zM3 5h10l-1 10H4zm3 2v6h1V7zm3 0v6h1V7z"/></svg>';

export const landmarksFeature: Feature = {
  id: 'landmarks',
  install({ camera, status, events, testApi }) {
    const button = byId('landmarks-button');
    const pinButton = byId('landmark-pin');
    const listNode = byId('landmarks-list');

    const dropdown = new Dropdown({ root: byId('landmarks'), button, list: listNode });
    const closeList = (): void => dropdown.close();

    function render(): void {
      const { list, selected } = camera.landmarkState();
      const chosen = list.find((l) => l.id === selected);
      button.textContent = chosen ? chosen.name : 'landmarks';
      listNode.replaceChildren(
        ...list.map((l) => {
          const go = make('button', { className: 'go', textContent: l.name, title: 'go to this view' });
          go.addEventListener('click', () => {
            camera.goToLandmark(l.id);
            closeList();
          });
          const row = make('li', {}, [go]);
          row.dataset.id = String(l.id);
          row.classList.toggle('selected', l.id === selected);
          if (l.id !== camera.originId) {
            const trash = make('button', { className: 'trash', title: `delete "${l.name}"`, innerHTML: TRASH });
            trash.addEventListener('click', () => {
              closeList();
              askDelete(l).catch(status.reportFailure);
            });
            row.append(trash);
          }
          return row;
        }),
      );
    }
    events.on('landmarks-changed', render);

    // ---- dialogs: name a new landmark, confirm a delete ----

    const question = make('div', { className: 'question' });
    const deleteDialog = new ConfirmDialog({ id: 'landmark-delete-dialog', title: 'delete landmark', yesText: 'delete', content: [question] });

    async function askDelete(landmark: Landmark): Promise<void> {
      question.textContent = `Delete the landmark "${landmark.name}"?`;
      const asking = deleteDialog.ask();
      deleteDialog.no.focus();
      if (await asking) camera.removeLandmark(landmark.id);
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
      const now = camera.camera;
      const view = { target: [...now.target] satisfies Landmark['target'], yaw: now.yaw, pitch: now.pitch, distance: now.distance };
      const list = camera.landmarks();
      let n = 1;
      while (list.some((l) => l.name === `landmark ${n}`)) n++;
      nameBox.value = `landmark ${n}`;
      nameDialog.yes.disabled = false;
      const asking = nameDialog.ask();
      nameBox.focus();
      nameBox.select();
      if (await asking) camera.addLandmark({ name: nameBox.value.trim(), ...view });
    }
    pinButton.addEventListener('click', () => {
      closeList();
      pin().catch(status.reportFailure);
    });

    render();
    testApi.app({
      addLandmark: camera.addLandmark,
      goToLandmark: camera.goToLandmark,
      removeLandmark: camera.removeLandmark,
      landmarkState: camera.landmarkState,
      landmarks: camera.landmarks,
    });
  },
};
