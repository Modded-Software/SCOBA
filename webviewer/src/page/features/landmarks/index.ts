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
import { TRASH } from '../../ui/icons';

export const landmarksFeature: Feature = {
  id: 'landmarks',
  install({ camera, status, events, testApi }) {
    const button = byId('landmarks-button');
    const pinButton = byId('landmark-pin');
    const listNode = byId('landmarks-list');

    // The wheel and Up/Down on the button go to the landmark before or after (SPEC-VIEWER 16.14).
    const landmarkAt = (index: number): Landmark | undefined => camera.landmarkState().list[index];
    const dropdown = new Dropdown({
      root: byId('landmarks'),
      button,
      list: listNode,
      steps: {
        current: () => {
          const { list, selected } = camera.landmarkState();
          return list.findIndex((l) => l.id === selected);
        },
        count: () => camera.landmarkState().list.length,
        usable: () => true,
        choose: (index) => {
          const landmark = landmarkAt(index);
          if (landmark) camera.goToLandmark(landmark.id);
        },
      },
    });
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
            const trash = make('button', { className: 'trash', title: `Delete Landmark "${l.name}"`, innerHTML: TRASH });
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
    const deleteDialog = new ConfirmDialog({ id: 'landmark-delete-dialog', title: 'Delete Landmark', yesText: 'Delete Landmark', content: [question], danger: true });

    async function askDelete(landmark: Landmark): Promise<void> {
      question.textContent = `Delete the landmark "${landmark.name}"?`;
      const asking = deleteDialog.ask();
      deleteDialog.no.focus();
      if (await asking) camera.removeLandmark(landmark.id);
    }

    const nameBox = make('input', { id: 'landmark-name', type: 'text', autocomplete: 'off', spellcheck: false, maxLength: 60 });
    const nameDialog = new ConfirmDialog({ id: 'landmark-name-dialog', title: 'New landmark: this view', yesText: 'Save', content: [nameBox] });
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
      // The exact view, at full precision: during a zoom glide, the distance it ends at (R-VIEW-144).
      const now = camera.camera;
      const view = { target: [...now.target] satisfies Landmark['target'], yaw: now.yaw, pitch: now.pitch, distance: camera.zoomGoal() ?? now.distance };
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
