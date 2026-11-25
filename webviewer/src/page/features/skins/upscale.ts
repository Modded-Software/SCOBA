// The upscale dialog (SPEC-VIEWER 17.5): one dialog, opened on one texture
// or on an instance's whole owner. Its choices are what the pipeline's state
// offers (features/skins/choices.ts). It closes when the call answers; a
// refusal keeps it open with the reason (R-VIEW-123).

import { NEW_SKIN, skinLabel, textureRoutes, type OwnerState, type TexturesHead, type TextureState } from '../../../shared/textures';
import type { FeatureContext } from '../../core/context';
import { make, messageOf } from '../../core/dom';
import type { Item } from '../../core/types';
import { Dialog } from '../../ui/components/dialog';
import { inputsOf, modelChoices, ownerPlan, sizeChoices, type Choice } from './choices';

/** What the open dialog is on. */
type Target = { kind: 'texture'; game: string; dataset: string; state: TextureState } | { kind: 'owner'; item: Item; owner: OwnerState; states: Map<string, TextureState> };

export interface UpscaleState {
  open: boolean;
  kind: 'texture' | 'owner' | null;
  inputs: string[];
  models: { id: string; disabled: boolean; reason: string }[];
  sizes: { size: number; disabled: boolean; reason: string }[];
  lines: string[];
  error: string;
}

export interface UpscaleDialog {
  openTexture(game: string, dataset: string, asset: string): Promise<void>;
  openOwner(item: Item): Promise<void>;
  state(): UpscaleState;
}

function fill(select: HTMLSelectElement, choices: readonly Choice[], keep: string): void {
  select.replaceChildren(
    ...choices.map((choice) => {
      const option = make('option', { value: choice.value, textContent: choice.reason ? `${choice.label} (${choice.reason})` : choice.label, disabled: Boolean(choice.reason) });
      option.dataset['reason'] = choice.reason;
      return option;
    }),
  );
  const usable = choices.filter((choice) => !choice.reason);
  select.value = usable.some((choice) => choice.value === keep) ? keep : (usable[0]?.value ?? choices[0]?.value ?? '');
}

