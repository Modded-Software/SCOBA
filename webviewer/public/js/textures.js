// The texture window: the HD texture viewer (scripts/hdtex/compare.html,
// served below /textures/) in a movable window over the view. It is hidden
// until a double-click on a unit or doodad: a gallery row, an instance row,
// or an instance in the view. It then lists that unit's or doodad's
// textures:
// - the ones with an HD version, original beside upscaled (the page's own
//   entries, filtered by ?user=);
// - every other texture its model file names, the original alone. Those are
//   read here: the model's layers name them, the dataset serves them, and
//   the renderer's DDS reader decodes them (originals).
// The viewer's "used by" chip drops the filter.
'use strict';

(() => {
  const app = window.SC2App;
  const { el, viewer } = app;

  const MARGIN = 16;
  const TOP = 48; // below the view tools
  const SIZE = [900, 620];
  const DDS_FOURCC = 84; // byte offset of the pixel format's FourCC in a DDS file

  const frame = el('iframe', { id: 'texture-frame', title: 'textures' });
  const win = new SC2Components.FloatingWindow({ id: 'texture-window', title: 'textures' });
  win.body.append(frame);
  // Keys go to the frame once it was clicked: Escape there closes the window
  // too. In the viewer's search box Escape only leaves the box.
  frame.addEventListener('load', () => {
    frame.contentWindow.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !e.target.matches('input')) win.close();
      // Ctrl+H and Ctrl+L belong to the viewer (hd.js): not the browser's history or address bar here either.
      if (e.ctrlKey && !e.altKey && !e.metaKey && !e.shiftKey && ['h', 'l'].includes(e.key.toLowerCase())) e.preventDefault();
    });
  });
  /** What the window shows: { user, dataset, file }; null before the first one. */
  let shown = null;
  /** Counts the opens, so a slow read for an earlier one is dropped. */
  let turn = 0;
  /** Object URLs of the decoded originals handed to the frame. */
  let urls = [];
  /** 'none', 'loading', 'done', or 'failed: <why>': the originals of what is shown. */
  let originalState = 'none';

  /** Where the window opens first: right of the open panels, as large as fits. */
  function firstPlace() {
    const left = app.visibleRect().left + MARGIN;
    return { left, top: TOP, width: Math.min(SIZE[0], innerWidth - left - MARGIN), height: Math.min(SIZE[1], innerHeight - TOP - MARGIN) };
  }

  /** RGBA pixels as a PNG object URL. */
  function pngUrl(width, height, rgba) {
    const canvas = el('canvas', { width, height });
    canvas.getContext('2d').putImageData(new ImageData(rgba, width, height), 0, 0);
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (!blob) return reject(new Error(`cannot encode ${width}x${height}`));
        const url = URL.createObjectURL(blob);
        urls.push(url);
        return resolve(url);
      }, 'image/png');
    });
  }

  /** One texture file, decoded: its colour, and its alpha when that is not one value all over. */
  async function decode(source, dataset) {
    const response = await fetch(app.pathSolver(dataset)(source));
    if (!response.ok) throw new Error(`${response.status}`);
    if (!source.endsWith('.dds')) throw new Error('not a DDS file');
    const bytes = await response.arrayBuffer();
    const image = new ModelViewer.parsers.dds.Image();
    image.load(bytes);
    const { width, height, data } = image.getMipmap(0);
    const fourCC = String.fromCharCode(...new Uint8Array(bytes, DDS_FOURCC, 4)).replace(/\0+$/, '');
    const color = new Uint8ClampedArray(data);
    const alpha = new Uint8ClampedArray(data.length);
    let flat = true;
    for (let i = 0; i < data.length; i += 4) {
      const a = data[i + 3];
      if (a !== data[3]) flat = false;
      alpha.set([a, a, a, 255], i);
      color[i + 3] = 255;
    }
    const planes = [{ plane: 'color', image: await pngUrl(width, height, color) }];
    if (!flat) planes.push({ plane: 'alpha', image: await pngUrl(width, height, alpha) });
    return { texture: source.split('\\').pop(), format: fourCC || 'uncompressed', size: [width, height], planes };
  }

  /** Every texture the layers of a model file name, decoded; and the ones that failed, with why. */
  async function originals(file, dataset) {
    const model = await viewer.load(app.modelUrl(file, dataset), app.pathSolver(dataset));
    if (!model) throw new Error(`cannot load ${file}`);
    const sources = new Set();
    for (const material of model.materials[1]) {
      for (const layer of material.layers) if (layer.active && !layer.constant && layer.source) sources.add(layer.source.replaceAll('/', '\\'));
    }
    const textures = [];
    const failed = [];
    for (const source of [...sources].sort()) {
      await decode(source, dataset).then(
        (texture) => textures.push(texture),
        (error) => failed.push(`${source.split('\\').pop()} (${error.message})`),
      );
    }
    return { textures, failed };
  }

  const frameLoaded = () =>
    new Promise((resolve) => {
      frame.addEventListener('load', resolve, { once: true });
    });

  /**
   * Open the window on the textures of `user` (a unit or doodad id, or a
   * model file's name), called `name`, whose model file is `file` in `dataset`.
   */
  async function openTextures({ user, name, file, dataset }) {
    const built = await app.getJson('/api/textures');
    if (!built.built) throw new Error(`the texture viewer is not built; run: ${built.build}`);
    win.title.textContent = `textures · ${name}`;
    win.open(firstPlace());
    if (shown && shown.user === user && shown.file === file && shown.dataset === dataset) return;
    shown = { user, file, dataset };
    const mine = ++turn;
    for (const url of urls) URL.revokeObjectURL(url);
    urls = [];
    originalState = 'loading';
    const loaded = frameLoaded();
    frame.src = `/textures/?${new URLSearchParams({ user, embed: '1' })}`;
    try {
      const [found] = await Promise.all([originals(file, dataset), loaded]);
      if (mine !== turn) return;
      frame.contentWindow.hdtex.addOriginals(user, found.textures, found.failed);
      originalState = 'done';
    } catch (error) {
      if (mine === turn) originalState = `failed: ${error.message}`;
      throw error;
    }
  }

  /** The same for a unit or doodad of the gallery: its record's model file (a doodad's first variation). */
  async function openTexturesFor(kind, id) {
    const dataset = app.dataset();
    const record = await app.record(kind, id, dataset);
    const file = kind === 'doodad' ? record.files[0] : record.file;
    if (!file) throw new Error(`${record.name} has no model file`);
    return openTextures({ user: id, name: record.name, file, dataset });
  }

  /** The same for an instance of the scene: the model file it shows. A bare model file goes by its file name. */
  function openTexturesOf(item) {
    const fileName = item.path.split('\\').pop();
    return openTextures({ user: item.unit ? item.unit.id : fileName, name: item.unit ? item.unit.name : fileName, file: item.path, dataset: item.dataset });
  }

  app.canvas.addEventListener('dblclick', (e) => {
    const item = app.itemAt(e.clientX, e.clientY);
    if (item) openTexturesOf(item).catch(app.reportFailure);
  });

  Object.assign(app, {
    openTexturesFor,
    openTexturesOf,
    /** For the tests: whether the window is open, whose textures it shows, and how reading the originals went. */
    textureWindow: () => ({ open: win.isOpen, user: shown ? shown.user : null, file: shown ? shown.file : null, dataset: shown ? shown.dataset : null, originals: originalState }),
  });
})();
