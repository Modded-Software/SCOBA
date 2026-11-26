// The skin changes (SPEC-VIEWER 17.4, 17.6.2): make the next New Skin N
// (R-HD-137), rename a skin (R-VIEW-156), delete a skin, delete a variant
// (R-VIEW-147), and save the picks of the texture window to a skin
// (R-VIEW-133). Every dialog says in plain words what will happen
// (R-VIEW-128); a delete is red (R-VIEW-136). A change goes through
// core/skins.ts, so each instance follows without a reload.

import { firstSaveInto, hasSkin, namedInto, ORIGINAL_SKIN, skinLabel, skinNameRefusal, textureRoutes, type OwnerState, type SaveInto, type SkinBody, type TextureRemoveAsk } from '../../../shared/textures';
import type { FeatureContext } from '../../core/context';
import { make } from '../../core/dom';
import type { Item } from '../../core/types';
import { ConfirmDialog } from '../../ui/components/dialog';
import { stepSelect } from '../../ui/components/stepper';

/** One pick of a window: a variant for a texture. */
export interface TexturePick {
  asset: string;
  variant: string;
}

/** What the texture window asks to save (event "texture-save"). */
export interface SaveAsk {
  game: string;
  dataset: string;
  owner: string;
  /** The instance the window is on; null: a record or a file. */
  item: number | null;
  picks: TexturePick[];
}

/** Why a name cannot be the new name of skin `from` among `names`; empty: it can. */
export function renameRefusal(name: string, from: string, names: readonly string[]): string {
  if (name === from) return 'that is its name now';
  const bad = skinNameRefusal(name);
  if (bad) return bad;
  const taken = names.find((one) => one !== from && one.toLowerCase() === name.toLowerCase());
  return taken === undefined ? '' : `there is a skin "${taken}" already`;
}

export interface SkinActions {
  /** Make the next New Skin N naming what the item's skin names (R-HD-137); its name. */
  create(item: Item): Promise<string>;
  /** Ask a new name, then rename the item's skin; every instance on it and the bake follow (R-VIEW-156). The new name, or null: cancelled. */
  rename(item: Item): Promise<string | null>;
  /** Ask, then delete a skin; its instances show Original. The service refuses the baked skin (R-HD-136). */
  remove(item: Item, skin: string): Promise<boolean>;
  /** Ask the target and show each change, then set the picks in it; the instance shows it (R-VIEW-133). Null: cancelled. */
  saveTo(ask: SaveAsk): Promise<string | null>;
  /** Ask, then remove one variant of a texture (R-VIEW-147). False: cancelled. A refusal throws with the pipeline's reason. */
  removeVariant(game: string, dataset: string, asset: string, variant: string): Promise<boolean>;
  /** For the tests: the open dialog; null: none is open. */
  state(): { id: string; title: string; text: string; buttons: string[]; danger: boolean; into: SaveInto | null; next: string; skins: string[]; existingDisabled: boolean; lines: string[]; name: string; yesDisabled: boolean } | null;
}

/** One red dialog that asks a yes or no question. */
function asking(id: string, title: string, yes: string) {
  const text = make('p', { className: 'skin-question' });
  const dialog = new ConfirmDialog({ id, title, yesText: yes, content: [text], danger: true });
  async function ask(question: string): Promise<boolean> {
    text.textContent = question;
    const answer = dialog.ask();
    dialog.no.focus();
    return answer;
  }
  return { dialog, ask };
}

/** The short name of an asset: its file. */
const fileOf = (asset: string): string => asset.split('\\').pop() ?? asset;

