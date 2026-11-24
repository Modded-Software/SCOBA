// The page's static files: the HTML, the style sheets, the shaders and the
// page bundle. A fixed table: nothing else under public/ is served.

import { join } from 'node:path';
import { sendFile, type Route } from './http';

const TEXT = 'text/plain; charset=utf-8';

const FILES = new Map<string, readonly [string, string]>([
  ['/', ['public/index.html', 'text/html; charset=utf-8']],
  ...['outline.vert', 'outline-blur.frag', 'outline-compose.frag', 'ground.vert', 'ground.frag', 'nod.vert', 'nod.frag'].map((name): [string, readonly [string, string]] => [`/shaders/${name}`, [`public/shaders/${name}`, TEXT]]),
  // The texture viewer page as a template, with no entries of its own: a
  // game hands it the textures it shows (page/core/texturewindow.ts).
  ['/texture-viewer.html', ['../scripts/hdtex/compare.html', 'text/html; charset=utf-8']],
  ['/theme.css', ['public/theme.css', 'text/css; charset=utf-8']],
  ['/style.css', ['public/style.css', 'text/css; charset=utf-8']],
  // Built by src/tools/build.ts: the page bundle (src/page) with mdx-m3-viewer.
  ['/vendor/renderer.js', ['public/vendor/renderer.js', 'text/javascript; charset=utf-8']],
  ['/vendor/renderer.js.map', ['public/vendor/renderer.js.map', 'application/json; charset=utf-8']],
]);

/** The route of the static files below the viewer folder `root`. GET only; never cached. */
export function staticFiles(root: string): Route {
  return async ({ method, route, res }) => {
    const entry = FILES.get(route);
    if (!entry || method !== 'GET') return false;
    sendFile(res, join(root, entry[0]), entry[1], 'no-store');
    return true;
  };
}
