// The ground grid toggle and the skybox picker.
'use strict';

(() => {
  const app = window.SC2App;
  const { ground, skyScene, viewer } = app;
  const gridButton = app.$('grid-toggle');
  const skyButton = app.$('sky-button');

  /** The skybox shown: { id, name, file, model, instance } or null. */
  app.sky = null;

  function setGrid(on) {
    ground.enabled = Boolean(on);
    gridButton.classList.toggle('on', ground.enabled);
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
    if (!mine) return;
    app.pending++;
    try {
      const model = await viewer.load(app.modelUrl(mine.file), app.pathSolver);
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
      }
      app.setStatus(error.message);
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
  skyButton.addEventListener('click', () => skyPicker.open().catch((error) => app.setStatus(error.message)));

  Object.assign(app, { setGrid, setSky });
})();
