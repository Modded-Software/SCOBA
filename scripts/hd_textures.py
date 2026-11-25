"""The texture pipeline's command line: status, request, pick, default, package.

    uv run python scripts/hd_textures.py status --game sc2 --dataset stock --kind terrain
    uv run python scripts/hd_textures.py request --game sc2 --dataset scoba --layer out/SCOBA256.SC2Map --asset <asset> --chain upscale

Every command prints one JSON value. The commands are those of
hdtex/core/cli.py. This file only names the games that exist.
See docs/specifications/SPEC-HD-TEXTURES.md.
"""

from __future__ import annotations

from hdtex.core import cli, registry
from hdtex.sc2.game import GAME as SC2

# The games this tool knows: each registers itself when its module loads (hdtex.core.registry).
GAMES = (SC2,)
if not all(registry.GAMES.has(game.id) for game in GAMES):
    raise SystemExit("hd_textures: a game did not register")

if __name__ == "__main__":
    raise SystemExit(cli.run())
