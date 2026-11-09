"""Replace the GUI trigger graph with one empty category.

The Galaxy bootstrap owns initialization, so editor-generated triggers are not
needed. The Root category keeps the file valid for the map editor.

Idempotent: the output is the same on every run.
Revert: rebuild from src/SCOBA.SC2Map, or restore Triggers from git.
"""

from __future__ import annotations

import argparse
from pathlib import Path

ROOT_ID = "82945EFA"
CONTENT = f"""<?xml version="1.0" encoding="utf-8"?>
<TriggerData>
    <Root>
        <Item Type="Category" Id="{ROOT_ID}"/>
    </Root>
    <Element Type="Category" Id="{ROOT_ID}">
    </Element>
</TriggerData>
"""


def strip_triggers(map_dir: Path) -> None:
    triggers = map_dir / "Triggers"
    if not triggers.is_file():
        return
    triggers.write_text(CONTENT, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("map_dir", type=Path, help="map folder or .SC2Map")
    args = parser.parse_args()
    strip_triggers(args.map_dir)
    print(f"stripped {args.map_dir / 'Triggers'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())