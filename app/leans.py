"""leans.py — Pure helper for composing flavor-lever directions.

Intentionally free of NiceGUI imports so it can be unit-tested without
triggering the heavy module-level setup in main.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.epicure_service import EpicureService


def build_directions(
    svc: "EpicureService",
    model_key: str,
    cuisine: str,
    push: int,
    flavor: int,
) -> list[tuple[str, float]]:
    """Compose the active flavor levers into a weighted (pole_key, strength) list
    for EpicureService.pairings_directed.

    cuisine push 0-80; flavor bipolar -80..80
    (>0 sweet, <0 savory, 0 off).
    """
    dirs: list[tuple[str, float]] = []
    if push > 0 and cuisine:
        dirs.append((cuisine, float(push)))
    if flavor != 0:
        poles = svc.flavor_poles(model_key)
        key = poles.get("sweet") if flavor > 0 else poles.get("savory")
        if key:
            dirs.append((key, float(abs(flavor))))
    return dirs
