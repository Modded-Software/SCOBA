// Ghost in the texture window (core/texturewindow.ts), without a texture
// service: every texture file a model's materials name, decoded, each
// with what draws with it (material, shader, drawn or why not, groups). A
// material without a texture file, and a texture that does not load, are
// listed as not shown, with why.

import type { GameContext } from '../../../page/core/context';
import { decodeDds } from '../../../page/core/ddsdecode';
import { messageOf } from '../../../page/core/dom';
import type { ShownTexture } from '../../../page/core/texturewindow';
import type { Item } from '../../../page/core/types';
import { nodLooks, type NodLook } from '../../../formats/nod/looks';
import { GHOST } from './game';

export interface GhostTextures {
  openTexturesFor(category: string, id: string): Promise<void>;
  openTexturesOf(item: Item): Promise<void>;
}

/** How a material is drawn, in words. */
function drawnAs(look: NodLook): string {
  if (look.kind !== null) return `drawn ${look.kind}${look.twoSided ? ', both sides' : ''}`;
  return look.why !== null ? `not drawn: ${look.why}` : 'not drawn: hidden by its shader';
}

/** One fact per material: its name, then shader, how it is drawn, its groups and triangles. */
function materialFacts(looks: readonly NodLook[]): [string, string][] {
  const byMaterial = new Map<string, NodLook[]>();
  for (const look of looks) byMaterial.set(look.material, [...(byMaterial.get(look.material) ?? []), look]);
  return [...byMaterial].map(([material, used]): [string, string] => {
    const [first] = used;
    const triangles = used.reduce((sum, l) => sum + l.triangles, 0);
    const shader = first && first.shader ? `shader ${first.shader}` : 'no shader';
    return [`material ${material}`, `${shader} · ${first ? drawnAs(first) : ''} · groups ${used.map((l) => l.group).join(', ')} · ${triangles} triangles`];
  });
}

export function installGhostTextures(context: GameContext): GhostTextures {
  const { api, render, textureWindow } = context;

  /** Every texture file of the model, decoded, with its materials' facts; the rest named in `failed`. */
  async function read(file: string, dataset: string, urls: string[]): Promise<{ textures: ShownTexture[]; failed: string[] }> {
    const model = await render.loadModel(api.modelUrl(file, dataset, GHOST), api.pathSolver(dataset, GHOST));
    if (!model) throw new Error(`cannot load ${file}`);
    const looks = nodLooks(model);
    const byTexture = new Map<string, NodLook[]>();
    const failed: string[] = [];
    for (const look of looks) {
      if (look.texture === null) {
        const named = failed.some((f) => f.startsWith(`${look.material}: `));
        if (!named) failed.push(`${look.material}: no texture file (${drawnAs(look)})`);
        continue;
      }
      byTexture.set(look.texture, [...(byTexture.get(look.texture) ?? []), look]);
    }
    const textures: ShownTexture[] = [];
    for (const [texture, used] of [...byTexture].sort(([a], [b]) => a.localeCompare(b))) {
      await decodeDds(String(api.pathSolver(dataset, GHOST)(texture)), texture, urls).then(
        (decoded) => textures.push({ ...decoded, asset: null, facts: materialFacts(used) }),
        (error: unknown) => failed.push(`${texture} (${messageOf(error)})`),
      );
    }
    return { textures, failed };
  }

  function openTextures(user: string, name: string, file: string, dataset: string): Promise<void> {
    // Ghost has no texture service (R-VIEW-100): the window shows the originals only.
    return textureWindow.open({ user, name, file, dataset, game: GHOST, service: false, read: (urls) => read(file, dataset, urls) });
  }

  async function openTexturesFor(category: string, id: string): Promise<void> {
    const dataset = api.requireDataset(api.currentDataset(GHOST), GHOST);
    const record = await api.record(category, id, dataset, GHOST);
    if (!record.file) throw new Error(`${record.name} has no model file`);
    return openTextures(id, record.name, record.file, dataset);
  }

  /** A bare model file goes by its file name. */
  function openTexturesOf(item: Item): Promise<void> {
    const fileName = item.path.split('/').pop() ?? item.path;
    const record = item.source ? item.source.record : null;
    return openTextures(record ? record.id : fileName, record ? record.name : fileName, item.path, item.dataset);
  }

  return { openTexturesFor, openTexturesOf };
}