export function createUpscale({ skins, status }: Pick<FeatureContext, 'skins' | 'status'>): UpscaleDialog {
  const dialog = new Dialog({ id: 'upscale-dialog', title: 'Upscale' });
  const input = make('select', { className: 'upscale-input' });
  const model = make('select', { className: 'upscale-model' });
  const size = make('select', { className: 'upscale-size' });
  const what = make('div', { className: 'upscale-what' });
  const lines = make('div', { className: 'upscale-lines' });
  const error = make('div', { className: 'upscale-error failure' });
  const submit = make('button', { className: 'primary upscale-submit', textContent: 'Upscale' });
  dialog.body.append(what, make('label', { className: 'upscale-row' }, ['Input ', input]), make('label', { className: 'upscale-row' }, ['Model ', model]), make('label', { className: 'upscale-row' }, ['Size ', size]), lines, error, make('div', { className: 'answers' }, [submit]));
  let target: Target | null = null;
  let head: TexturesHead = { sizes: [], models: [], limits: [] };
  /** The title and the button name what is upscaled (R-VIEW-128). */
  const named = (text: string): void => {
    submit.textContent = text;
    dialog.node.querySelector('.dialog-head span')?.replaceChildren(text);
  };

  function update(): void {
    if (!target) return;
    lines.replaceChildren();
    if (target.kind === 'texture') {
      fill(model, modelChoices(target.state, head, input.value), model.value);
      fill(size, sizeChoices(target.state, head, input.value, model.value), size.value);
    } else {
      fill(model, head.models.map((one) => ({ value: one.id, label: one.title, reason: '' })), model.value);
      fill(size, head.sizes.map((one) => ({ value: String(one), label: String(one), reason: '' })), size.value);
      const plan = ownerPlan(target.owner, target.item.skin, target.states, model.value, Number(size.value));
      if (plan.data) lines.append(make('div', { className: 'upscale-data', textContent: `${plan.data} data textures get fast` }));
      if (plan.kept.length) lines.append(make('div', { className: 'upscale-kept', textContent: `${plan.kept.length} textures cannot reach ${size.value} and keep their variant`, title: plan.kept.join('\n') }));
      lines.append(make('div', { className: 'upscale-asked', textContent: `${plan.asked} textures get a request` }));
      lines.append(make('div', { className: 'upscale-into', textContent: 'The result goes to New Skin; save it to give it a name.' }));
    }
    submit.disabled = !model.value || !size.value || [...model.selectedOptions, ...size.selectedOptions].some((option) => option.disabled);
  }

  async function openTexture(game: string, dataset: string, asset: string): Promise<void> {
    const body = await skins.judge(game, dataset, [asset]);
    const [state] = body.textures;
    if (!state) throw new Error(`${dataset} has no texture ${asset}`);
    head = body;
    target = { kind: 'texture', game, dataset, state };
    named('Upscale Texture');
    what.textContent = `${asset} in ${dataset}`;
    input.disabled = false;
    fill(input, inputsOf(state).map((id) => ({ value: id, label: id, reason: '' })), input.value);
    error.textContent = '';
    update();
    dialog.open();
  }

  async function openOwner(item: Item): Promise<void> {
    const owner = skins.owner(item);
    if (!owner) throw new Error('this instance has no texture owner');
    const body = await skins.judge(item.game, item.dataset, owner.textures);
    head = body;
    target = { kind: 'owner', item, owner, states: new Map(body.textures.map((state) => [state.asset, state])) };
    named('Upscale Skin');
    what.textContent = `${owner.title} (${owner.owner}) in ${item.dataset}: ${owner.textures.length} textures`;
    input.replaceChildren(make('option', { value: item.skin, textContent: `skin ${skinLabel(item.skin)}, as shown now` }));
    input.disabled = true;
    error.textContent = '';
    update();
    dialog.open();
  }

  async function send(): Promise<void> {
    const mine = target;
    if (!mine) return;
    const sized = Number(size.value);
    if (mine.kind === 'texture') {
      await skins.change(mine.game, mine.dataset, textureRoutes.request(mine.game, mine.dataset), { asset: mine.state.asset, input: input.value, model: model.value, size: sized });
      status.setStatus(`${mine.state.asset}: ${model.value} at ${sized} requested`);
    } else {
      const { item, owner } = mine;
      // Into New Skin (R-VIEW-117); the server refuses it while New Skin is stored.
      await skins.change(item.game, item.dataset, textureRoutes.skin(item.game, item.dataset), { owner: owner.owner, action: 'upscale', name: NEW_SKIN, from: item.skin, model: model.value, size: sized });
      await skins.set(item, NEW_SKIN);
      status.setStatus(`${owner.title}: New Skin made; save it to give it a name`);
    }
  }

  submit.addEventListener('click', () => {
    submit.disabled = true;
    error.textContent = '';
    send().then(
      () => {
        target = null;
        dialog.close();
      },
      (failure: unknown) => {
        error.textContent = messageOf(failure);
        update();
      },
    );
  });
  for (const select of [input, model, size]) select.addEventListener('change', update);

  function state(): UpscaleState {
    const options = (select: HTMLSelectElement) => [...select.options];
    return {
      open: dialog.isOpen,
      kind: target?.kind ?? null,
      inputs: options(input).map((option) => option.value),
      models: options(model).map((option) => ({ id: option.value, disabled: option.disabled, reason: option.dataset['reason'] ?? '' })),
      sizes: options(size).map((option) => ({ size: Number(option.value), disabled: option.disabled, reason: option.dataset['reason'] ?? '' })),
      lines: [...lines.children].map((line) => line.textContent),
      error: error.textContent,
    };
  }

  return { openTexture, openOwner, state };
}
