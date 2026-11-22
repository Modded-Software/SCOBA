// Datasets: where game data and assets come from (server-datasets.mjs).
// - The top left of the gallery panel holds the current dataset: the gallery lists it and new
//   instances come from it. The choice is kept in localStorage.
// - Every instance has its own dataset (scene.js), so the same unit can
//   stand side by side from two of them.
// - Every request names its dataset, and model and texture URLs carry the
//   dataset's signature, so a reloaded dataset is fetched anew.
// - The page asks the server now and then whether a dataset's files
//   changed on disk. When one did, a toast slides up at the bottom centre
//   of the view: reload the data, yes or no. Yes rebuilds the dataset on
//   the server and reloads the page (the scene is in the URL, the camera in
//   localStorage). No hides the toast until the files change again.
'use strict';

(() => {
  const app = window.SC2App;
  const { $, el } = app;
  const select = $('dataset');

  const KEY = 'sc2viewer.dataset';
  const POLL = 3000; // ms between checks for changed datasets

  /** Id -> { id, label, signature, changed, current, ... } as the server lists them. */
  const known = new Map();
  let defaultId = null; // the server's default dataset
  let current = null;
  const listeners = [];

  /** The dataset id, checked: an unknown one is an error. */
  function requireDataset(id) {
    if (!known.has(id)) throw new Error(`no dataset "${id}" (have: ${[...known.keys()].join(', ')})`);
    return id;
  }

  const version = (id) => known.get(requireDataset(id)).signature ?? '';
  /** An API URL that reads `dataset` (default: the current one). */
  const api = (route, params = {}, dataset = current) => `${route}?${new URLSearchParams({ ...params, dataset: requireDataset(dataset) })}`;

  /** A unit or doodad record ('unit', 'doodad') from a dataset. */
  async function record(kind, id, dataset = current) {
    const url = api(`/api/${kind}`, { id }, dataset);
    const response = await fetch(url);
    if (response.status === 404) throw new Error(`${id} is not in dataset "${dataset}"`);
    if (!response.ok) throw new Error(`${response.status} ${url}`);
    return response.json();
  }

  function setDataset(id) {
    requireDataset(id);
    if (id === current) return;
    current = id;
    select.value = id;
    localStorage.setItem(KEY, id);
    for (const listener of listeners) listener(id);
  }
  select.addEventListener('change', () => setDataset(select.value));

  function take(body) {
    known.clear();
    for (const dataset of body.datasets) known.set(dataset.id, dataset);
    defaultId = body.default;
  }

  /** Read the datasets and choose the current one: the stored choice when it still exists. */
  async function setupDatasets() {
    const body = await app.getJson('/api/datasets');
    take(body);
    for (const problem of body.problems) console.warn(`sc2viewer: not a dataset: ${problem.dir}: ${problem.reason}`);
    select.replaceChildren(...body.datasets.map((d) => el('option', { value: d.id, textContent: d.label })));
    const stored = localStorage.getItem(KEY);
    current = stored !== null && known.has(stored) ? stored : defaultId;
    select.value = current;
    setTimeout(poll, POLL);
  }

  // ---- changed datasets: the toast ----

  const toast = new SC2Components.Toast({ id: 'dataset-toast' });
  const { text } = toast;
  const yes = toast.addButton('dataset-toast-yes', 'yes');
  const no = toast.addButton('dataset-toast-no', 'no');
  yes.classList.add('primary');
  /** The toast's subject while it is up: { id, current }; otherwise null. */
  let asked = null;
  /** Dataset id -> the changed state the user said "no" to. */
  const declined = new Map();
  let busy = false;

  function showToast(dataset) {
    asked = { id: dataset.id, current: dataset.current };
    yes.hidden = false;
    yes.disabled = false;
    no.disabled = false;
    no.textContent = 'no';
    // The bottom centre of the part of the view no panel covers.
    const view = app.visibleRect();
    toast.show(`Dataset "${dataset.label}" changed on disk. Reload the data?`, (view.left + view.right) / 2);
  }

  function hideToast() {
    asked = null;
    toast.hide();
  }

  no.addEventListener('click', () => {
    if (asked) declined.set(asked.id, asked.current);
    hideToast();
  });

  yes.addEventListener('click', async () => {
    if (!asked || busy) return;
    busy = true;
    yes.disabled = true;
    no.disabled = true;
    const { id } = asked;
    text.textContent = `Reloading dataset "${known.get(id).label}"…`;
    try {
      const response = await fetch(`/api/dataset/reload?${new URLSearchParams({ id })}`, { method: 'POST' });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `${response.status}`);
      // The scene is in the URL and the camera in localStorage: a reload shows the same view with the new data.
      location.reload();
    } catch (error) {
      console.warn('sc2viewer: dataset reload failed:', error);
      text.textContent = `Reload failed: ${error.message}`;
      yes.hidden = true;
      no.disabled = false;
      no.textContent = 'close';
      busy = false;
    }
  });

  /** Ask the server which datasets changed; put the toast up for the first one not declined. */
  async function check() {
    const body = await app.getJson('/api/datasets');
    for (const dataset of body.datasets) {
      const mine = known.get(dataset.id);
      if (mine) Object.assign(mine, { changed: dataset.changed, current: dataset.current });
      // Back as loaded: an old "no" no longer counts.
      if (!dataset.changed) declined.delete(dataset.id);
    }
    if (busy) return;
    if (asked) {
      const now = body.datasets.find((d) => d.id === asked.id);
      // Changed back, or gone: nothing to ask.
      if (!now || !now.changed) hideToast();
      else asked.current = now.current;
      return;
    }
    const next = body.datasets.find((d) => d.changed && known.has(d.id) && declined.get(d.id) !== d.current);
    if (next) showToast(next);
  }

  function poll() {
    check()
      .catch((error) => console.warn('sc2viewer: dataset check failed:', error))
      .finally(() => setTimeout(poll, POLL));
  }

  Object.assign(app, {
    setupDatasets,
    setDataset,
    requireDataset,
    record,
    api,
    dataset: () => current,
    defaultDataset: () => defaultId,
    datasets: () => [...known.values()].map((d) => ({ ...d })),
    onDatasetChange: (listener) => listeners.push(listener),
    checkDatasets: check,
    datasetToast: () => ({ up: toast.isUp, dataset: asked ? asked.id : null, text: text.textContent }),
    // A model path is fetched as-is. Anything a model asks for (textures) is
    // an in-model path, resolved by the server for the dataset.
    modelUrl: (path, dataset = current) => `/file?${new URLSearchParams({ path, dataset: requireDataset(dataset), v: version(dataset) })}`,
    pathSolver: (dataset = current) => {
      const tail = new URLSearchParams({ dataset: requireDataset(dataset), v: version(dataset) });
      return (src) => (typeof src === 'string' && !src.startsWith('/') ? `/asset?path=${encodeURIComponent(src)}&${tail}` : src);
    },
    iconUrl: (name, dataset = current) => `/icon/${name}?${new URLSearchParams({ dataset: requireDataset(dataset) })}`,
  });
})();
