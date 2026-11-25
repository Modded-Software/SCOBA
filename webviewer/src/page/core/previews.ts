// Small pictures of texture files (the skin editor, the ground picker), decoded in the page
// from the file itself (core/ddsdecode.ts), one per URL, until cleared.

import { decodeDdsBytes, fetchTexture } from './ddsdecode';
import { make, messageOf } from './dom';

export interface Previews {
  /** An image of the file at `url`; on a failure, a box that says why. */
  node(url: string, name: string): HTMLElement;
  /** Forget every picture and free its object URL. */
  clear(): void;
}

export function createPreviews(): Previews {
  let urls: string[] = [];
  let made = new Map<string, Promise<string>>();

  function image(url: string, name: string): Promise<string> {
    let found = made.get(url);
    if (!found) {
      found = fetchTexture(url).then(async (response) => {
        const decoded = await decodeDdsBytes(await response.arrayBuffer(), name, urls);
        const colour = decoded.planes.find((plane) => plane.plane === 'color') ?? decoded.planes[0];
        if (!colour) throw new Error('no plane');
        return colour.image;
      });
      made.set(url, found);
    }
    return found;
  }

  function node(url: string, name: string): HTMLElement {
    const box = make('span', { className: 'tex-preview loading' });
    image(url, name).then(
      (src) => {
        box.className = 'tex-preview';
        box.replaceChildren(make('img', { src, alt: '', draggable: false }));
      },
      (error: unknown) => {
        box.className = 'tex-preview failed';
        box.title = `no picture: ${messageOf(error)}`;
        box.textContent = '?';
      },
    );
    return box;
  }

  function clear(): void {
    for (const url of urls) URL.revokeObjectURL(url);
    urls = [];
    made = new Map();
  }

  return { node, clear };
}
