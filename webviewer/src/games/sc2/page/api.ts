// The SC2 part of the test API: add a model file, a record, a unit or a
// doodad. A doodad's variant is its "variation", as the map editor names
// it. The skin is the core option `skin`.

import type { SceneService } from '../../../page/core/context';
import type { AddOptions } from '../../../page/core/types';
import { DOODADS, UNITS } from './records';

export interface Sc2AddOptions extends Omit<AddOptions, 'variant' | 'options'> {
  /** Which of a doodad's model variations. */
  variation?: number | null;
}

function coreOptions(options: Sc2AddOptions): AddOptions {
  const { variation, ...rest } = options;
  return variation === undefined ? rest : { ...rest, variant: variation };
}

export function sc2SceneApi(scene: Pick<SceneService, 'add' | 'addRecord'>): {
  add(path: string, options?: Sc2AddOptions): Promise<number>;
  addRecord(category: string, id: string, options?: Sc2AddOptions): Promise<number | null>;
  addUnit(id: string, options?: Sc2AddOptions): Promise<number | null>;
  addDoodad(id: string, options?: Sc2AddOptions): Promise<number | null>;
} {
  return {
    add: (path, options = {}) => scene.add(path, coreOptions(options)),
    addRecord: (category, id, options = {}) => scene.addRecord(category, id, coreOptions(options)),
    addUnit: (id, options = {}) => scene.addRecord(UNITS, id, coreOptions(options)),
    addDoodad: (id, options = {}) => scene.addRecord(DOODADS, id, coreOptions(options)),
  };
}
