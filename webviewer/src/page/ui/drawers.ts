// The two panels on the left, the gallery (#gallery) and the instances
// (#instances), are drawers: a handle at the bottom of each one's right
// edge (R-VIEW-24) slides it out
// to the left and back. A closed panel takes no keys (inert) and leaves the
// view free (core/host.ts visibleRect). Which are open is a setting (core/settings.ts).

import type { Store, UiService } from '../core/context';
import { byId } from '../core/dom';
import { settings, type DrawersSetting } from '../core/settings';

type DrawerId = 'gallery' | 'instances';

const DRAWERS: readonly { id: DrawerId; tab: string; name: string }[] = [
  { id: 'gallery', tab: 'gallery-handle', name: 'gallery' },
  { id: 'instances', tab: 'instances-handle', name: 'instances' },
];

const isDrawer = (id: string): id is DrawerId => id === 'gallery' || id === 'instances';

export type DrawersApi = Pick<UiService, 'setDrawer' | 'drawerState'>;

export function installDrawers(store: Store, placeStatus: () => void): DrawersApi {
  // The stored drawers, else the setting's declared default: both open.
  const open: DrawersSetting = store.read(settings.drawers);

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
    // The game tabs slide with the gallery and stay at the window edge (ui/gametabs.ts).
    byId('game-tabs').classList.toggle('closed', !open.gallery);
  }

  /** Open or close one drawer ('gallery' or 'instances'); no `to`: the other way. */
  function setDrawer(id: string, to?: boolean): void {
    if (!isDrawer(id)) throw new Error(`drawer: no drawer "${id}"`);
    open[id] = to === undefined ? !open[id] : Boolean(to);
    store.write(settings.drawers, { ...open });
    apply();
    // The status toast stays centred on the part of the view that shows.
    placeStatus();
  }

  for (const { id, tab } of DRAWERS) byId(tab).addEventListener('click', () => setDrawer(id));
  // The toast moves when the slide ends: the panel's box is final then.
  for (const { id } of DRAWERS) byId(id).addEventListener('transitionend', () => placeStatus());
  apply();

  return {
    setDrawer,
    /** For the tests: which drawers are open. */
    drawerState: () => ({ ...open }),
  };
}
