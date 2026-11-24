// What features/scenes shows the tests (SPEC-VIEWER section 10.2), as
// types; core/types.ts re-exports them.

/** A stored scene that failed its check: listed, and can only be deleted. */
export interface RefusedScene {
  id: string;
  /** Its name, when it has a string one. */
  name: string | null;
  reason: string;
}

export interface ScenesState {
  open: { id: string; name: string } | null;
  /** The good scenes, by name. */
  list: { id: string; name: string; items: number; modified: string }[];
  refused: RefusedScene[];
  /** True while a scene's items are being added. */
  loading: boolean;
  /** The page address at startup: 'empty', or 'refused' (it held a "#" part; it was cleared). */
  address: string;
}
