// The pictures of the variants in the texture page (SPEC-VIEWER 17.3): a
// variant's file is fetched and decoded once, then shown as a tile's
// preview and in the picture beside the original (R-VIEW-130). main.ts names
// the dataset and the entry; this holds the decoded files.

import { decodeDdsBytes, fetchTexture, type DecodedTexture } from '../core/ddsdecode';
import { make, messageOf } from '../core/dom';
import { ORIGINAL, shownOrder, textureRoutes, type TextureState, type TextureVariant } from '../../shared/textures';
import type { Side } from './imageview';

/** Where the variant files come from: the show request's game and dataset. Null: nothing is shown yet. */
export type PictureSource = { game: string; dataset: string } | null;

/** What a picture reads of an entry of the list. */
export interface Pictured {
  asset: string | null;
  plane: 'color' | 'alpha';
  /** The original's picture, in the entry's plane. */
  image: string;
}

/** Decoded variant files: `${asset}|${variant}|${sha256}` -> the decoded texture. */
const decoded = new Map<string, Promise<DecodedTexture>>();
/** The object URLs of their planes. */
const urls: string[] = [];

/** Another thing is shown: drop the decoded files and their URLs. */
export function clearPictures(): void {
  for (const url of urls.splice(0)) URL.revokeObjectURL(url);
  decoded.clear();
}

/** A variant's file, decoded once. */
function decodedOf(source: PictureSource, asset: string, variant: TextureVariant): Promise<DecodedTexture> {
  const key = `${asset}|${variant.id}|${variant.sha256}`;
  let texture = decoded.get(key);
  if (!texture && source) {
    const url = textureRoutes.file(source.game, source.dataset, asset, variant.id, variant.sha256);
    texture = fetchTexture(url).then(async (response) => decodeDdsBytes(await response.arrayBuffer(), variant.id, urls));
    decoded.set(key, texture);
  }
  return texture ?? Promise.reject(new Error('no texture service'));
}

/** The variants in `shown`, in the order of the tiles, decoded in the entry's plane: the picture's sides beside the original. */
export async function sides(source: PictureSource, item: Pictured, state: TextureState | undefined, shown: ReadonlySet<string>): Promise<Side[]> {
  if (!state || !source || item.asset === null) return [];
  const found: Side[] = [];
  for (const variant of shownOrder(state.variants)) {
    if (!shown.has(variant.id)) continue;
    const made = await decodedOf(source, state.asset, variant);
    const plane = made.planes.find((one) => one.plane === item.plane);
    if (plane) found.push({ label: `${variant.title} · ${variant.size}`, image: plane.image, width: made.size[0] });
  }
  return found;
}

/** The picture of a tile, in the entry's plane. A variant's shows once its file is decoded. */
export function preview(source: PictureSource, item: Pictured, state: TextureState | undefined, variant: string): HTMLElement {
  const box = make('span', { className: 'tex-preview' });
  const img = (src: string): HTMLImageElement => make('img', { src, alt: '', draggable: false });
  if (variant === ORIGINAL) {
    box.append(img(item.image));
    return box;
  }
  const found = state?.variants.find((one) => one.id === variant);
  if (!found || item.asset === null) {
    box.classList.add('none');
    return box;
  }
  box.classList.add('loading');
  decodedOf(source, item.asset, found).then(
    (made) => {
      const plane = made.planes.find((one) => one.plane === item.plane) ?? made.planes[0];
      box.classList.remove('loading');
      if (plane) box.append(img(plane.image));
    },
    (error: unknown) => {
      box.className = 'tex-preview failed';
      box.title = `no picture: ${messageOf(error)}`;
      box.textContent = '?';
    },
  );
  return box;
}
