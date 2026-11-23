// The part features/scenes adds to the page object (SPEC-VIEWER section
// 10.2), as types. Here in core, because a feature may not import another
// feature (section 3); app.ts re-exports them.

import type { SceneDocument } from '../../shared/scene';

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

export interface ScenesApi {
  setupScenes(): Promise<void>;
  /** Write the open scene: after every change to the instances. */
  saveScene(): void;
  /** Wait for the scene opens and writes asked so far. */
  flushScenes(): Promise<void>;
  /** The open scene as it would be stored now, or null. */
  sceneDocument(): SceneDocument | null;
  scenesState(): ScenesState;
  newScene(name: string): Promise<string>;
  openScene(id: string): Promise<void>;
  renameScene(id: string, name: string): Promise<void>;
  deleteScene(id: string): Promise<void>;
  /** The open scene as the text of a file. */
  exportScene(): string;
  /** Check a file's text, store it as a new scene and open it. Returns its id. */
  importScene(text: string): Promise<string>;
}
