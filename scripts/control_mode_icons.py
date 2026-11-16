#!/usr/bin/env python3
"""Control mode icons: stock game textures, one per mode.

Operator 2026-11-16: no generated icons. The icons were picked by
extracting candidates to PNG and comparing them side by side:
- WASD / Point & Click: the Stukov rally cursor arrow;
- Actions: the Ghost Snipe scope.
Both are green, like the HUD bars. The map script uses the same paths
(c_HUD_ICON_PNC / c_HUD_ICON_TPS in ui/hud_buttons.galaxy).
"""

from __future__ import annotations

ICONS = {
    "SCOBAControlPNC": r"Assets\Textures\btn-ac-zerg-stukov-beaconrally.dds",
    "SCOBAControlTPS": r"Assets\Textures\btn-ability-terran-snipe-color.dds",
}
