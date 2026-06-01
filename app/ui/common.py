"""ui_common.py — tiny shared UI helpers used by both viz.py and components.py.

Kept dependency-free (no NiceGUI import) so it's a stable contract both Wave B
modules and the app orchestrator can rely on.
"""

from __future__ import annotations

# Ingredient food-group -> hue, for the category color dots (stable across views).
# Groups come from EpicureService.group_of(): one of
# beverage / dairy / fruit / grain / pantry / spice / vegetable / other.
GROUP_HUE: dict[str, float] = {
    "vegetable": 140,
    "fruit": 330,
    "spice": 35,
    "dairy": 50,
    "grain": 25,
    "beverage": 280,
    "pantry": 200,
    "other": 0,
}


def group_color(group: str, lightness: float = 55, chroma: float = 0.12) -> str:
    """An oklch() color string for a food-group, tunable in lightness/chroma."""
    hue = GROUP_HUE.get(group, 0)
    return f"oklch({lightness}% {chroma} {hue})"


def title_case(name: str) -> str:
    """'sesame_oil' -> 'Sesame Oil' for display."""
    return name.replace("_", " ").title()
