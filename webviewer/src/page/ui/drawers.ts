// The two panels on the left, the gallery (#panel) and the instances
// (#instances), are drawers: a tab at each one's right edge slides it out
// to the left and back. A closed panel takes no keys (inert) and leaves the
// view free (app.visibleRect). Which are open is a setting (core/settings.ts).

import { app, type DrawersApi } from '../core/app';
import { byId } from '../core/dom';
import { readSetting, settings, writeSetting, type DrawersSetting } from '../core/settings';

type DrawerId = 'panel' | 'instances';

const DRAWERS: readonly { id: DrawerId; tab: string; name: string }[] = [
  { id: 'panel', tab: 'panel-tab', name: 'gallery' },
  { id: 'instances', tab: 'instances-tab', name: 'instances' },
];

const isDrawer = (id: string): id is DrawerId => id === 'panel' || id === 'instances';

export function installDrawers(): DrawersApi {
  // Both open when none are stored, or the stored value is refused.
  const open: DrawersSetting = readSetting(settings.drawers).value ?? { panel: true, instances: true };

  function apply(): void {
    for (const { id, tab, name } of DRAWERS) {
      const node = byId(id);
      const button = byId(tab);
      node.classList.toggle('closed', !open[id]);
      node.inert = !open[id];
      button.classList.toggle('closed', !open[id]);
      button.textContent = open[id] ? '\u2039' : '\u203A';
      button.title = `${open[id] ? 'hide' : 'show'} the ${name}`;
      button.setAttribute('aria-expanded', String(open[id]));
    }
  }

  /** Open or close one drawer ('panel' or 'instances'); no `to`: the other way. */
  function setDrawer(id: string, to?: boolean): void {
    if (!isDrawer(id)) throw new Error(`drawer: no drawer "${id}"`);
    open[id] = to === undefined ? !open[id] : Boolean(to);
    writeSetting(settings.drawers, { ...open });
    apply();
    // The status toast stays centred on the part of the view that shows.
    app().placeStatus();
  }

  for (const { id, tab } of DRAWERS) byId(tab).addEventListener('click', () => setDrawer(id));
  // The toast moves when the slide ends: the panel's box is final then.
  for (const { id } of DRAWERS) byId(id).addEventListener('transitionend', () => app().placeStatus());
  apply();

  return {
    setDrawer,
    /** For the tests: which drawers are open. */
    drawerState: () => ({ ...open }),
  };
}
