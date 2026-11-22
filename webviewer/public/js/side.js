// The two panels on the left, the gallery (#panel) and the instances
// (#instances), are drawers: a tab at each one's right edge slides it out
// to the left and back. A closed panel takes no keys (inert) and leaves the
// view free (app.visibleRect). Which are open is kept in localStorage.
'use strict';

(() => {
  const app = window.SC2App;
  const { $ } = app;

  const KEY = 'sc2viewer.drawers';
  const DRAWERS = [
    { id: 'panel', tab: 'panel-tab', name: 'gallery' },
    { id: 'instances', tab: 'instances-tab', name: 'instances' },
  ];

  /** Stored open flags, { panel: bool, instances: bool }; both open when none are stored. */
  function load() {
    const stored = localStorage.getItem(KEY);
    if (stored === null) return { panel: true, instances: true };
    let open;
    try {
      open = JSON.parse(stored);
    } catch (error) {
      console.warn(`sc2viewer: stored drawers refused: ${error.message}`);
      return { panel: true, instances: true };
    }
    return { panel: open.panel !== false, instances: open.instances !== false };
  }

  const open = load();

  function apply() {
    for (const { id, tab, name } of DRAWERS) {
      const node = $(id);
      const button = $(tab);
      node.classList.toggle('closed', !open[id]);
      node.inert = !open[id];
      button.classList.toggle('closed', !open[id]);
      button.textContent = open[id] ? '\u2039' : '\u203A';
      button.title = `${open[id] ? 'hide' : 'show'} the ${name}`;
      button.setAttribute('aria-expanded', String(open[id]));
    }
  }

  /** Open or close one drawer ('panel' or 'instances'); no `to`: the other way. */
  function setDrawer(id, to) {
    if (!(id in open)) throw new Error(`drawer: no drawer "${id}"`);
    open[id] = to === undefined ? !open[id] : Boolean(to);
    localStorage.setItem(KEY, JSON.stringify(open));
    apply();
    // The status toast stays centred on the part of the view that shows.
    app.placeStatus();
  }

  for (const { id, tab } of DRAWERS) $(tab).addEventListener('click', () => setDrawer(id));
  // The toast moves when the slide ends: the panel's box is final then.
  for (const { id } of DRAWERS) $(id).addEventListener('transitionend', () => app.placeStatus());
  apply();

  Object.assign(app, {
    setDrawer,
    /** For the tests: which drawers are open. */
    drawerState: () => ({ ...open }),
  });
})();
