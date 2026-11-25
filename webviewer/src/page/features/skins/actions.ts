// The skin changes that ask first (SPEC-VIEWER 17.4, 17.6, 17.6.2): save New
// Skin under a name, discard it, rename or delete a saved skin, and save the
// picks of a window to a skin (R-VIEW-133). Every dialog says in plain words
// what will happen (R-VIEW-128); a delete or a discard is red (R-VIEW-136).
// A change goes through core/skins.ts, so each instance follows without a
// reload.

import { NEW_SKIN, ORIGINAL, ORIGINAL_SKIN, skinLabel, textureRoutes, type OwnerState } from '../../../shared/textures';
import type { FeatureContext } from '../../core/context';
import { make } from '../../core/dom';
import type { Item } from '../../core/types';
import { ConfirmDialog } from '../../ui/components/dialog';

/** One pick of a window: a variant for a texture. */
export interface TexturePick {
  asset: string;
  variant: string;
}

/** What a window asks to save (event "texture-save", the editor's Save to Skin…). */
export interface SaveAsk {
  game: string;
  dataset: string;
  owner: string;
  /** The instance the window is on; null: a record or a file. */
  item: number | null;
  picks: TexturePick[];
  /** The target chosen first; null: the instance's skin when it is New Skin or saved, else New Skin. */
  target: string | null;
}

export interface SkinActions {
  /** Ask a name and keep New Skin under it; the instances on New Skin show the saved skin. Null: cancelled. */
  save(item: Item): Promise<string | null>;
  /** Ask, then delete New Skin; its instances show Original. */
  discard(item: Item): Promise<boolean>;
  /** Ask a new name for a saved skin. Null: cancelled. */
  rename(item: Item, skin: string): Promise<string | null>;
  /** Ask, then delete a saved skin; its instances show Original. The service refuses the baked skin (R-HD-136). */
  remove(item: Item, skin: string): Promise<boolean>;
  /** Ask the target and show each change, then set the picks in it; the instance shows it (R-VIEW-133). Null: cancelled. */
  saveTo(ask: SaveAsk): Promise<string | null>;
  /** For the tests: the open dialog; null: none is open. */
  state(): { id: string; title: string; text: string; buttons: string[]; danger: boolean; targets: string[]; target: string; lines: string[] } | null;
}

/** One dialog that asks a question, with a name box when it asks a name. */
function asking(id: string, title: string, yes: string, named: boolean, danger = false) {
  const text = make('p', { className: 'skin-question' });
  const name = make('input', { className: 'skin-name-box', type: 'text', maxLength: 40, autocomplete: 'off', spellcheck: false, placeholder: 'name: letters, digits, - or _' });
  const dialog = new ConfirmDialog({ id, title, yesText: yes, content: named ? [text, name] : [text], danger });
  const ok = (): boolean => !named || /^[A-Za-z0-9_-]{1,40}$/.test(name.value.trim());
  name.addEventListener('input', () => (dialog.yes.disabled = !ok()));
  name.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && ok()) dialog.settle(true);
  });
  async function ask(question: string, value = ''): Promise<string | null> {
    text.textContent = question;
    name.value = value;
    dialog.yes.disabled = !ok();
    const answer = dialog.ask();
    if (named) name.focus();
    else dialog.no.focus();
    return (await answer) ? name.value.trim() : null;
  }
  return { dialog, ask };
}

/** The short name of an asset: its file. */
const fileOf = (asset: string): string => asset.split('\\').pop() ?? asset;

