// The SC2 part of the test API: add a model file, a record, a unit or a
// doodad. A doodad's variant is its "variation", as the map editor names
// it; `hd` is the SC2 item option (the HD texture set).

import type { SceneService } from '../../../page/core/context';
import type { AddOptions } from '../../../page/core/types';
import { DOODADS, UNITS } from './records';

export interface Sc2AddOptions extends Omit<AddOptions, 'variant' | 'options'> {
  /** Which of a doodad's model variations. */
  variation?: number | null;
  /** The HD texture set (default on). */
  hd?: boolean;
}

function coreOptions(options: Sc2AddOptions): AddOptions {
  const { variation, hd, ...rest } = options;
  const out: AddOptions = hd === undefined ? rest : { ...rest, options: { hd } };
  return variation === undefined ? out : { ...out, variant: variation };
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
