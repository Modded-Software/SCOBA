// The upscale dialog (SPEC-VIEWER 17.5): one dialog, opened on one texture
// or on an instance's whole owner. Its choices are what the pipeline's state
// offers (features/skins/choices.ts). It opens at once and waits for the
// state with a line; while its call is out the button says "Requesting…"
// (R-VIEW-145). It may be closed at any time; the request goes on. It
// closes when the call answers; a refusal keeps it open with the reason
// (R-VIEW-123).

import { NEW_SKIN, skinLabel, textureRoutes, type OwnerState, type TexturesHead, type TextureState } from '../../../shared/textures';
import type { FeatureContext } from '../../core/context';
import { make, messageOf } from '../../core/dom';
import type { Item } from '../../core/types';
import { Dialog } from '../../ui/components/dialog';
import { stepSelect } from '../../ui/components/stepper';
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
  /** It waits for the state: "Reading what can be made…" shows. */
  reading: boolean;
  /** Its call is out: the button says "Requesting…" and is disabled. */
  sending: boolean;
  /** The line that says it may be closed. */
  note: string;
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
  const input = stepSelect(make('select', { className: 'upscale-input' }));
  const model = stepSelect(make('select', { className: 'upscale-model' }));
  const size = stepSelect(make('select', { className: 'upscale-size' }));
  const what = make('div', { className: 'upscale-what' });
  const lines = make('div', { className: 'upscale-lines' });
  const error = make('div', { className: 'upscale-error failure' });
  const wait = make('div', { className: 'upscale-wait', textContent: 'Reading what can be made…', hidden: true });
  const note = make('div', { className: 'upscale-note' });
  const submit = make('button', { className: 'primary upscale-submit', textContent: 'Upscale' });
  dialog.body.append(what, wait, make('label', { className: 'upscale-row' }, ['Input ', input]), make('label', { className: 'upscale-row' }, ['Model ', model]), make('label', { className: 'upscale-row' }, ['Size ', size]), lines, note, error, make('div', { className: 'answers' }, [submit]));
  let target: Target | null = null;
  let head: TexturesHead = { sizes: [], models: [], limits: [] };
  /** Counts the opens: a judge or a call that answers after another open changes nothing of it. */
  let turn = 0;
  /** The call of this turn is out (R-VIEW-145). */
  let sending = false;
  /** The button's own name, while it is not sending. */
  let label = 'Upscale';
  /** The title and the button name what is upscaled (R-VIEW-128). */
  const named = (text: string): void => {
    label = text;
    submit.textContent = text;
    dialog.node.querySelector('.dialog-head span')?.replaceChildren(text);
  };

  /** Open at once, before the state is read: the dialog waits with a line, not the page (R-VIEW-145). */
  function opening(title: string, about: string, progress: string): number {
    const mine = ++turn;
    target = null;
    sending = false;
    named(title);
    what.textContent = about;
    note.textContent = `You can close this dialog. The progress shows on ${progress} in the texture window.`;
    wait.hidden = false;
    error.textContent = '';
    lines.replaceChildren();
    for (const select of [input, model, size]) {
      select.replaceChildren();
      select.disabled = true;
    }
    submit.disabled = true;
    submit.classList.remove('busy');
    dialog.open();
    return mine;
  }

  /** The state is read: the choices fill in. */
  function ready(): void {
    wait.hidden = true;
    model.disabled = false;
    size.disabled = false;
  }

  function update(): void {
    if (!target) return;
    submit.textContent = sending ? 'Requesting…' : label;
    submit.classList.toggle('busy', sending);
    for (const select of [model, size]) select.disabled = sending;
    if (target.kind === 'texture') input.disabled = sending;
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
    submit.disabled = sending || !model.value || !size.value || [...model.selectedOptions, ...size.selectedOptions].some((option) => option.disabled);
  }

  /** A judge that failed: the dialog stays open with the reason. */
  function unread(mine: number, failure: unknown): void {
    if (mine !== turn) return;
    wait.hidden = true;
    error.textContent = `what can be made cannot be read: ${messageOf(failure)}`;
  }

  async function openTexture(game: string, dataset: string, asset: string): Promise<void> {
    const mine = opening('Upscale Texture', `${asset} in ${dataset}`, "this texture's tile");
    let body: Awaited<ReturnType<typeof skins.judge>>;
    try {
      body = await skins.judge(game, dataset, [asset]);
    } catch (failure) {
      unread(mine, failure);
      return;
    }
    if (mine !== turn || !dialog.isOpen) return;
    const [state] = body.textures;
    if (!state) {
      unread(mine, new Error(`${dataset} has no texture ${asset}`));
      return;
    }
    head = body;
    target = { kind: 'texture', game, dataset, state };
    ready();
    input.disabled = false;
    fill(input, inputsOf(state).map((id) => ({ value: id, label: id, reason: '' })), input.value);
    update();
  }

  async function openOwner(item: Item): Promise<void> {
    const owner = skins.owner(item);
    if (!owner) throw new Error('this instance has no texture owner');
    const mine = opening('Upscale Skin', `${owner.title} (${owner.owner}) in ${item.dataset}: ${owner.textures.length} textures`, "each texture's tile");
    let body: Awaited<ReturnType<typeof skins.judge>>;
    try {
      body = await skins.judge(item.game, item.dataset, owner.textures);
    } catch (failure) {
      unread(mine, failure);
      return;
    }
    if (mine !== turn || !dialog.isOpen) return;
    head = body;
    target = { kind: 'owner', item, owner, states: new Map(body.textures.map((state) => [state.asset, state])) };
    ready();
    input.replaceChildren(make('option', { value: item.skin, textContent: `skin ${skinLabel(item.skin)}, as shown now` }));
    input.disabled = true;
    update();
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

  // One call at a time; the dialog may be closed meanwhile and the request goes on (R-VIEW-121, R-VIEW-145).
  submit.addEventListener('click', () => {
    if (sending || !target) return;
    const mine = turn;
    sending = true;
    error.textContent = '';
    update();
    const done = (): void => {
      if (mine !== turn) return;
      sending = false;
      submit.classList.remove('busy');
    };
    send().then(
      () => {
        done();
        if (mine !== turn) return;
        target = null;
        dialog.close();
      },
      (failure: unknown) => {
        done();
        // Closed meanwhile: the refusal goes to the status line.
        if (mine !== turn || !dialog.isOpen) {
          status.reportFailure(failure);
          return;
        }
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
      reading: !wait.hidden,
      sending,
      note: note.textContent,
    };
  }

  return { openTexture, openOwner, state };
}