export function createSkinActions({ skins, scene, events }: Pick<FeatureContext, 'skins' | 'scene' | 'events'>): SkinActions {
  const deleting = asking('skin-delete-dialog', 'Delete Skin', 'Delete Skin');
  const removing = asking('variant-delete-dialog', 'Delete Variant', 'Delete Variant');

  // Rename Skin (R-VIEW-156): a name box, checked as it is typed.
  const nameBox = make('input', { id: 'skin-rename-name', type: 'text', autocomplete: 'off', spellcheck: false, maxLength: 40 });
  const renameWhy = make('p', { className: 'skin-rename-why' });
  const renameQuestion = make('p', { className: 'skin-question' });
  const renaming = new ConfirmDialog({ id: 'skin-rename-dialog', title: 'Rename Skin', yesText: 'Rename Skin', content: [renameQuestion, nameBox, renameWhy] });
  const all = [deleting, removing, { dialog: renaming }];

  // Save to Skin (17.6.2): a new skin, or an existing one picked from the owner's skins; one line per pick; the question.
  const intoNew = make('input', { id: 'skin-save-new', type: 'radio', name: 'skin-save-into' });
  const intoExisting = make('input', { id: 'skin-save-existing', type: 'radio', name: 'skin-save-into' });
  const newLabel = make('span', { className: 'skin-save-next' });
  const existing = stepSelect(make('select', { id: 'skin-save-skin', className: 'skin-target' }));
  const changes = make('ul', { className: 'skin-changes' });
  const question = make('p', { className: 'skin-question' });
  const draft = new ConfirmDialog({
    id: 'skin-draft-dialog',
    title: 'Save to Skin',
    yesText: 'Save to Skin',
    content: [make('label', { className: 'upscale-row' }, [intoNew, newLabel]), make('label', { className: 'upscale-row' }, [intoExisting, 'Existing skin ', existing]), changes, question],
  });
  /** The target the dialog shows now. */
  const intoNow = (): SaveInto => (intoExisting.checked ? { kind: 'existing', skin: existing.value } : { kind: 'new' });

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

  /** Make the next New Skin N of an owner from skin `from`; its name. */
  async function made(game: string, dataset: string, owner: string, from: string): Promise<string> {
    const body = await skins.change<SkinBody>(game, dataset, textureRoutes.skin(game, dataset), { owner, action: 'copy', name: null, from });
    if (body.made === null) throw new Error(`${owner}: the copy named no skin`);
    return body.made;
  }

  /** Refuse an item on a skin its owner does not have: nothing is made from it or renamed. */
  function needSkin(owner: OwnerState, item: Item): void {
    if (!hasSkin(owner, item.skin)) throw new Error(`${owner.owner} has no skin "${item.skin}"; choose another skin first`);
  }

  async function create(item: Item): Promise<string> {
    const owner = await ownerOf(item);
    needSkin(owner, item);
    return made(item.game, item.dataset, owner.owner, item.skin);
  }

  async function rename(item: Item): Promise<string | null> {
    const owner = await ownerOf(item);
    needSkin(owner, item);
    const from = item.skin;
    if (from === ORIGINAL_SKIN) throw new Error('Original names nothing and has no name to change');
    const names = owner.skins.map((skin) => skin.name);
    const baked = owner.bake?.skin === from;
    renameQuestion.textContent = `New name of skin "${from}" of ${owner.title} (${owner.owner}) in ${item.dataset}. Every instance on it keeps it${baked ? ', and the bake names the new name' : ''}.`;
    const check = (): void => {
      const why = renameRefusal(nameBox.value, from, names);
      renameWhy.textContent = why;
      renaming.yes.disabled = why !== '';
    };
    nameBox.oninput = check;
    nameBox.onkeydown = (e) => {
      if (e.key === 'Enter' && !renaming.yes.disabled) renaming.settle(true);
    };
    nameBox.value = from;
    check();
    const answer = renaming.ask();
    nameBox.focus();
    nameBox.select();
    if (!(await answer)) return null;
    const to = nameBox.value;
    await moving(item, from, to, { owner: owner.owner, action: 'rename', name: from, new: to });
    return to;
  }

  async function remove(item: Item, skin: string): Promise<boolean> {
    const owner = await ownerOf(item);
    if (!(await deleting.ask(`Delete skin "${skin}" of ${owner.title} (${owner.owner})? Instances on it will show Original.`))) return false;
    await moving(item, skin, ORIGINAL_SKIN, { owner: owner.owner, action: 'delete', name: skin });
    return true;
  }

  async function removeVariant(game: string, dataset: string, asset: string, variant: string): Promise<boolean> {
    if (!(await removing.ask(`Delete variant ${variant} of ${fileOf(asset)} in the texture store? Its file is removed for every dataset that shares this texture. A skin that names it uses the original for this texture from then on. The original and the bakes do not change.`))) return false;
    const response = await fetch(textureRoutes.remove(game, dataset), { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ asset, variant } satisfies TextureRemoveAsk) });
    const answer: unknown = await response.json();
    if (!response.ok) throw new Error(`${variant} of ${fileOf(asset)} was not deleted: ${String(Reflect.get(Object(answer), 'error') ?? response.status)}`);
    events.emit('textures-changed', { game, dataset });
    return true;
  }

  async function saveTo(ask: SaveAsk): Promise<string | null> {
    const found = await skins.readOwner(ask.game, ask.dataset, ask.owner);
    if (!found) throw new Error(`${ask.dataset} has no owner ${ask.owner} with textures`);
    const owner: OwnerState = found;
    const item = ask.item === null ? null : (scene.items.find((one) => one.id === ask.item) ?? null);
    const saved = owner.skins.map((skin) => skin.name);
    newLabel.textContent = `New skin: ${owner.next}`;
    existing.replaceChildren(...saved.map((name) => make('option', { value: name, textContent: name })));
    intoExisting.disabled = saved.length === 0;
    existing.disabled = saved.length === 0;
    // The same target the window counted its picks against (texview/main.ts baseOf).
    const first = firstSaveInto(owner, item ? item.skin : null);
    intoNew.checked = first.kind === 'new';
    intoExisting.checked = first.kind === 'existing';
    if (first.kind === 'existing') existing.value = first.skin;
    /** The picks that change the target. */
    const real = (): TexturePick[] => ask.picks.filter((pick) => namedInto(owner, intoNow(), pick.asset) !== pick.variant);
    const labelOf = (into: SaveInto): string => (into.kind === 'new' ? owner.next : skinLabel(into.skin));
    function show(): void {
      const into = intoNow();
      changes.replaceChildren(
        ...ask.picks.map((pick) => {
          const from = namedInto(owner, into, pick.asset);
          const line = make('li', { className: from === pick.variant ? 'same' : 'change', textContent: `${fileOf(pick.asset)}: ${from === pick.variant ? `${from}, no change` : `${from} → ${pick.variant}`}`, title: pick.asset });
          line.dataset['asset'] = pick.asset;
          return line;
        }),
      );
      question.textContent = [
        `${owner.title} (${owner.owner}) in ${ask.dataset}: ${real().length} of ${ask.picks.length} textures change in ${labelOf(into)}.`,
        'Bakes, Original and the other skins do not change.',
        ...(into.kind === 'new' ? [`${owner.next} will be made from Original; the textures not picked show their original.`] : []),
        item ? `This instance will show ${labelOf(into)}.` : 'No instance changes its skin.',
      ].join(' ');
      draft.yes.disabled = real().length === 0;
    }
    intoNew.onchange = show;
    intoExisting.onchange = show;
    existing.onchange = () => {
      intoExisting.checked = true;
      show();
    };
    show();
    const answer = draft.ask();
    draft.no.focus();
    if (!(await answer)) return null;
    const picked = real();
    const chosen = intoNow();
    // The pipeline names a new skin; the page takes the name it answers.
    const into = chosen.kind === 'new' ? await made(ask.game, ask.dataset, ask.owner, ORIGINAL_SKIN) : chosen.skin;
    for (const pick of picked) await skins.change(ask.game, ask.dataset, textureRoutes.skin(ask.game, ask.dataset), { owner: ask.owner, action: 'set', name: into, asset: pick.asset, variant: pick.variant });
    if (item && item.skin !== into) await skins.set(item, into);
    return into;
  }

  function state(): ReturnType<SkinActions['state']> {
    const open = [...all.map((one) => one.dialog), draft].find((one) => one.dialog.isOpen);
    if (!open) return null;
    const node = open.dialog.node;
    const isDraft = open === draft;
    const isRename = open === renaming;
    return {
      id: node.id,
      title: node.querySelector('.dialog-head span')?.textContent ?? '',
      text: node.querySelector('p.skin-question')?.textContent ?? '',
      buttons: [...node.querySelectorAll('.answers button')].map((b) => b.textContent ?? ''),
      danger: open.yes.classList.contains('danger'),
      into: isDraft ? intoNow() : null,
      next: isDraft ? (newLabel.textContent ?? '') : '',
      skins: isDraft ? [...existing.options].map((option) => option.value) : [],
      existingDisabled: isDraft ? intoExisting.disabled : false,
      lines: isDraft ? [...changes.children].map((line) => line.textContent ?? '') : isRename ? [renameWhy.textContent ?? ''] : [],
      name: isRename ? nameBox.value : '',
      yesDisabled: open.yes.disabled,
    };
  }

  return { create, rename, remove, saveTo, removeVariant, state };
}

