// The edit sessions as the texture page shows them (SPEC-PHOTOCRAFT 9.1,
// 9.5): the Edit Texture button of the tiles with the session's state, the
// EDIT badge of a list row, and the Manage Edits… button. The page reads no
// session itself: the window hands them over each time the main page has
// read them (hdtex.edits), and opens a session through the window too.

import type { EditSession, EditStateName } from '../../shared/edits';
import type { TextureState } from '../../shared/textures';
import type { TileEdits } from '../core/tiles';

/** What the window offers of the edit sessions; absent in a show request: the page has no edit control. */
export interface EditTools {
  /** Open the session of a texture's variant in the editor window. */
  open(asset: string, variant: string): void;
  /** Open the list of the dataset's sessions. */
  manage(): void;
}

let sessions: EditSession[] = [];
let tools: EditTools | null = null;

const shownKey = (list: readonly EditSession[]): string => JSON.stringify(list.map((one) => [one.session, one.asset, one.variant, one.state]));

/** The button of the bar: there while the page has edit tools and the dataset has a session. */
function manageButton(): HTMLButtonElement {
  const found = document.getElementById('manage-edits');
  if (!(found instanceof HTMLButtonElement)) throw new Error('the texture viewer page has no #manage-edits');
  return found;
}

/** A new show request: its tools, and no session until the window hands them over. */
export function resetEdits(next: EditTools | null): void {
  tools = next;
  sessions = [];
  const button = manageButton();
  button.hidden = true;
  button.onclick = next ? () => next.manage() : null;
}

/** Take the sessions the main page read. True: what the page shows of them changed. */
function takeEdits(next: readonly EditSession[]): boolean {
  const changed = shownKey(next) !== shownKey(sessions);
  sessions = [...next];
  manageButton().hidden = tools === null || sessions.length === 0;
  return changed;
}

/** The hand-over of the window (hdtex.edits): take the sessions, and draw again when what the page shows of them changed. */
export const editsTaker =
  (redraw: () => void) =>
  (next: readonly EditSession[]): void => {
    if (takeEdits(next)) redraw();
  };

/** The state of the session of a texture's variant; null: it has none. */
const sessionOf = (asset: string, variant: string): EditStateName | null => sessions.find((one) => one.asset === asset && one.variant === variant)?.state ?? null;

/** A session of the texture is edited: its row gets the badge EDIT (R-PC-37). */
export const hasEdit = (asset: string): boolean => sessions.some((one) => one.asset === asset && one.state === 'edited');

/** The Edit Texture buttons of a texture's tiles; undefined: the page has no edit control. */
export function tileEdits(state: TextureState): TileEdits | undefined {
  const mine = tools;
  if (!mine) return undefined;
  // A texture has planes once the pipeline has judged it; one that cannot be upscaled has no role, so none (R-PC-29).
  const disabled = state.judged ? state.reason : 'not read yet';
  return { disabled, session: (variant) => sessionOf(state.asset, variant), open: (variant) => mine.open(state.asset, variant) };
}

/** For the tests (hdtex.state): the sessions the page holds, and whether Manage Edits… shows. */
export const editsState = (): { sessions: { session: string; asset: string; variant: string; state: EditStateName }[]; manage: boolean; tools: boolean } => ({
  sessions: sessions.map(({ session, asset, variant, state }) => ({ session, asset, variant, state })),
  manage: !manageButton().hidden,
  tools: tools !== null,
});
