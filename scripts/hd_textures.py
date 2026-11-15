"""Upscale the game textures the map uses and cache them for the build.

    list      show the textures a source resolves to
    build     extract, upscale, and encode them into the cache (uses the GPU)
    verify    check the cache against its manifest and the quality limits
    preview   write comparison sheets for judging the result by eye
    compare   write a web page that shows every texture next to its cached variants

`--variant` names the set of models: "upscale" (Upscale 4x) or "generative"
(Generative 4x). Each variant has its own cache. The map build injects the
one SC2_HD_TEXTURES names. See docs/specifications/SPEC-HD-TEXTURES.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hdtex import check, compare, pipeline, preview
from hdtex.casc import Casc, CascError
from hdtex.inject import InjectError, load_manifests
from hdtex.roles import ROLES, RoleError
from hdtex.sources import SOURCES, SourceError
from hdtex.upscaler import UpscaleError
from hdtex.variants import DEFAULT, VARIANTS
from project_root import project_root

# Limits for `verify`. The measured values are in the manifest.
# BC3 loss on the largest level, in dB. The terrain set measures 36.7 and up.
MIN_ENCODE_PSNR = 35.0
# The result shrunk to the source size must be the same picture. An inverted
# channel correlates below zero, a swapped one near zero. The set measures 0.83 and up.
MIN_FIDELITY_CORR = 0.7
# Far view: a small mip of the result against the same mip of the source, in levels.
# The set measures 0.82 at most. Without the low-frequency match it measures 1.90 and up.
MAX_COARSE_RMSE = 1.5
# Seam step of the result relative to the source. Some originals have a seam of their own.
MAX_SEAM_GROWTH = 1.5


def default_map() -> Path:
    return project_root() / "src" / "SCOBA.SC2Map"


def parse_models(values: list[str]) -> tuple[tuple[str, str], ...]:
    """`PLANE=MODEL` for every texture, `TEXTURE.PLANE=MODEL` for one, such as zerus_4.color=fast."""
    planes = {plane.name for role in ROLES.values() for plane in role.planes}
    pairs = []
    for value in values:
        key, _, model = value.partition("=")
        if key.rsplit(".", 1)[-1] not in planes or not model:
            raise SystemExit(
                f"--model needs [TEXTURE.]PLANE=MODEL with PLANE one of {', '.join(sorted(planes))}: {value}"
            )
        pairs.append((key.lower(), model))
    return tuple(pairs)


def cmd_list(args: argparse.Namespace) -> int:
    work = pipeline.variant_root(args.variant) / args.source
    work.mkdir(parents=True, exist_ok=True)
    for ref in SOURCES[args.source](args.map, Casc(), work):
        entries = ", ".join(f"{o.entry}.{o.field}" for o in ref.overrides)
        print(f"{ref.role:8s} {ref.asset}  <-  {ref.casc_path}  ->  {ref.map_path}  ({entries})")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    settings = pipeline.Settings(
        models=parse_models(args.model),
        max_size=args.max_size,
        wrap=not args.no_wrap,
        gpu=args.gpu,
        tile=args.tile,
        variant=args.variant,
    )
    manifest = pipeline.build(args.source, args.map, settings, force=args.force)
    print(f"hdtex: wrote {manifest}")
    return cmd_verify(args)


def lowest_correlation(texture: dict) -> float:
    """Lowest correlation over the channels that carry a picture."""
    values = [value for value in texture["fidelity_corr"] if value is not None]
    if not values:
        raise SystemExit(f"{texture['file']}: every channel is constant, nothing to compare")
    return min(values)


def texture_problems(folder: Path, texture: dict) -> list[str]:
    path = folder / texture["file"]
    if not path.is_file():
        return ["file is missing"]
    problems = []
    if pipeline.file_sha256(path) != texture["sha256"]:
        problems.append("file does not match the manifest hash")
    # Channels that hold a constant score 99 and never limit the minimum.
    if min(texture["encode_psnr"]) < MIN_ENCODE_PSNR:
        problems.append(f"encode PSNR {min(texture['encode_psnr'])} dB is below {MIN_ENCODE_PSNR}")
    if lowest_correlation(texture) < MIN_FIDELITY_CORR:
        problems.append(f"correlation with the source {lowest_correlation(texture)} is below {MIN_FIDELITY_CORR}")
    if texture["coarse_rmse"] > MAX_COARSE_RMSE:
        problems.append(f"coarse mip differs from the source by {texture['coarse_rmse']} levels, limit {MAX_COARSE_RMSE}")
    if texture["seam"] > max(1.0, texture["seam_source"]) * MAX_SEAM_GROWTH:
        problems.append(f"seam ratio {texture['seam']} against {texture['seam_source']} in the source")
    return problems


def cached(args: argparse.Namespace) -> list[tuple[Path, dict]]:
    """The manifests of the asked variant. None is an error the caller reports."""
    cache = pipeline.variant_root(args.variant)
    manifests = load_manifests(cache)
    if not manifests:
        print(f"hdtex: no cache at {cache}", file=sys.stderr)
    return manifests


def cmd_verify(args: argparse.Namespace) -> int:
    manifests = cached(args)
    if not manifests:
        return 1
    failures = 0
    for folder, manifest in manifests:
        by_model: dict[str, list[str]] = {}
        for key, model in sorted(manifest["settings"]["models"].items()):
            by_model.setdefault(model, []).append(key)
        print(f"{VARIANTS[args.variant].title}: {manifest['source']}: models {json.dumps(by_model, sort_keys=True)}")
        for texture in manifest["textures"]:
            problems = texture_problems(folder, texture)
            if not problems:
                check.check_texture_file(folder / texture["file"])
            size = "x".join(str(v) for v in texture["size"])
            print(
                f"  {'FAIL' if problems else 'ok  '} {Path(texture['file']).name:30s} {texture['role']:8s} {size:10s} "
                f"mips {texture['mips']:2d}  encode {min(texture['encode_psnr']):5.1f} dB  "
                f"corr {lowest_correlation(texture):.2f}  coarse {texture['coarse_rmse']:.2f}  "
                f"seam {texture['seam']:.2f} (source {texture['seam_source']:.2f})"
            )
            for problem in problems:
                print(f"       {problem}")
            failures += bool(problems)
    print(f"hdtex: verify failures: {failures}")
    return 1 if failures else 0


def cmd_preview(args: argparse.Namespace) -> int:
    manifests = cached(args)
    for folder, manifest in manifests:
        for path in preview.write_sheets(folder, manifest):
            print(path)
    return 0 if manifests else 1


def cmd_compare(args: argparse.Namespace) -> int:
    """One page for every cached variant. `--variant` plays no part."""
    print(compare.write_page(args.source))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--map", type=Path, default=default_map(), help="map source folder (default: src/SCOBA.SC2Map)")
    parser.add_argument("--source", choices=sorted(SOURCES), default="terrain", help="kind of textures (default: terrain)")
    titles = ", ".join(f"{key}: {variant.title}" for key, variant in VARIANTS.items())
    parser.add_argument("--variant", choices=list(VARIANTS), default=DEFAULT, help=f"set of models ({titles}; default: {DEFAULT})")
    commands = parser.add_subparsers(dest="command", required=True, metavar="command")
    commands.add_parser("list", help="show the textures a source resolves to").set_defaults(handler=cmd_list)
    build = commands.add_parser("build", help="extract, upscale, and encode into the cache")
    build.add_argument("--gpu", type=int, help="GPU index for arc-upscale (default: its own default)")
    build.add_argument("--tile", type=int, help="arc-upscale tile size; lower it if VRAM runs out")
    build.add_argument("--max-size", type=int, default=4096, help="largest texture side to keep (default: 4096)")
    build.add_argument("--model", action="append", default=[], metavar="[TEXTURE.]PLANE=MODEL", help="upscaler model for a plane")
    build.add_argument("--no-wrap", action="store_true", help="do not make opposite edges match; for textures that do not tile")
    build.add_argument("--force", action="store_true", help="redo every stage")
    build.set_defaults(handler=cmd_build)
    commands.add_parser("verify", help="check the cache").set_defaults(handler=cmd_verify)
    commands.add_parser("preview", help="write comparison sheets").set_defaults(handler=cmd_preview)
    commands.add_parser("compare", help="write the web page with every cached variant").set_defaults(handler=cmd_compare)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (CascError, SourceError, RoleError, UpscaleError, InjectError, compare.CompareError, pipeline.InputError) as error:
        print(f"hdtex: error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
