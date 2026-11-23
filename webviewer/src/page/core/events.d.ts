// The types of the `events` package, for the page project. The library's
// ModelViewer extends its EventEmitter. In the browser bundle that is the
// npm `events` package (package.json), which ships no types; the Node
// types that describe it elsewhere are not part of the page project
// (tsconfig.page.json: no Node globals). This is the part the page uses.

declare module 'events' {
  export class EventEmitter {
    on(event: string | symbol, listener: (...args: never[]) => void): this;
    once(event: string | symbol, listener: (...args: never[]) => void): this;
    off(event: string | symbol, listener: (...args: never[]) => void): this;
    removeListener(event: string | symbol, listener: (...args: never[]) => void): this;
    emit(event: string | symbol, ...args: unknown[]): boolean;
  }
}
