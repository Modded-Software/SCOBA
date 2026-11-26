"""Make the variants of a recipe on request.

`make` runs in the program that was asked. It hands each plane to the
runner, waits, joins, encodes, and keeps the variants. While it runs, the
recipe's folder holds request.json: which program, which step, which
upscale folders. request.log beside it holds every step with its time, and
the trace of a failure. `progress` reads how far a request is.

Each change of a request's state is written to the state index, for every
dataset that holds the texture (SPEC-HD-TEXTURES 4.9).
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import numpy as np

from . import dds, encode, keptrecipe, results, steps, variants
from .dataset import Dataset
from .interfaces import DONE, FAILED, RUNNING, WAITING, Runner, Texture
from .progress import (
    ENCODING,
    FILE,
    JOB_FILE,
    LOG_FILE,
    UPSCALING,
    RequestError,
    job_of,
    model_refusal,
    refusal,
    started,
)
from .roles import ROLES  # loading it registers the roles
from .store import GameStore, StoreError, file_sha256, read_plane, write_json

BROKEN = ".broken"  # added to the name of an output that is no whole image
POLL_SECONDS = 1.0
# Jobs that wait while no worker runs fail the request after this long. A worker
# that is starting has the time to take its lock.
IDLE_LIMIT_SECONDS = 30.0
IDLE_LOOK_SECONDS = 10.0  # how often a request whose jobs all wait asks for a worker

LOG = logging.getLogger(__name__)


def _wait(
    runner: Runner,
    jobs: dict[str, Path],
    wait: Callable[[float], None],
    changed: Callable[[], None],
) -> None:
    """Return when every job is done and its output is there. Raise when one failed, is lost, or none can start.

    `changed` is called when a job's state is another than at the look before.
    """
    seen: dict[str, str] = {}
    quiet = 0.0  # seconds since a job of this request ran, or a worker was seen
    look_at = 0.0
    while True:
        open_jobs = []
        moved = False
        for job, output in jobs.items():
            found = runner.state(job)
            if seen.get(job) != found.state:
                LOG.info(
                    "job %s for %s: %s%s",
                    job,
                    output.name,
                    found.state,
                    f": {found.error}" if found.error else "",
                )
                seen[job] = found.state
                moved = True
            if found.state in (WAITING, RUNNING):
                open_jobs.append(found.state)
            elif found.state == FAILED:
                raise RequestError(
                    f"the upscaler failed on {output.name} (job {job}): {found.error or 'it gave no reason'}"
                )
            elif found.state != DONE:
                raise RequestError(found.error)
            elif not output.is_file():
                raise RequestError(
                    f"job {job} is done and wrote nothing: {output} is not there"
                )
        if moved:
            changed()
        if not open_jobs:
            return
        if RUNNING in open_jobs:
            quiet = look_at = 0.0
        elif quiet >= look_at:
            reason = runner.idle()
            LOG.info(
                "%d jobs wait for %.0f s: %s",
                len(open_jobs),
                quiet,
                reason or "a worker runs",
            )
            if not reason:
                quiet = 0.0
            elif quiet >= IDLE_LIMIT_SECONDS:
                raise RequestError(
                    f"{len(open_jobs)} jobs waited {quiet:.0f} s and {reason}"
                )
            look_at = quiet + IDLE_LOOK_SECONDS
        wait(POLL_SECONDS)
        quiet += POLL_SECONDS


def _ask(
    runner: Runner, source: Path, folder: Path, output: Path, model: str, tiles: bool
) -> str | None:
    """See that `output` is made. Returns the job to wait for. None: the output is there."""
    job = job_of(folder)
    before = runner.state(job) if job is not None else None
    if before is not None and before.state in (WAITING, RUNNING):
        LOG.info(
            "%s: job %s is asked for already and is %s", output.name, job, before.state
        )
        return job
    if output.is_file():
        LOG.info("%s: it is there", output.name)
        return None
    if before is not None:
        LOG.info(
            "%s: asked again; job %s before it is %s%s",
            output.name,
            job,
            before.state,
            f": {before.error}" if before.error else "",
        )
    job = runner.submit(source, folder, model, tiles)
    write_json(folder / JOB_FILE, {"job": job})
    return job


def _set_aside(output: Path, error: StoreError) -> str:
    """Move an output that is no whole image out of the way, and say what it was."""
    aside = output.with_name(output.name + BROKEN)
    said = f"{error} ({output.stat().st_size} bytes, sha256 {file_sha256(output)}); kept as {aside.name}"
    output.replace(aside)
    return said


def _step(
    game: GameStore,
    runner: Runner,
    texture: Texture,
    model: variants.Model,
    planes: dict,
    note: Callable[..., None],
    wait,
) -> dict:
    """One step on every plane of a texture. Returns the planes after it and the model of each."""
    role = ROLES.get(texture.role or "")
    version = runner.version()
    outputs: dict[str, Path] = {}
    folders: list[str] = []
    jobs: dict[str, Path] = {}
    models: dict[str, str | None] = {}
    for plane in role.planes:
        given = steps.prepare(planes[plane.name], plane.colour, texture.grid)
        models[plane.name] = None if given is None else model.model_for(plane)
        if given is None:
            continue
        source = game.plane_path(game.put_plane(given))
        folder = game.upscale_dir(source.stem, model.model_for(plane), version, texture.tiles)
        outputs[plane.name] = runner.output(source, folder)
        folders.append(str(folder))
        job = _ask(runner, source, folder, outputs[plane.name], model.model_for(plane), texture.tiles)
        if job is not None:
            jobs[job] = outputs[plane.name]
    note(phase=UPSCALING, jobs=folders)
    _wait(runner, jobs, wait, note)
    note(phase=ENCODING, jobs=folders)
    upscaled: dict[str, np.ndarray] = {}
    broken: list[str] = []
    for name, output in outputs.items():
        try:
            upscaled[name] = read_plane(output)
        except StoreError as error:
            broken.append(_set_aside(output, error))
    if broken:
        raise RequestError(
            f"the upscaler left {len(broken)} broken files; ask again: {'; '.join(broken)}"
        )
    made = {
        plane.name: steps.conclude(
            planes[plane.name], upscaled.get(plane.name), plane.colour, texture.grid
        )
        for plane in role.planes
    }
    return {"planes": made, "models": models, "runner": version}


def _make(
    dataset: Dataset,
    runner: Runner,
    texture: Texture,
    recipe: str,
    size: int,
    original: bytes,
    note: Callable[..., None],
    wait,
) -> dict:
    """Make `recipe` at `size`, and each recipe before it at the size the id names. Returns the entry of `recipe`."""
    game = dataset.game
    recipe_steps = variants.parse_recipe(recipe)
    role = ROLES.get(texture.role or "")
    sha256 = hashlib.sha256(original).hexdigest()
    planes = role.split(encode.read_texture(original)[1])
    entry: dict = {}
    # The nearest person's edit among the steps before: what a model's variant is matched to and
    # measured against, in place of the original (R-PC-83). None: no step before is an edit.
    reference: dict | None = None
    reference_id = ""
    for index, prefix in enumerate(variants.prefixes(recipe)):
        kept = game.entry(texture.origin, prefix)
        last = prefix == recipe
        if kept is not None:
            # A kept recipe is never made again (R-HD-158). `make` picked a last step that serves the request, and
            # refused a stale step before it; a step before the last is taken as it is kept (R-HD-159).
            if kept["original"]["sha256"] != sha256 or (last and results.edges_off(kept, texture.tiles)):
                raise RequestError(
                    f"step {index + 1}, {prefix}, is kept and does not serve this request; a kept variant is not made again"
                )
            LOG.info("step %d, %s: its recipe is kept", index + 1, prefix)
            if last:
                if not keptrecipe.holds(kept, size):
                    note(step=index + 1, phase=ENCODING, jobs=[])
                return keptrecipe.with_size(game, texture, kept, size, original, reference)
            planes = keptrecipe.planes(game, texture, prefix, kept, recipe_steps[index].size or 0)
            if results.user_made(kept):
                reference = planes
                reference_id = variants.variant_id(prefix, max(kept["size"]))
            continue
        if recipe_steps[index].edit:
            # No model makes an edit: only its transfer does.
            raise RequestError(
                f"step {index + 1}, {prefix}, is a person's edit that is not there; transfer the edit again"
            )
        if index:
            # The input of this step is the variant of the recipe before it at the size the recipe names.
            given = recipe_steps[index - 1].size or 0
            planes = {
                plane.name: steps.fit(planes[plane.name], given, plane.colour)
                for plane in role.planes
            }
        LOG.info("step %d, %s: upscaling", index + 1, prefix)
        step = _step(
            game,
            runner,
            texture,
            recipe_steps[index].model,
            planes,
            partial(note, step=index + 1),
            wait,
        )
        planes = step["planes"]
        LOG.info("step %d, %s: encoding", index + 1, prefix)
        encoded = encode.encode(original, role, planes, reference, tiles=texture.tiles)
        # One size is kept: the one asked for, and of a step before the last the one the id names (R-HD-123).
        wanted = size if last else recipe_steps[index].size or 0
        entry = keptrecipe.keep(
            game,
            texture,
            prefix,
            sha256,
            {
                # The variant its numbers compare with; empty: the original.
                "reference": reference_id,
                "role": role.name,
                "codec": encoded.format,
                "grid": list(texture.grid),
                "original": {"sha256": sha256, "size": list(encoded.source_size)},
                "size": list(encoded.size),
                "mips": encoded.mips,
                "planes": {
                    name: game.put_plane(plane) for name, plane in planes.items()
                },
                "models": step["models"],
                "runner": step["runner"],
                "encoder": encode.ENCODER_VERSION,
                results.TILES: texture.tiles,
                "numbers": encoded.numbers,
            },
            {wanted: encoded.file(wanted)},
        )
        if last:
            # Another request kept the recipe meanwhile, at another size: this one's is added to it.
            entry = keptrecipe.with_size(game, texture, entry, size, original, reference)
    return entry


@contextmanager
def _logged(path: Path) -> Iterator[None]:
    """While it is open, every line the core logs goes to the end of `path`, with its time and its process."""
    path.parent.mkdir(parents=True, exist_ok=True)
    core = logging.getLogger(__package__)
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(process)d %(name)s: %(message)s")
    )
    level = core.level
    core.addHandler(handler)
    core.setLevel(logging.INFO)
    try:
        yield
    finally:
        core.setLevel(level)
        core.removeHandler(handler)
        handler.close()


def _longest(texture: Texture, original: Path) -> int:
    try:
        header = dds.parse(original)
    except dds.DdsError as error:
        raise RequestError(
            f"{texture.asset}: its original cannot be read: {error}"
        ) from error
    return max(header.width, header.height)


def _cap() -> int:
    try:
        return variants.max_side()
    except variants.VariantError as error:
        raise RequestError(str(error)) from error


def by_factor(dataset: Dataset, texture: Texture, given: str, model: str, factor: int) -> str:
    """The variant `factor` times its input's side asks for, at most the largest side (R-HD-123)."""
    try:
        recipe = variants.extended(given, model)
    except variants.VariantError as error:
        raise RequestError(f"{texture.asset}: {error}") from error
    if reason := model_refusal(texture, recipe):
        raise RequestError(f"{texture.asset}, {recipe}: {reason}")
    longest = _longest(texture, dataset.original(texture))
    if reason := refusal(texture, recipe, longest):
        raise RequestError(f"{texture.asset}, {recipe}: {reason}")
    side, reason = variants.factor_side(recipe, factor, longest, _cap())
    if reason:
        raise RequestError(f"{texture.asset}, {recipe}, {factor}x: {reason}")
    return variants.variant_id(recipe, side)