export function createSkinActions({ skins, scene, events }: Pick<FeatureContext, 'skins' | 'scene' | 'events'>): SkinActions {
  const saving = asking('skin-save-dialog', 'Save New Skin As', 'Save Skin', true);
  const discarding = asking('skin-discard-dialog', 'Discard New Skin', 'Discard New Skin', false, true);
  const renaming = asking('skin-rename-dialog', 'Rename Skin', 'Rename Skin', true);
  const deleting = asking('skin-delete-dialog', 'Delete Skin', 'Delete Skin', false, true);
  const all = [saving, discarding, renaming, deleting];

  // Save to Skin (17.6.2): a target, one line per pick, then the question.
  const target = make('select', { className: 'skin-target' });
  const changes = make('ul', { className: 'skin-changes' });
  const question = make('p', { className: 'skin-question' });
  const draft = new ConfirmDialog({ id: 'skin-draft-dialog', title: 'Save to Skin', yesText: 'Save to Skin', content: [make('label', { className: 'upscale-row' }, ['Target ', target]), changes, question] });

  /** The item's owner, read now. */
  async function ownerOf(item: Item): Promise<OwnerState> {
    const id = skins.ownerOf(item);
    const found = id ? await skins.readOwner(item.game, item.dataset, id) : null;
    if (!found) throw new Error('this instance has no texture owner');
    return found;
  }

  /**
   * A change that renames or removes skin `before`: every instance of the owner on it is set to `after` first,
   * so the change's own re-apply finds each on a skin that exists. A refused change sets them back.
   */
  async function moving(item: Item, before: string, after: string, body: Record<string, unknown> | null): Promise<void> {
    const owner = skins.ownerOf(item);
    const on = scene.items.filter((one) => one.game === item.game && one.dataset === item.dataset && skins.ownerOf(one) === owner && one.skin === before);
    for (const one of on) one.skin = after;
    try {
      if (body) await skins.change(item.game, item.dataset, textureRoutes.skin(item.game, item.dataset), body);
      else for (const one of on) await skins.apply(one);
    } catch (failure) {
      for (const one of on) one.skin = before;
      throw failure;
    }
    events.emit('scene-edited', { what: 'skin' });
  }

  async function save(item: Item): Promise<string | null> {
    const owner = await ownerOf(item);
    const name = await saving.ask(`Give New Skin of ${owner.title} (${owner.owner}) in ${item.dataset} a name. It is kept under that name; New Skin is then empty until the next change.`);
    if (name === null) return null;
    // An offered New Skin is stored by the rename itself (R-HD-137).
    await moving(item, NEW_SKIN, name, { owner: owner.owner, action: 'rename', name: NEW_SKIN, new: name });
    return name;
  }

  async function discard(item: Item): Promise<boolean> {
    const owner = await ownerOf(item);
    if ((await discarding.ask(`Discard New Skin of ${owner.title} (${owner.owner}) in ${item.dataset}? Its changes are lost. Instances on New Skin will show Original.`)) === null) return false;
    // An offered New Skin is not stored: there is nothing to delete.
    const stored = owner.skins.some((skin) => skin.name === NEW_SKIN && skin.stored);
    await moving(item, NEW_SKIN, ORIGINAL_SKIN, stored ? { owner: owner.owner, action: 'delete', name: NEW_SKIN } : null);
    return true;
  }

  async function rename(item: Item, skin: string): Promise<string | null> {
    const owner = await ownerOf(item);
    const name = await renaming.ask(`New name for skin "${skin}" of ${owner.title} (${owner.owner}). Instances on it keep showing it.`, skin);
    if (name === null || name === skin) return null;
    await moving(item, skin, name, { owner: owner.owner, action: 'rename', name: skin, new: name });
    return name;
  }

  async function remove(item: Item, skin: string): Promise<boolean> {
    const owner = await ownerOf(item);
    if ((await deleting.ask(`Delete skin "${skin}" of ${owner.title} (${owner.owner})? Instances on it will show Original.`)) === null) return false;
    await moving(item, skin, ORIGINAL_SKIN, { owner: owner.owner, action: 'delete', name: skin });
    return true;
  }

  /** What `skin` names for `asset` now; an unstored New Skin names what it offers (R-HD-137); a missing one names nothing. */
  const namedIn = (owner: OwnerState, skin: string, asset: string): string => owner.skins.find((one) => one.name === skin)?.textures[asset] ?? ORIGINAL;

  async function saveTo(ask: SaveAsk): Promise<string | null> {
    const found = await skins.readOwner(ask.game, ask.dataset, ask.owner);
    if (!found) throw new Error(`${ask.dataset} has no owner ${ask.owner} with textures`);
    const owner: OwnerState = found;
    const item = ask.item === null ? null : (scene.items.find((one) => one.id === ask.item) ?? null);
    const newStored = owner.skins.some((skin) => skin.name === NEW_SKIN && skin.stored);
    const saved = owner.skins.filter((skin) => skin.name !== NEW_SKIN).map((skin) => skin.name);
    target.replaceChildren(make('option', { value: NEW_SKIN, textContent: newStored ? 'New Skin' : 'New Skin (made now)' }), ...saved.map((name) => make('option', { value: name, textContent: name })));
    const wanted = ask.target ?? (item && item.skin !== ORIGINAL_SKIN ? item.skin : NEW_SKIN);
    target.value = [NEW_SKIN, ...saved].includes(wanted) ? wanted : NEW_SKIN;
    /** The picks that change the target. */
    const real = (): TexturePick[] => ask.picks.filter((pick) => namedIn(owner, target.value, pick.asset) !== pick.variant);
    function show(): void {
      const into = target.value;
      changes.replaceChildren(
        ...ask.picks.map((pick) => {
          const from = namedIn(owner, into, pick.asset);
          const line = make('li', { className: from === pick.variant ? 'same' : 'change', textContent: `${fileOf(pick.asset)}: ${from === pick.variant ? `${from}, no change` : `${from} → ${pick.variant}`}`, title: pick.asset });
          line.dataset['asset'] = pick.asset;
          return line;
        }),
      );
      question.textContent = [
        `${owner.title} (${owner.owner}) in ${ask.dataset}: ${real().length} of ${ask.picks.length} textures change in ${skinLabel(into)}.`,
        'Bakes, Original and the other skins do not change.',
        ...(into === NEW_SKIN && !newStored ? [`New Skin will be made from what ${owner.title} shows now.`] : []),
        item ? `This instance will show ${skinLabel(into)}.` : 'No instance changes its skin.',
      ].join(' ');
      draft.yes.disabled = real().length === 0;
    }
    target.onchange = show;
    show();
    const answer = draft.ask();
    draft.no.focus();
    if (!(await answer)) return null;
    const into = target.value;
    for (const pick of real()) await skins.change(ask.game, ask.dataset, textureRoutes.skin(ask.game, ask.dataset), { owner: ask.owner, action: 'set', name: into, asset: pick.asset, variant: pick.variant });
    if (item && item.skin !== into) await skins.set(item, into);
    return into;
  }

  function state(): ReturnType<SkinActions['state']> {
    const open = [...all.map((one) => one.dialog), draft].find((one) => one.dialog.isOpen);
    if (!open) return null;
    const node = open.dialog.node;
    const isDraft = open === draft;
    return {
      id: node.id,
      title: node.querySelector('.dialog-head span')?.textContent ?? '',
      text: node.querySelector('p.skin-question')?.textContent ?? '',
      buttons: [...node.querySelectorAll('.answers button')].map((b) => b.textContent ?? ''),
      danger: open.yes.classList.contains('danger'),
      targets: isDraft ? [...target.options].map((option) => option.value) : [],
      target: isDraft ? target.value : '',
      lines: isDraft ? [...changes.children].map((line) => line.textContent ?? '') : [],
    };
  }

  return { save, discard, rename, remove, saveTo, state };
}

