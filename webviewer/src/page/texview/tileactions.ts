// What a tile of the texture page does besides a pick (SPEC-VIEWER 17.6.1):
// Ask Again and Open Log of a failed request (R-VIEW-146), and the trash of
// a variant (R-VIEW-147). Ask Again calls the request route here. The trash
// asks the main page first. main.ts hands over the page they act on.

import { messageOf } from '../core/dom';
import type { PageOwner } from '../core/texturewindow';
import type { TileRemoval, TileRequests } from '../core/tiles';
import { askOf, recipeOf, skinLabel, textureRoutes, type TextureState } from '../../shared/textures';
import { tileEdits } from './edits';
import { call, take } from './states';

/** What the actions read and call of the page, for one show request. */
export interface TilePage {
  game: string;
  dataset: string;
  /** That show request is still the one shown. */
  current(): boolean;
  /** Draw the list and the tiles again. */
  render(): void;
  say(text: string): void;
  /** Poll the states while a request runs. */
  schedule(): void;
  /** Read the states again, then poll while a request runs. */
  reread(): void;
}

/** The Ask Again calls that are out, as `asset|recipe`. */
const retrying = new Set<string>();

/** Another thing is shown: no call of it is out. */
export const clearRetries = (): void => retrying.clear();

/** Ask Again and Open Log of a texture's failed requests: the same variant, no dialog. */
export function requestTools(page: TilePage, state: TextureState): TileRequests {
  const key = (recipe: string): string => `${state.asset}|${recipe}`;
  return {
    asking: (recipe) => retrying.has(key(recipe)),
    log: (recipe) => textureRoutes.log(page.game, page.dataset, state.asset, recipe),
    retry: (recipe, variant) => {
      const ask = askOf(state.asset, variant);
      if (!ask || retrying.has(key(recipe))) return;
      retrying.add(key(recipe));
      page.render();
      call(textureRoutes.request(page.game, page.dataset), ask)
        .then((body) => {
          if (!page.current()) return;
          page.say('');
          take(body);
        })
        .catch((error: unknown) => page.say(`${variant} was not asked for again: ${messageOf(error)}`))
        .finally(() => {
          retrying.delete(key(recipe));
          if (!page.current()) return;
          page.render();
          page.schedule();
        });
    },
  };
}

/** What the trash reads and calls of the page, for the texture whose tiles are shown. */
export interface Removal {
  /** The main page asks, then removes. False: cancelled. A refusal rejects. */
  remove(asset: string, variant: string): Promise<boolean>;
  /** The owner as the window read it last; null: none. */
  owner: PageOwner | null;
  /** The variant picked for the texture now. */
  picked: string;
  /** A variant was removed: it leaves the picture. */
  removed(variant: string): void;
}

/**
 * Why a variant cannot be removed now (R-VIEW-147): it is picked, the game shows it, a bake names it,
 * an edit session is open on it, another variant is made from it, or its recipe is being made. Empty: it can.
 * A skin of this dataset that names it does not keep it. The pipeline refuses what the page cannot see:
 * the skins and bakes of other datasets (R-HD-146).
 */
function removalRefusal({ owner, picked }: Removal, state: TextureState, variant: string): string {
  const asset = state.asset;
  if (variant === picked) return 'it is picked now; pick another tile first';
  if (owner) {
    if (owner.shows[asset] === variant) return 'the game shows it: it is baked';
    if (owner.bake?.textures[asset] === variant) return `it is baked in skin ${skinLabel(owner.bake.skin)}`;
    // A skin that names it does not keep it: the skin names the original after (operator 2026-11-26).
  }
  if (state.bake === variant) return 'it is baked';
  if (tileEdits(state)?.session(variant)) return 'an edit session is open on it; discard it first';
  const built = state.variants.find((one) => one.input === variant)?.id ?? Object.keys(state.requests).find((recipe) => recipe.startsWith(`${variant}+`));
  if (built) return `${built} is made from it; delete that first`;
  const open = state.requests[recipeOf(variant)];
  if (open && open.state !== 'failed') return `a request of ${recipeOf(variant)} is ${open.state}`;
  return '';
}

/** The trash of each variant tile of a texture; the main page asks first. */
export function removalTools(page: TilePage, removal: Removal, state: TextureState): TileRemoval {
  return {
    refusal: (variant) => removalRefusal(removal, state, variant),
    remove: (variant) => {
      removal.remove(state.asset, variant).then(
        (removed) => {
          if (!removed || !page.current()) return;
          removal.removed(variant);
          page.say('');
          page.reread();
        },
        (error: unknown) => {
          if (page.current()) page.say(messageOf(error));
        },
      );
    },
  };
}
