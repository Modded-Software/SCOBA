// The test API (SPEC-VIEWER 11): what the features, the games and main.ts
// hand to testApi, put together as window.SCOBAEdit and window.scobaeditor. A
// member two of them give is an error: one would hide the other.

import type { TestApiBuilder } from './context';
import type { FormatModule, ProbeContext } from './plugin';

export interface TestApi {
  readonly builder: TestApiBuilder;
  /** window.SCOBAEdit. */
  app(): Readonly<Record<string, unknown>>;
  /** window.scobaeditor: `ready` is false until main.ts says the startup is done. */
  viewer(): Record<string, unknown>;
}

function add(into: Record<string, unknown>, members: Readonly<Record<string, unknown>>, name: string): void {
  const both = Object.keys(members).filter((key) => Object.hasOwn(into, key));
  if (both.length) throw new Error(`test api: ${name} has the member(s) ${both.join(', ')} twice`);
  // As descriptors: a getter (SCOBAEdit.pointer) stays a getter, read when the test reads it.
  Object.defineProperties(into, Object.getOwnPropertyDescriptors(members));
}

/**
 * scobaeditor.probe(format, name, ...args) (SPEC-VIEWER 6.3): calls one of a
 * format's probes. An unknown format or name is an error that names it.
 */
export function createProbe(formats: readonly FormatModule[], context: ProbeContext): (format: string, name: string, ...args: unknown[]) => unknown {
  const made = new Map<string, Readonly<Record<string, unknown>>>();
  for (const f of formats) if (f.probes) made.set(f.id, f.probes(context));
  return (format, name, ...args) => {
    const probes = made.get(format);
    if (!probes) throw new Error(`probe: no format "${format}" has probes`);
    const fn = Object.hasOwn(probes, name) ? probes[name] : undefined;
    if (typeof fn !== 'function') throw new Error(`probe: format "${format}" has no probe "${name}"`);
    return Reflect.apply(fn, undefined, args);
  };
}

export function createTestApi(): TestApi {
  const app: Record<string, unknown> = {};
  const viewer: Record<string, unknown> = { ready: false };
  const parts = new Map<string, () => unknown>();
  const builder: TestApiBuilder = {
    app: (members) => add(app, members, 'SCOBAEdit'),
    viewer: (members) => add(viewer, members, 'scobaeditor'),
    statePart(name, read) {
      if (parts.has(name)) throw new Error(`test api: two state parts "${name}"`);
      parts.set(name, read);
    },
    stateParts: () => Object.fromEntries([...parts].map(([name, read]) => [name, read()])),
  };
  return { builder, app: () => app, viewer: () => viewer };
}
