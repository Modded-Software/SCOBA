// Small inline icons of the page's lists and buttons, 12 px, in the text colour.

const svg = (path: string): string => `<svg viewBox="0 0 16 16" width="12" height="12" aria-hidden="true"><path fill="currentColor" d="${path}"/></svg>`;

/** Edit or rename. */
export const PENCIL = svg('M11 1l4 4-9 9H2v-4zM10 4l2 2');
/** Delete; its button is red (R-VIEW-136). */
export const TRASH = svg('M6 1h4l1 1h3v2H2V2h3zM3 5h10l-1 10H4zm3 2v6h1V7zm3 0v6h1V7z');
/** A skin: a shirt (R-VIEW-137). */
export const SKIN = svg('M5 1L1 4l2 3 2-1v9h6V6l2 1 2-3-4-3c0 1-1 2-3 2S5 2 5 1z');