def make(
    dataset: Dataset,
    runner: Runner,
    texture: Texture,
    variant: str,
    wait: Callable[[float], None] = time.sleep,
) -> dict:
    """Make a variant of a texture: its recipe, at the size asked for, and the recipes before it. Returns the entry
    of the recipe that serves the request.

    Its size is at most the largest side (variants.max_side). The file of
    that size is kept, and of no other (R-HD-123). A recipe that is kept
    and lacks the size gets it with no job (`keptrecipe.with_size`).

    A kept variant is never made again (R-HD-158). One that is sound is
    the answer. One that is stale, or has edges of the other rule, stays
    as it is: the request makes the next revision beside it, or finds a
    revision that is sound (results.served). The entry's `recipe` names
    which. A kept step before the last is the input as it is (R-HD-159); a
    stale one refuses the request.

    A refused request leaves nothing. A failure leaves the reason in
    request.json, its trace in request.log, and no variant; the planes
    that were upscaled stay.

    Every change of its state goes to the state index: `note` writes it.
    """
    recipe, size = variants.split(variant)
    if not recipe:
        raise RequestError(f"{texture.asset}: the original is not made; it is there")
    if reason := model_refusal(texture, recipe):
        raise RequestError(f"{texture.asset}, {recipe}: {reason}")
    original = dataset.original(texture)
    longest = _longest(texture, original)
    cap = _cap()
    if size > cap:
        raise RequestError(
            f"{texture.asset}, {variant}: {size} is above the largest side, {cap} ({variants.MAX_SIDE_ENV})"
        )
    if reason := refusal(texture, recipe, longest) or variants.size_refusal(
        recipe, size, longest
    ):
        raise RequestError(f"{texture.asset}, {variant}: {reason}")
    made = dataset.made(texture)
    if reason := keptrecipe.input_refusal(made, recipe):
        raise RequestError(f"{texture.asset}, {variant}: {reason}")
    return _run(dataset, runner, texture, results.served(made, variant), made, original, wait)


