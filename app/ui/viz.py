"""viz.py — Orbit and List result views for the Epicure NiceGUI app.

Exposes two pure builder functions:
  render_list(container, svc, results, on_add, on_hover, compact=False)
  render_orbit(container, svc, results, in_play, on_add, on_hover)

Both clear the container then build NiceGUI elements inside it.
`results` is list[tuple[str, float]] ranked descending.
`in_play` is list[str] (current recipe ingredients).
Callbacks: on_add(name: str), on_hover(name_or_None).
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Any, Callable

from nicegui import ui

from app.ui.common import group_color, title_case

if TYPE_CHECKING:
    from app.services.epicure_service import EpicureService

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------
VW, VH = 680, 560
CX, CY = VW / 2, VH / 2
GA = math.pi * (3 - math.sqrt(5))  # golden angle


# ---------------------------------------------------------------------------
# render_list
# ---------------------------------------------------------------------------


def render_list(
    container: ui.element,
    svc: EpicureService,
    results: list[tuple[str, float]],
    on_add: Callable[[str], None],
    on_hover: Callable[[str | None], None],
    compact: bool = False,
) -> None:
    """Ranked rows: rank · dot · name · similarity bar · score · + button."""
    container.clear()
    with container:
        if not results:
            ui.label("No connections yet.").style(
                "color:var(--ink-soft); font-style:italic; padding:12px 4px; font-size:14px;"
            )
            return

        max_score = results[0][1] if results[0][1] else 1.0

        with ui.column().style(
            "display:flex; flex-direction:column; gap:2px; width:100%;"
        ):
            for i, (name, score) in enumerate(results):
                group = svc.group_of(name)
                dot_color = group_color(group)
                bar_color = group_color(group, 60, 0.13)
                bar_pct = (score / max_score) * 100 if max_score else 0

                with (
                    ui.row()
                    .style(
                        "display:flex; align-items:center; gap:9px; padding:7px 8px; "
                        "border-radius:8px; cursor:pointer; width:100%; box-sizing:border-box;"
                    )
                    .classes("suggestion-row") as row
                ):
                    # Hover highlight via JS events
                    row.on("mouseenter", lambda n=name: on_hover(n))
                    row.on("mouseleave", lambda: on_hover(None))
                    row.on("click", lambda n=name: on_add(n))
                    row._props["title"] = "Add to recipe"

                    # Rank number
                    ui.label(str(i + 1)).style(
                        "width:18px; text-align:right; font-size:11px; "
                        "color:var(--ink-soft); font-family:var(--mono);"
                    )

                    # Color dot
                    ui.element("span").style(
                        f"width:9px; height:9px; border-radius:50%; "
                        f"flex:0 0 auto; background:{dot_color}; display:inline-block;"
                    )

                    # Name
                    ui.label(title_case(name)).style(
                        "font-size:14px; font-weight:600; color:var(--ink); "
                        "width:116px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;"
                    )

                    # Similarity bar
                    with ui.element("span").style(
                        "flex:1; height:6px; background:var(--track); "
                        "border-radius:6px; overflow:hidden; min-width:30px;"
                    ):
                        ui.element("span").style(
                            f"display:block; height:100%; border-radius:6px; "
                            f"width:{bar_pct:.1f}%; background:{bar_color};"
                        )

                    # Score
                    ui.label(f"{score:.2f}").style(
                        "font-size:12px; font-family:var(--mono); "
                        "color:var(--ink-soft); width:32px; text-align:right;"
                    )

                    # + button (omit in compact mode)
                    if not compact:
                        add_btn = ui.button("+").style(
                            "border:1px solid var(--chip-line); background:var(--chip); "
                            "color:var(--accent); cursor:pointer; font-size:15px; font-weight:700; "
                            "width:22px; height:22px; border-radius:6px; padding:0; line-height:1; "
                            "display:grid; place-items:center; min-width:unset;"
                        )
                        add_btn.on("click.stop", lambda n=name: on_add(n))


# ---------------------------------------------------------------------------
# render_orbit
# ---------------------------------------------------------------------------


def _orbit_layout(
    results: list[tuple[str, float]],
    in_play: list[str],
) -> tuple[dict[str, dict[str, float]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Compute anchor positions, node positions, and edges in 680x560 space."""
    n = len(in_play)
    anchors: dict[str, dict[str, float]] = {}

    if n == 1:
        anchors[in_play[0]] = {"x": CX, "y": CY}
    elif n > 1:
        a_r = min(86, 34 + n * 6)
        for j, name in enumerate(in_play):
            a = (j / n) * math.pi * 2 - math.pi / 2
            anchors[name] = {
                "x": CX + a_r * math.cos(a),
                "y": CY + a_r * math.sin(a),
            }

    scores = [s for _, s in results]
    mn = min(scores) if scores else 0
    mx = max(scores) if scores else 1
    rng = mx - mn

    def norm(s: float) -> float:
        return 1.0 if rng < 1e-6 else (s - mn) / rng

    inner_r, outer_r = 118, 248
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for i, (name, score) in enumerate(results):
        ang = i * GA - math.pi / 2
        nv = norm(score)
        rad = inner_r + (1 - nv) * (outer_r - inner_r)
        x = CX + rad * math.cos(ang)
        y = CY + rad * math.sin(ang)
        nodes.append({"name": name, "score": score, "norm": nv, "x": x, "y": y})

        # Edge to nearest anchor(s) — connect to first 1-2 in-play anchors
        # (prototype uses EPI.why() partners; we approximate with all in_play[:2])
        for p in list(anchors.keys())[:2]:
            anc = anchors[p]
            edges.append(
                {
                    "x1": x,
                    "y1": y,
                    "x2": anc["x"],
                    "y2": anc["y"],
                    "from": name,
                }
            )

    return anchors, nodes, edges


