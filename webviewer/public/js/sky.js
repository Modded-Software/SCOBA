// The ground grid toggle and the skybox picker.
'use strict';

(() => {
  const app = window.SC2App;
  const { ground, skyScene, viewer } = app;
  const gridButton = app.$('grid-toggle');
  const skyButton = app.$('sky-button');

  /** The skybox shown: { id, name, file, model, instance } or null. */
  app.sky = null;

  // The grid toggle and the sky are kept in localStorage, so a reload shows
  // the view as it was (the camera: core.js).
  const KEY = 'sc2viewer.view';

  function saveView() {
    const sky = app.sky ? { id: app.sky.id, name: app.sky.name, file: app.sky.file } : null;
    localStorage.setItem(KEY, JSON.stringify({ grid: ground.enabled, sky }));
  }

  function setGrid(on) {
    ground.enabled = Boolean(on);
    gridButton.classList.toggle('on', ground.enabled);
    saveView();
  }
  gridButton.addEventListener('click', () => setGrid(!ground.enabled));

  /** Show a skybox ({ id, name, file }), or none (null). */
  async function setSky(choice) {
    if (app.sky && app.sky.instance) app.sky.instance.detach();
    // The choice holds at once; its model follows when loaded.
    const mine = choice ? { id: choice.id, name: choice.name, file: choice.file, model: null, instance: null } : null;
    app.sky = mine;
    skyButton.classList.toggle('on', Boolean(choice));
    skyButton.title = choice ? 'skybox: ' + choice.name : 'choose a skybox';
    saveView();
    if (!mine) return;
    app.pending++;
    try {
      // Skyboxes are the default dataset's, whatever the current one is (server loadSkyboxes).
      const from = app.defaultDataset();
      const model = await viewer.load(app.modelUrl(mine.file, from), app.pathSolver(from));
      if (!model) throw new Error('cannot load ' + mine.file);
      if (app.sky !== mine) return; // another sky was chosen meanwhile
      const instance = model.addInstance();
      if (model.sequences.length) {
        instance.setSequence(0);
        instance.setSequenceLoopMode(2);
      }
      skyScene.addInstance(instance);
      Object.assign(mine, { model, instance });
      app.reportUndrawn(mine.name, model);
    } catch (error) {
      if (app.sky === mine) {
        app.sky = null;
        skyButton.classList.remove('on');
        saveView();
      }
      app.setStatus(error.message, { failure: true });
      throw error;
    } finally {
      app.pending--;
    }
  }

  const skyPicker = new SC2Components.Picker({
    id: 'sky-dialog',
    title: 'skybox',
    hint: 'search skyboxes',
    none: '(none)',
    fetchPage: (q, offset, limit) => app.getJson('/api/skyboxes?' + new URLSearchParams({ q, offset: String(offset), limit: String(limit) })),
    describe: (s) => ({ id: s.id, name: s.name, sub: s.file }),
    onPick: (choice) => setSky(choice).catch(app.reportFailure),
  });
  skyButton.addEventListener('click', () => skyPicker.open().catch((error) => app.reportFailure(error)));

  /**
   * At startup, once the datasets are known: the stored grid toggle and sky.
   * A stored value that is not a view is refused and reported.
   */
  async function restoreView() {
    const text = localStorage.getItem(KEY);
    if (text === null) return;
    let stored;
    try {
      stored = JSON.parse(text);
      if (!stored || typeof stored.grid !== 'boolean') throw new Error('no grid setting');
      const sky = stored.sky;
      if (sky !== null && !(sky && [sky.id, sky.name, sky.file].every((v) => typeof v === 'string' && v))) throw new Error('the sky is not a skybox');
    } catch (error) {
      console.warn(`sc2viewer: stored view settings refused: ${error.message}`);
      saveView();
      return;
    }
    setGrid(stored.grid);
    if (stored.sky) await setSky(stored.sky);
  }

  Object.assign(app, { setGrid, setSky, restoreView });
})();
