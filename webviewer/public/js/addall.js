// "add all": adds one instance of every unit the unit list shows (search,
// race, kind and family filters), after a dialog asks to confirm the count.
// Skybox units (a backdrop model, server markSkyboxUnits) are left out, and
// the dialog names them.
// The new units are laid out on the ground by size, smallest first, in
// small, medium and large clusters, each with its own cell size;
// on a map with units already, the block goes next to them (arrange).
// The camera then frames the new block, kept as a landmark (landmarks.js)
// named after the list filters.
'use strict';

(() => {
  const app = window.SC2App;
  const { el } = app;
  const button = app.$('add-all');

  const PAGE = 500; // the server's largest page
  const LOADERS = 6; // models loading at once
  const GAP = 0.5; // world units between neighbours

  /** What the last run did, for the tests and the status line. */
  const run = { asked: 0, added: 0, failed: [], running: false, layout: [], landmark: null, skipped: [] };

  // ---- confirm dialog ----

  const dialog = new SC2Components.Dialog({ id: 'add-all-dialog', title: 'add all' });
  dialog.node.classList.add('confirm-dialog');
  const question = el('div', { className: 'question' });
  const yes = el('button', { id: 'add-all-yes', textContent: 'add' });
  const no = el('button', { id: 'add-all-no', textContent: 'cancel' });
  dialog.body.append(question, el('div', { className: 'answers' }, [no, yes]));
  let answer = null; // resolves the open question: true (add) or false
  const settle = (value) => {
    const done = answer;
    answer = null;
    dialog.close();
    if (done) done(value);
  };
  yes.addEventListener('click', () => settle(true));
  no.addEventListener('click', () => settle(false));
  // Escape, the x and the backdrop close the dialog: that is a "no".
  dialog.node.addEventListener('close', () => settle(false));

  function ask(text) {
    question.textContent = text;
    return new Promise((resolve) => {
      answer = resolve;
      dialog.open();
      yes.focus();
    });
  }

  // ---- the run ----

  /** Every unit the list shows, all pages. */
  async function listedUnits() {
    const query = app.unitQuery();
    const units = [];
    let total = Infinity;
    while (units.length < total) {
      const page = await app.getJson('/api/units?' + new URLSearchParams({ ...query, offset: String(units.length), limit: String(PAGE) }));
      total = page.total;
      if (!page.items.length) break;
      units.push(...page.items);
    }
    if (units.length !== total) throw new Error(`add all: the list changed while it was read (${units.length} of ${total})`);
    return units;
  }

  /** Bounding size on the ground: the diameter of the model's bounds, scaled as drawn. */
  const size = (item) => 2 * item.model.bounds.r * Math.max(item.dataScale[0], item.dataScale[1]) * item.scale;

  /** Ground box of items, each a square of its size around its centre; null for none. */
  function footprint(list) {
    if (!list.length) return null;
    const box = { x0: Infinity, x1: -Infinity, y0: Infinity, y1: -Infinity };
    for (const item of list) {
      const h = size(item) / 2;
      box.x0 = Math.min(box.x0, item.x - h);
      box.x1 = Math.max(box.x1, item.x + h);
      box.y0 = Math.min(box.y0, item.y - h);
      box.y1 = Math.max(box.y1, item.y + h);
    }
    return box;
  }

  const CLUSTERS = 3; // small, medium, large

  /**
   * Split sizes (ascending) into up to CLUSTERS runs of the sorted list, so
   * smallest first still holds across clusters. The splits are the ones
   * with the least ground area: sum over clusters of count x cell squared,
   * the cell being the cluster's largest size plus GAP. An outlier then
   * gets a cluster of its own instead of setting everyone's cell.
   * Returns the index where each cluster starts.
   */
  function clusterStarts(sizes) {
    const n = sizes.length;
    if (!n) return [];
    // Area of the cluster holding sizes[i .. j-1].
    const area = (i, j) => (j - i) * (sizes[j - 1] + GAP) ** 2;
    let best = { cost: area(0, n), starts: [0] };
    for (let a = 1; a < n; a++) {
      const two = area(0, a) + area(a, n);
      if (two < best.cost) best = { cost: two, starts: [0, a] };
      if (CLUSTERS < 3) continue;
      for (let b = a + 1; b < n; b++) {
        const three = area(0, a) + area(a, b) + area(b, n);
        if (three < best.cost) best = { cost: three, starts: [0, a, b] };
      }
    }
    return best.starts;
  }

  /**
   * Smallest first, in size clusters (small, medium, large). Each cluster is
   * a near-square grid of equal cells, the cell its largest size plus GAP,
   * so an outlier sets the cells of its own cluster only. The clusters stand
   * side by side, small to large, top edges aligned. On an empty scene the
   * block is centred on the origin. With units already there (`others`) it
   * goes next to them, GAP away: below them when their footprint is wider
   * than deep, else to the right, so repeated runs stay together.
   */
  function arrange(list, others = []) {
    const sorted = [...list].sort((a, b) => size(a) - size(b));
    const starts = clusterStarts(sorted.map(size));
    const clusters = starts.map((start, k) => {
      const members = sorted.slice(start, k + 1 < starts.length ? starts[k + 1] : sorted.length);
      const cell = size(members[members.length - 1]) + GAP;
      const cols = Math.ceil(Math.sqrt(members.length));
      return { members, cell, cols, width: cols * cell, depth: Math.ceil(members.length / cols) * cell };
    });
    const depth = Math.max(0, ...clusters.map((c) => c.depth));
    const blockWidth = clusters.reduce((sum, c) => sum + c.width, 0);
    // Where the block's centre goes.
    let cx = 0;
    let cy = 0;
    const near = footprint(others);
    if (near) {
      if (near.x1 - near.x0 >= near.y1 - near.y0) {
        cx = (near.x0 + near.x1) / 2;
        cy = near.y0 - GAP - depth / 2;
      } else {
        cx = near.x1 + GAP + blockWidth / 2;
        cy = (near.y0 + near.y1) / 2;
      }
    }
    const top = cy + depth / 2;
    let left = cx - blockWidth / 2;
    const layout = [];
    clusters.forEach((c, k) => {
      c.members.forEach((item, i) => {
        const col = i % c.cols;
        const row = Math.floor(i / c.cols);
        app.setPosition(item, left + (col + 0.5) * c.cell, top - (row + 0.5) * c.cell);
        layout.push({ id: item.id, size: size(item), x: item.x, y: item.y, cluster: k, cell: c.cell });
      });
      left += c.width;
    });
    app.saveHash();
    return layout;
  }

  async function addAll() {
    if (run.running) return;
    // The filters as the list showed them: the landmark's name.
    const name = app.filterName(app.unitQuery());
    const listed = await listedUnits();
    // Skybox units are backdrops, not units to stand on the map: left out, and said so.
    const skipped = listed.filter((unit) => unit.skybox);
    const ids = listed.filter((unit) => !unit.skybox).map((unit) => unit.id);
    const skippedText = skipped.length ? ` ${skipped.length} skybox unit${skipped.length === 1 ? ' is' : 's are'} left out: ${skipped.map((unit) => unit.id).join(', ')}.` : '';
    if (!ids.length) {
      app.setStatus(listed.length ? `add all: only skybox units in the list.${skippedText}` : 'add all: the list is empty');
      return;
    }
    const sure = await ask(`Are you sure you want to add ${ids.length} unit${ids.length === 1 ? '' : 's'} to the map?${skippedText}`);
    if (!sure) return;
    Object.assign(run, { asked: ids.length, added: 0, failed: [], running: true, layout: [], landmark: null, skipped: skipped.map((unit) => unit.id) });
    // The units already on the map: the new block goes next to them.
    const before = new Set(app.items.map((item) => item.id));
    const made = [];
    let next = 0;
    const worker = async () => {
      while (next < ids.length) {
        const id = ids[next++];
        try {
          made.push(await app.addUnit(id));
          run.added++;
        } catch (error) {
          run.failed.push(`${id}: ${error.message}`);
        }
        app.setStatus(`add all: ${run.added + run.failed.length} of ${ids.length}`);
      }
    };
    try {
      await Promise.all(Array.from({ length: LOADERS }, worker));
      const items = made.map((id) => app.items.find((item) => item.id === id)).filter(Boolean);
      run.layout = arrange(items, app.items.filter((item) => before.has(item.id)));
      // Look at the new block and keep the view as a landmark.
      if (run.layout.length) {
        const box = {
          x0: Math.min(...run.layout.map((l) => l.x - l.cell / 2)),
          x1: Math.max(...run.layout.map((l) => l.x + l.cell / 2)),
          y0: Math.min(...run.layout.map((l) => l.y - l.cell / 2)),
          y1: Math.max(...run.layout.map((l) => l.y + l.cell / 2)),
        };
        run.landmark = app.addLandmark({ name, ...app.frameBox(box) });
      }
      app.setStatus(run.failed.length ? `add all: ${run.added} added, ${run.failed.length} failed: ${run.failed.join('; ')}` : `add all: ${run.added} added`);
      for (const line of run.failed) console.warn('add all failed: ' + line);
    } finally {
      run.running = false;
    }
  }

  button.addEventListener('click', () => addAll().catch(app.reportFailure));

  Object.assign(app, {
    addAll,
    arrangeBySize: arrange,
    addAllState: () => ({ ...run, failed: [...run.failed], skipped: [...run.skipped], layout: run.layout.map((l) => ({ ...l })), dialogOpen: dialog.isOpen, question: question.textContent }),
  });
})();