def render_orbit(
    container: ui.element,
    svc: EpicureService,
    results: list[tuple[str, float]],
    in_play: list[str],
    on_add: Callable[[str], None],
    on_hover: Callable[[str | None], None],
) -> None:
    """Phyllotaxis orbit of suggestion nodes with in-play anchors and edge SVG underlay."""
    container.clear()
    with container:
        if not in_play:
            with ui.column().style(
                "display:flex; flex-direction:column; align-items:center; justify-content:center; "
                "gap:10px; height:100%; min-height:520px; color:var(--ink-soft); "
                "font-size:15px; text-align:center;"
            ):
                ui.label("◍").style("font-size:46px; opacity:0.35;")
                ui.label("Add an ingredient to see its connections.")
            return

        anchors, nodes, edges = _orbit_layout(results, in_play)

        # Outer wrapper: relative-positioned coordinate space at 680:560 aspect ratio
        # NOTE on edges: The SVG underlay uses the same 680x560 viewBox as the node
        # coordinate space. Node positions are converted to % of VW/VH for CSS left/top.
        # The SVG uses preserveAspectRatio="xMidYMid meet" and fills the container, so
        # when the container is not exactly 680x560 the SVG scales uniformly. Node
        # positions are pinned with CSS percentages computed from the same (x/VW, y/VH)
        # fractions, so they match the SVG's scaled coordinates only when the container
        # aspect ratio is exactly 680:560. At other aspect ratios there will be a small
        # misalignment between edge endpoints and node centres. This is an accepted
        # trade-off: correct placement on standard-width screens, approximate elsewhere.

        with ui.element("div").style(
            "position:relative; width:100%; aspect-ratio:680/560; min-height:520px; "
            "overflow:hidden;"
        ):
            # --- SVG edge underlay ---
            if edges:
                edge_lines = "".join(
                    f'<line x1="{e["x1"]:.1f}" y1="{e["y1"]:.1f}" '
                    f'x2="{e["x2"]:.1f}" y2="{e["y2"]:.1f}" '
                    f'stroke="var(--edge)" stroke-width="1.0" opacity="0.22" />'
                    for e in edges
                )
                ui.html(
                    f'<svg viewBox="0 0 {VW} {VH}" '
                    f'preserveAspectRatio="xMidYMid meet" '
                    f'style="position:absolute;inset:0;width:100%;height:100%;'
                    f'pointer-events:none;display:block;">'
                    f"{edge_lines}"
                    f"</svg>"
                )

            # --- Suggestion nodes ---
            for nd in nodes:
                name = nd["name"]
                score = nd["score"]
                nv = nd["norm"]
                group = svc.group_of(name)
                fill_color = group_color(group, 92, 0.05)
                stroke_color = group_color(group, 55, 0.13)
                dot_color = group_color(group, 58, 0.14)

                # Node radius: 6..13 px (mirroring prototype's 6 + norm*7)
                r = 6 + nv * 7

                # % position relative to VW/VH
                left_pct = nd["x"] / VW * 100
                top_pct = nd["y"] / VH * 100

                # Node wrapper — absolutely positioned, centered on (x,y)
                with (
                    ui.element("div")
                    .style(
                        f"position:absolute; "
                        f"left:{left_pct:.3f}%; top:{top_pct:.3f}%; "
                        f"transform:translate(-50%, -50%); "
                        f"display:flex; flex-direction:column; align-items:center; "
                        f"cursor:pointer; user-select:none; z-index:2;"
                    )
                    .classes("orbit-node") as node_el
                ):
                    node_el.on("click", lambda n=name: on_add(n))
                    node_el.on("mouseenter", lambda n=name: on_hover(n))
                    node_el.on("mouseleave", lambda: on_hover(None))
                    node_el._props["title"] = (
                        f"Click to add {title_case(name)} to your recipe"
                    )

                    # Disc + inner dot via SVG for crisp circles and hover ring
                    disc_size = int((r + 4 + 4) * 2 + 4)  # viewport px for the svg
                    cx_s = disc_size / 2
                    cy_s = disc_size / 2

                    disc_svg = (
                        f'<svg width="{disc_size}" height="{disc_size}" '
                        f'style="overflow:visible; display:block;" '
                        f'class="orbit-disc" data-name="{name}">'
                        # hover ring (hidden by default, shown via CSS/JS)
                        f'<circle class="hover-ring" cx="{cx_s}" cy="{cy_s}" r="{r + 7}" '
                        f'fill="none" stroke="var(--anchor-ring)" stroke-width="2" opacity="0" />'
                        # outer fill
                        f'<circle cx="{cx_s}" cy="{cy_s}" r="{r}" '
                        f'fill="{fill_color}" stroke="{stroke_color}" stroke-width="1.6" />'
                        # inner dot
                        f'<circle cx="{cx_s}" cy="{cy_s}" r="{max(2.5, r * 0.42):.1f}" '
                        f'fill="{dot_color}" />'
                        f"</svg>"
                    )
                    ui.html(disc_svg)

                    # Label below disc
                    ui.label(title_case(name)).style(
                        "font-size:11.5px; color:var(--ink); font-family:var(--sans); "
                        "font-weight:500; text-align:center; white-space:nowrap; "
                        "paint-order:stroke; margin-top:2px; pointer-events:none; "
                        "text-shadow:0 0 3px var(--panel), 0 0 3px var(--panel);"
                    ).classes("orbit-label")

                    # Score label + "+" affordance (revealed on hover via separate
                    # elements; NiceGUI lacks hover pseudo-state so we use JS toggle)
                    (
                        ui.label(f"{score:.2f}")
                        .style(
                            "font-size:10px; font-family:var(--mono); color:var(--ink-soft); "
                            "display:none; text-align:center; pointer-events:none;"
                        )
                        .classes("orbit-score")
                    )

                    add_badge = (
                        ui.button("+")
                        .style(
                            "position:absolute; top:-8px; right:-8px; "
                            "width:18px; height:18px; border-radius:50%; padding:0; "
                            "background:var(--accent); color:var(--accent-ink); "
                            "font-size:13px; font-weight:700; line-height:1; "
                            "display:none; border:none; cursor:pointer; "
                            "place-items:center; z-index:3;"
                        )
                        .classes("orbit-add-badge")
                    )
                    add_badge.on("click.stop", lambda n=name: on_add(n))

                # JS to toggle hover state: show score + ring + add badge
                ui.add_head_html("""
<style>
.orbit-node:hover .orbit-score { display:block !important; }
.orbit-node:hover .orbit-add-badge { display:grid !important; }
.orbit-node:hover .hover-ring { opacity:1 !important; }
.orbit-node:hover .orbit-disc circle:not(.hover-ring):first-of-type + circle { opacity:1; }
</style>
""") if False else None  # styles injected once below

            # --- In-play anchor nodes (drawn on top, non-interactive) ---
            for aname, pos in anchors.items():
                agroup = svc.group_of(aname)
                afill = group_color(agroup, 55, 0.14)
                astroke = group_color(agroup, 45, 0.16)
                left_pct = pos["x"] / VW * 100
                top_pct = pos["y"] / VH * 100

                with ui.element("div").style(
                    f"position:absolute; "
                    f"left:{left_pct:.3f}%; top:{top_pct:.3f}%; "
                    f"transform:translate(-50%, -50%); "
                    f"display:flex; flex-direction:column; align-items:center; "
                    f"pointer-events:none; z-index:5;"
                ):
                    anchor_svg = (
                        f'<svg width="52" height="52" style="overflow:visible;display:block;">'
                        f'<circle cx="26" cy="26" r="20" '
                        f'fill="{afill}" stroke="var(--anchor-ring)" stroke-width="3" />'
                        f'<circle cx="26" cy="26" r="20" '
                        f'fill="none" stroke="{astroke}" stroke-width="1.5" opacity="0.5" />'
                        f"</svg>"
                    )
                    ui.html(anchor_svg)
                    ui.label(title_case(aname)).style(
                        "font-size:13.5px; font-weight:800; color:var(--ink); "
                        "font-family:var(--sans); text-align:center; white-space:nowrap; "
                        "text-shadow:0 0 4px var(--panel), 0 0 4px var(--panel); "
                        "margin-top:4px; pointer-events:none;"
                    )

        # Inject hover styles once (idempotent — browser dedupes same <style> content)
        ui.add_head_html("""<style>
.orbit-node:hover .orbit-score { display:block !important; }
.orbit-node:hover .orbit-add-badge { display:grid !important; }
.orbit-node:hover .hover-ring { opacity:1 !important; }
</style>""")
