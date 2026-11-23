// The scene list (SPEC-VIEWER section 10.2): a drop-down in the view tools.
// A click on a scene opens it; each has rename and delete; delete asks
// first. At the end: new, export, import. A refused stored scene is listed
// with its reason and can only be deleted.

import type { ScenesState } from '../../core/app';
import { app } from '../../core/app';
import { byId, byIdAs, make } from '../../core/dom';
import { ConfirmDialog } from '../../ui/components/dialog';
import { Dropdown } from '../../ui/components/dropdown';

export interface SceneListActions {
  state(): ScenesState;
  openScene(id: string): Promise<void>;
  newScene(name: string): Promise<string>;
  renameScene(id: string, name: string): Promise<void>;
  deleteScene(id: string): Promise<void>;
  exportScene(): string;
  importScene(text: string): Promise<string>;
}

const PENCIL = '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M11 1l4 4-9 9H2v-4zM10 4l2 2"/></svg>';
const TRASH = '<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="M6 1h4l1 1h3v2H2V2h3zM3 5h10l-1 10H4zm3 2v6h1V7zm3 0v6h1V7z"/></svg>';

/** A file name for a scene: its name with only letters, digits, "-" and "_". */
export const fileName = (name: string): string => `${name.replace(/[^A-Za-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '') || 'scene'}.scene.json`;

export function installSceneList(actions: SceneListActions): { render(): void } {
  const button = byId('scenes-button');
  const listNode = byId('scenes-list');
  const fileInput = byIdAs('scenes-import-file', HTMLInputElement);
  const dropdown = new Dropdown({ root: byId('scenes'), button, list: listNode });
  const report = (error: unknown): void => app().reportFailure(error);
  const run = (work: () => Promise<unknown>): void => {
    dropdown.close();
    work().catch(report);
  };

  // ---- dialogs: a name (new, rename), a delete ----

  const nameBox = make('input', { id: 'scene-name', type: 'text', autocomplete: 'off', spellcheck: false, maxLength: 80 });
  const nameDialog = new ConfirmDialog({ id: 'scene-name-dialog', title: 'scene name', yesText: 'save', content: [nameBox] });
  const nameOk = (): boolean => nameBox.value.trim().length > 0;
  nameBox.addEventListener('input', () => {
    nameDialog.yes.disabled = !nameOk();
  });
  nameBox.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && nameOk()) nameDialog.settle(true);
  });

  /** Ask a name; null when cancelled. */
  async function askName(title: string, start: string): Promise<string | null> {
    nameDialog.dialog.node.querySelector('.dialog-head span')?.replaceChildren(title);
    nameBox.value = start;
    nameDialog.yes.disabled = !nameOk();
    const asking = nameDialog.ask();
    nameBox.focus();
    nameBox.select();
    return (await asking) ? nameBox.value.trim() : null;
  }

  const question = make('div', { className: 'question' });
  const deleteDialog = new ConfirmDialog({ id: 'scene-delete-dialog', title: 'delete scene', yesText: 'delete', content: [question] });

  async function askDelete(id: string, label: string): Promise<void> {
    question.textContent = `Delete the scene "${label}"? This cannot be undone.`;
    const asking = deleteDialog.ask();
    deleteDialog.no.focus();
    if (await asking) await actions.deleteScene(id);
  }

  // ---- export and import ----

  function download(): void {
    const state = actions.state();
    const text = actions.exportScene();
    const url = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
    const link = make('a', { href: url, download: fileName(state.open?.name ?? 'scene') });
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  fileInput.addEventListener('change', () => {
    const file = fileInput.files?.[0];
    fileInput.value = '';
    if (!file) return;
    file
      .text()
      .then((text) => actions.importScene(text))
      .then(() => app().setStatus(`imported scene from ${file.name}`))
      .catch(report);
  });

  // ---- the list ----

  function iconButton(className: string, title: string, svg: string, onClick: () => void): HTMLButtonElement {
    const node = make('button', { className, title, innerHTML: svg });
    node.addEventListener('click', onClick);
    return node;
  }

  function render(): void {
    const state = actions.state();
    button.textContent = state.open ? state.open.name : 'scenes';
    const rows = state.list.map((scene) => {
      const go = make('button', { className: 'go', textContent: scene.name, title: `open "${scene.name}" (${scene.items} instances)` });
      go.addEventListener('click', () => run(() => actions.openScene(scene.id)));
      const rename = iconButton('rename', `rename "${scene.name}"`, PENCIL, () =>
        run(async () => {
          const name = await askName('rename scene', scene.name);
          if (name !== null) await actions.renameScene(scene.id, name);
        }),
      );
      const trash = iconButton('trash', `delete "${scene.name}"`, TRASH, () => run(() => askDelete(scene.id, scene.name)));
      const row = make('li', {}, [go, rename, trash]);
      row.dataset.id = scene.id;
      row.classList.toggle('selected', scene.id === state.open?.id);
      return row;
    });
    const broken = state.refused.map((scene) => {
      const label = scene.name ?? scene.id;
      const text = make('span', { className: 'go', textContent: `${label}: refused`, title: scene.reason });
      const trash = iconButton('trash', `delete "${label}"`, TRASH, () => run(() => askDelete(scene.id, label)));
      const row = make('li', { className: 'refused' }, [text, trash]);
      row.dataset.id = scene.id;
      return row;
    });
    const add = make('button', { id: 'scene-new', textContent: 'new', title: 'a new, empty scene' });
    add.addEventListener('click', () =>
      run(async () => {
        const name = await askName('new scene', `scene ${state.list.length + 1}`);
        if (name !== null) await actions.newScene(name);
      }),
    );
    const save = make('button', { id: 'scene-export', textContent: 'export', title: 'download the open scene as a file' });
    save.addEventListener('click', () => {
      dropdown.close();
      try {
        download();
      } catch (error) {
        report(error);
      }
    });
    const load = make('button', { id: 'scene-import', textContent: 'import', title: 'open a scene file' });
    load.addEventListener('click', () => {
      dropdown.close();
      fileInput.click();
    });
    listNode.replaceChildren(...rows, ...broken, make('li', { className: 'actions' }, [add, save, load]));
  }

  render();
  return { render };
}
