// The game tabs (SPEC-VIEWER 10.1): one button[data-game] per game the
// server lists, stacked, the text turned vertical, on the gallery's right
// edge from its top (R-VIEW-20). A tab makes that game the gallery's: its
// datasets, categories and lists; the scene, the camera and the selection
// stay (R-VIEW-21). With the gallery closed the tabs stay at the window
// edge, and a click opens the gallery on that game (R-VIEW-23). A game
// that cannot open (not available, or no page module) has its tab
// disabled, with the reason as its title (R-VIEW-27).

import type { GameRegistry, StatusService } from '../core/context';
import type { EventBus, ViewerEvents } from '../core/bus';
import { byId, make } from '../core/dom';
import type { DrawersApi } from './drawers';

export interface GameTabsDeps {
  readonly games: GameRegistry;
  readonly drawers: DrawersApi;
  readonly status: StatusService;
  readonly events: EventBus<ViewerEvents>;
}

export function installGameTabs({ games, drawers, status, events }: GameTabsDeps): void {
  const bar = byId('game-tabs');

  function mark(): void {
    const chosen = games.game();
    for (const node of bar.querySelectorAll('button[data-game]')) {
      if (!(node instanceof HTMLButtonElement)) continue;
      const on = node.dataset.game === chosen;
      node.classList.toggle('on', on);
      node.setAttribute('aria-pressed', String(on));
    }
  }

  async function choose(id: string): Promise<void> {
    if (!drawers.drawerState().gallery) drawers.setDrawer('gallery', true);
    await games.setGame(id);
  }

  /** Build the tabs from the games read. */
  function showGameTabs(): void {
    bar.replaceChildren(
      ...games.gamesInfo().map((game) => {
        const why = games.gameRefusal(game.id);
        const button = make('button', { textContent: game.tab, title: why === null ? game.label : `${game.label}: ${why}`, disabled: why !== null });
        button.dataset.game = game.id;
        button.addEventListener('click', () => choose(game.id).catch(status.reportFailure));
        return button;
      }),
    );
    mark();
  }

  events.on('startup', showGameTabs);
  // The mark follows every game change (scobaeditor.games.choose too).
  events.on('game-changed', () => {
    if (bar.childElementCount) mark();
  });
}