def _run(
    dataset: Dataset,
    runner: Runner,
    texture: Texture,
    variant: str,
    made: dict[str, results.Made],
    original: bytes,
    wait: Callable[[float], None],
) -> dict:
    """Run the request of the variant that serves it (`results.served`): write its state, make it, clear the state."""
    recipe, size = variants.split(variant)
    if recipe in made and (reason := keptrecipe.size_refusal(made[recipe].entry, size)):
        raise RequestError(f"{texture.asset}, {variant}: {reason}")
    folder = dataset.game.recipe_dir(texture.origin, recipe)
    said = {
        "pid": os.getpid(),
        "started": started(os.getpid()),
        "since": time.time(),
        "variant": variant,
        "step": 1,
        "steps": len(variants.parse_recipe(recipe)),
        "phase": UPSCALING,
        "jobs": [],
        "failed": "",
    }

    def note(**fields: object) -> None:
        said.update(fields)
        write_json(folder / FILE, said)
        dataset.changed(texture)

    note()
    with _logged(folder / LOG_FILE):
        LOG.info("request: %s, %s, in dataset %s", texture.asset, recipe, dataset.name)
        start = time.monotonic()
        try:
            entry = _make(dataset, runner, texture, recipe, size, original, note, wait)
        except BaseException as error:
            # Whatever stops the request is written down where the next reader looks, with its trace.
            reason = (
                str(error)
                if isinstance(error, RequestError)
                else f"{type(error).__name__}: {error}"
            )
            LOG.exception("failed after %.1f s: %s", time.monotonic() - start, reason)
            note(failed=reason)
            if not isinstance(error, Exception):
                raise  # the program is being stopped
            raise RequestError(
                f"{texture.asset}, {recipe}: {reason}; the trace is in {folder / LOG_FILE}"
            ) from error
        LOG.info("done after %.1f s", time.monotonic() - start)
    # Another request of the same recipe may have ended first and removed it.
    (folder / FILE).unlink(missing_ok=True)
    dataset.changed(texture)
    return entry
