// The page asks the server now and then whether a dataset's files changed
// on disk. When one did, a toast slides up at the bottom centre of the
// view: reload the data, yes or no. Yes rebuilds the dataset on the server
// and reloads the page (the scene is in the scene store, the camera a
// setting). No hides the toast until the files change again.

import { routes } from '../../../shared/protocol';
import type { DatasetInfo, DatasetsBody } from '../../../shared/records';
import { app, type DatasetReloadApi } from '../../core/app';
import { messageOf } from '../../core/dom';
import { Toast } from '../../ui/components/toast';

const POLL = 3000; // ms between checks for changed datasets

export function installDatasetReload(): DatasetReloadApi {
  const toast = new Toast({ id: 'dataset-toast' });
  const { text } = toast;
  const yes = toast.addButton('dataset-toast-yes', 'yes');
  const no = toast.addButton('dataset-toast-no', 'no');
  yes.classList.add('primary');
  /** The toast's subject while it is up; otherwise null. */
  let asked: { id: string; current: string } | null = null;
  /** Dataset id -> the changed state the user said "no" to. */
  const declined = new Map<string, string>();
  let busy = false;

  function showToast(dataset: DatasetInfo): void {
    asked = { id: dataset.id, current: dataset.current };
    yes.hidden = false;
    yes.disabled = false;
    no.disabled = false;
    no.textContent = 'no';
    // The bottom centre of the part of the view no panel covers.
    const view = app().visibleRect();
    toast.show(`Dataset "${dataset.label}" changed on disk. Reload the data?`, (view.left + view.right) / 2);
  }

  function hideToast(): void {
    asked = null;
    toast.hide();
  }

  no.addEventListener('click', () => {
    if (asked) declined.set(asked.id, asked.current);
    hideToast();
  });

  yes.addEventListener('click', () => {
    reload().catch((error: unknown) => app().reportFailure(error));
  });

  async function reload(): Promise<void> {
    if (!asked || busy) return;
    busy = true;
    yes.disabled = true;
    no.disabled = true;
    const { id } = asked;
    text.textContent = `Reloading dataset "${app().datasetLabel(id)}"…`;
    try {
      const response = await fetch(routes.reload(app().game(), id), { method: 'POST' });
      const body: unknown = await response.json();
      const error: unknown = typeof body === 'object' && body !== null ? Reflect.get(body, 'error') : undefined;
      if (!response.ok) throw new Error(typeof error === 'string' && error ? error : `${response.status}`);
      // The scene is in the scene store and the camera a setting: a reload shows the same view with the new data.
      await app().flushScenes();
      location.reload();
    } catch (error) {
      console.warn('sc2viewer: dataset reload failed:', error);
      text.textContent = `Reload failed: ${messageOf(error)}`;
      yes.hidden = true;
      no.disabled = false;
      no.textContent = 'close';
      busy = false;
    }
  }

  /** Ask the server which datasets changed; put the toast up for the first one not declined. */
  async function check(): Promise<void> {
    const body = await app().getJson<DatasetsBody>(routes.datasets(app().game()));
    app().updateDatasets(body.datasets);
    // Back as loaded: an old "no" no longer counts.
    for (const dataset of body.datasets) if (!dataset.changed) declined.delete(dataset.id);
    if (busy) return;
    if (asked) {
      const subject = asked;
      const now = body.datasets.find((d) => d.id === subject.id);
      // Changed back, or gone: nothing to ask.
      if (!now || !now.changed) hideToast();
      else subject.current = now.current;
      return;
    }
    const next = body.datasets.find((d) => d.changed && app().hasDataset(d.id) && declined.get(d.id) !== d.current);
    if (next) showToast(next);
  }

  function poll(): void {
    check()
      .catch((error: unknown) => console.warn('sc2viewer: dataset check failed:', error))
      .finally(() => setTimeout(poll, POLL));
  }

  return {
    checkDatasets: check,
    datasetToast: () => ({ up: toast.isUp, dataset: asked ? asked.id : null, text: text.textContent }),
    startDatasetPolling: () => {
      setTimeout(poll, POLL);
    },
  };
}
