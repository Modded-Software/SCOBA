"""Search, filter, extract, preview, and browse SC2 CASC resources."""

import argparse
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from project_root import project_root

ROOT = project_root()
DEFAULT_STORMEX = ROOT / "tools" / "stormex"
DEFAULT_SC2 = Path(
    os.environ.get(
        "SC2_INSTALL",
        str(
            Path.home()
            / "Games/battlenet-prefix/pfx/drive_c/Program Files (x86)/StarCraft II"
        ),
    )
)
DEFAULT_OUT = Path("/mnt/ws-fast/sc2res")


def find_stormex():
    value = os.environ.get("STORMEX")
    if value:
        return Path(value)
    if DEFAULT_STORMEX.exists():
        return DEFAULT_STORMEX
    found = shutil.which("stormex")
    if found:
        return Path(found)
    sys.exit("stormex not found. Set STORMEX or place it at tools/stormex.")


def find_sc2():
    value = os.environ.get("SC2_PATH")
    if value:
        return Path(value)
    if DEFAULT_SC2.exists():
        return DEFAULT_SC2
    sys.exit("SC2 install not found. Set SC2_PATH.")


def exts_from(value):
    if not value:
        return None
    return tuple("." + part.strip().lower().lstrip(".") for part in value.split(",") if part.strip())


def run_stormex(args):
    cmd = [str(find_stormex()), "-S", str(find_sc2())] + args
    proc = subprocess.run(cmd, text=True, capture_output=True)
    if proc.returncode != 0 and proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc


def parse_paths(text, exts=None):
    result = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if exts and not line.lower().endswith(exts):
            continue
        result.append(line)
    return result


def stormex_failure(proc):
    if proc.returncode == 0:
        return
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    sys.exit(proc.returncode)


def output_dir(args, name):
    root = Path(args.out).expanduser() if args.out else DEFAULT_OUT / name
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def list_command(args):
    search = []
    if args.regex:
        search = ["-i", args.regex]
    elif args.pattern:
        search = ["-s", args.pattern]
    proc = run_stormex(search + ["-l"])
    stormex_failure(proc)
    paths = parse_paths(proc.stdout, exts_from(args.ext))
    if args.limit:
        paths = paths[: args.limit]
    if args.json:
        print(json.dumps(paths, indent=2))
    else:
        for path in paths:
            print(path)


def extract_command(args):
    out = output_dir(args, "extract")
    if args.exact:
        search = ["-s", Path(args.pattern.replace("\\", "/")).name]
    else:
        search = ["-s", args.pattern]
    proc = run_stormex(search + ["-x", "-o", str(out)])
    stormex_failure(proc)
    print(out)


def convert_file(source, target):
    try:
        from PIL import Image
    except ImportError:
        sys.exit("Pillow is required for preview. Install project dependencies.")
    with Image.open(source) as image:
        image = image.convert("RGBA")
        Image.alpha_composite(Image.new("RGBA", image.size, "#202020"), image).convert("RGB").save(target)


def preview_command(args):
    out = output_dir(args, "preview")
    tmp_root = DEFAULT_OUT / "tmp"
    tmp_root.mkdir(parents=True, exist_ok=True)
    converted = []
    with tempfile.TemporaryDirectory(prefix="sc2res-", dir=str(tmp_root)) as tmp:
        raw = Path(tmp)
        proc = run_stormex(["-s", args.pattern, "-x", "-o", str(raw)])
        stormex_failure(proc)
        wanted = exts_from(".dds,.tga") if not args.ext else exts_from(args.ext)
        files = sorted(p for p in raw.rglob("*") if p.is_file() and p.name.lower().endswith(wanted))
        if args.limit:
            files = files[: args.limit]
        for source in files:
            name = source.name.rsplit(".", 1)[0] + ".png"
            target = out / name
            try:
                convert_file(source, target)
            except Exception as exc:
                sys.stderr.write("skip %s: %s\n" % (source, exc))
                continue
            converted.append(target)
            print(target)
    if args.html and converted:
        write_gallery(converted, out / "index.html")
        print(out / "index.html")


def write_gallery(paths, target):
    items = []
    for path in paths:
        items.append("<figure><img src=\"%s\"><figcaption>%s</figcaption></figure>" % (html.escape(path.name), html.escape(path.name)))
    document = "<!doctype html><meta charset=\"utf-8\"><title>SC2 resources</title><style>body{background:#111;color:#ddd;font:14px sans-serif}figure{display:inline-block;margin:8px;text-align:center}img{max-width:96px;max-height:96px;image-rendering:pixelated}</style><h1>SC2 resources</h1>%s" % "\n".join(items)
    target.write_text(document, encoding="utf-8")


def paths_command(args):
    print("sc2:", find_sc2())
    print("stormex:", find_stormex())
    print("output:", DEFAULT_OUT)


def build_parser():
    parser = argparse.ArgumentParser(description="Search, filter, extract, preview, and browse SC2 CASC resources.")
    sub = parser.add_subparsers(dest="command", required=True)

    listing = sub.add_parser("list", help="List matching resource paths.")
    listing.add_argument("pattern", nargs="?", default="", help="Substring to search for.")
    listing.add_argument("--regex", help="Regex pattern instead of substring.")
    listing.add_argument("--ext", help="Comma-separated extensions, e.g. dds,tga.")
    listing.add_argument("--limit", type=int, default=0)
    listing.add_argument("--json", action="store_true")
    listing.set_defaults(func=list_command)

    extract = sub.add_parser("extract", help="Extract matching resources.")
    extract.add_argument("pattern")
    extract.add_argument("--out", default=None)
    extract.add_argument("--exact", action="store_true", help="Use only the basename of the path.")
    extract.set_defaults(func=extract_command)

    preview = sub.add_parser("preview", help="Extract and convert images to PNG.")
    preview.add_argument("pattern")
    preview.add_argument("--out", default=None)
    preview.add_argument("--ext", help="Comma-separated source extensions. Default dds,tga.")
    preview.add_argument("--limit", type=int, default=0)
    preview.add_argument("--html", action="store_true", help="Write index.html gallery.")
    preview.set_defaults(func=preview_command)

    paths = sub.add_parser("paths", help="Show detected storage, tool, and output paths.")
    paths.set_defaults(func=paths_command)
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
