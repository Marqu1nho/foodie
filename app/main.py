"""main.py — Epicure Lab orchestrator (NiceGUI 3.x).

Single-page app in the warm "Mise" style. The user's ingredient basket IS the
recipe; suggestions recompute around it. This module owns all shared server-side
state and all re-rendering, wiring together the verified UI + service modules.

Translated from the design prototype's app.jsx (React) to NiceGUI server-side
state. One module-level state set is fine — this is a personal local single-user
tool.

Importing this module registers the page but does NOT launch the server.

Phase-one note: the prototype's full Tweaks panel (accent themes, density,
direction look-switcher beyond "warm") is DEFERRED. We keep only the
"Suggestions" k control (6-20) inline in the toolbar. Direction is fixed to the
warm "Mise" look.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from nicegui import ui

from app.models import Recipe
from app.services.epicure_service import EpicureService
from app.services.recipe_store import RecipeStore
from app.ui.theme import MISE_HEAD_HTML
from app.ui.viz import render_orbit, render_list
from app.leans import build_directions
from app.ui.components_input import (
    build_chip_input,
    build_paste_scratch,
    build_cuisine_lean,
    build_flavor_lean,
)
from app.ui.components_panels import (
    build_why_panel,
    build_compare,
    build_recipe_drawer,
)

# ---------------------------------------------------------------------------
# Services — instantiated ONCE at module load.
# ---------------------------------------------------------------------------
svc = EpicureService()
store = RecipeStore()

MODEL_BLURB: dict[str, str] = {
    "cooc": "what you cook it with",
    "core": "a blend of both",
    "chem": "what shares aroma compounds",
}
MODELS: list[str] = ["cooc", "core", "chem"]

_init_cuisines: list[str] = svc.cuisines("core")


# ---------------------------------------------------------------------------
# Shared server-side state (single-user local tool).
# ---------------------------------------------------------------------------
@dataclass
class AppState:
    """Typed in-memory state holder for the single-user app."""

    in_play: list[str] = field(default_factory=lambda: ["chicken", "lemon", "garlic"])
    model: str = "core"  # CORE is the neutral default per the handoff
    view: str = "orbit"  # orbit | list
    fan: str = "single"  # single | duo | trio
    cuisine: str = _init_cuisines[0] if _init_cuisines else ""
    push: int = 0  # int 0-80, treated as theta degrees
    flavor: int = 0  # bipolar -80..80: >0 sweet, <0 savory, 0 off
    k: int = 12  # suggestions count, 6-20
    hovered: str | None = None
    editing_id: int | None = None


S: AppState = AppState()


def _fan_models() -> list[str]:
    fan = S.fan
    if fan == "duo":
        return ["cooc", "chem"]
    if fan == "trio":
        return MODELS
    return [S.model]


def compute(m: str) -> list[tuple[str, float]]:
    """Mirror app.jsx compute(). GUARD: never call pairings on empty in_play."""
    if not S.in_play:
        return []
    dirs = build_directions(svc, m, S.cuisine, S.push, S.flavor)
    if dirs:
        return svc.pairings_directed(m, S.in_play, dirs, S.k)
    return svc.pairings(m, S.in_play, S.k)


# ---------------------------------------------------------------------------
# Static section builders (no reactive wiring — pure layout/labels).
# ---------------------------------------------------------------------------
def _build_header(open_drawer: Callable[[], None]) -> None:
    """Title block + the 'Recipes' drawer-open button."""
    with ui.element("div").style(
        "display:flex; align-items:center; gap:18px; flex-wrap:wrap;"
    ):
        with ui.element("div").style(
            "display:flex; align-items:baseline; gap:6px; flex-shrink:0;"
        ):
            ui.label("Epicure").style(
                "font-family:var(--display); font-size:26px; font-weight:700;"
                " color:var(--ink); letter-spacing:-.01em;"
            )
            ui.label("lab").style(
                "font-family:var(--mono); font-size:12px; color:var(--accent);"
                " text-transform:uppercase; letter-spacing:.12em;"
            )
        ui.label("find what pairs — by recipe habit or flavour chemistry").style(
            "font-size:13px; color:var(--ink-soft); font-style:italic; flex-shrink:1;"
        )
        with ui.element("div").style(
            "margin-left:auto; display:flex; align-items:center; gap:10px;"
        ):
            ui.button("Recipes", on_click=open_drawer).style(
                "border:1px solid var(--line); background:var(--field);"
                " color:var(--ink); padding:7px 14px; border-radius:9px;"
                " font-size:13px; font-weight:600; box-shadow:none;"
            ).props("flat no-caps")


def _build_recipe_intro() -> None:
    """The 'Your recipe — the base your suggestions build on' label row."""
    with ui.element("div").style(
        "display:flex; align-items:baseline; gap:8px; flex-wrap:wrap;"
    ):
        ui.label("Your recipe").style(
            "font-family:var(--display); font-size:16px; font-weight:700;"
            " color:var(--ink); white-space:nowrap; flex-shrink:0;"
        )
        ui.label("— the base your suggestions build on").style(
            "font-size:12.5px; color:var(--ink-soft); font-style:italic; white-space:nowrap;"
        )


def _build_footer_hint() -> None:
    """Canvas-card footer hint line."""
    with ui.element("div").style(
        "display:flex; align-items:center; gap:8px; flex-wrap:wrap;"
        " padding:10px 14px; border-top:1px solid var(--line);"
        " font-size:12px; color:var(--ink-soft);"
    ):
        ui.html(
            "<span><b style='color:var(--ink)'>Click</b> a suggestion to add it to your recipe — suggestions refine around it</span>"
        )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------
ui.add_head_html(MISE_HEAD_HTML, shared=True)


@ui.page("/")
def index() -> None:
    # forward declarations for handlers (filled below)
    chip_refresh: dict[str, Callable[[], None]] = {"fn": lambda: None}
    drawer: dict[str, Any] = {"open": lambda: None, "refresh": lambda: None}

    # ---- handlers ----
    def add(name: str) -> None:
        if name and name not in S.in_play:
            S.in_play.append(name)
        S.hovered = None
        chip_refresh["fn"]()
        canvas_view.refresh()
        top_connections.refresh()
        why_view.refresh()
        drawer["refresh"]()

    def add_many(names: list[str]) -> None:
        for n in names:
            if n not in S.in_play:
                S.in_play.append(n)
        chip_refresh["fn"]()
        canvas_view.refresh()
        top_connections.refresh()
        why_view.refresh()
        drawer["refresh"]()

    def remove(name: str) -> None:
        if name in S.in_play:
            S.in_play.remove(name)
        chip_refresh["fn"]()
        canvas_view.refresh()
        top_connections.refresh()
        why_view.refresh()
        drawer["refresh"]()

    def clear_all() -> None:
        S.in_play = []
        chip_refresh["fn"]()
        canvas_view.refresh()
        top_connections.refresh()
        why_view.refresh()
        drawer["refresh"]()

    def set_model(m: str) -> None:
        S.model = m
        valid = svc.cuisines(m)
        if S.cuisine not in valid:
            S.cuisine = valid[0] if valid else ""
        cuisine_view.refresh()
        canvas_view.refresh()
        top_connections.refresh()
        why_view.refresh()
        toolbar_view.refresh()

    def set_view(v: str) -> None:
        S.view = v
        canvas_view.refresh()
        top_connections.refresh()

    def set_fan(f: str) -> None:
        S.fan = f
        canvas_view.refresh()
        top_connections.refresh()
        why_view.refresh()
        toolbar_view.refresh()

    def set_cuisine(c: str) -> None:
        S.cuisine = c
        canvas_view.refresh()
        top_connections.refresh()

    def set_push(p: int) -> None:
        S.push = int(p)
        canvas_view.refresh()
        top_connections.refresh()

    def set_flavor(v: int) -> None:
        S.flavor = int(v)
        canvas_view.refresh()
        top_connections.refresh()

    def set_k(v: int) -> None:
        S.k = int(v)
        canvas_view.refresh()
        top_connections.refresh()

    def set_hovered(name: str | None) -> None:
        # keep cheap: only refresh the WHY panel
        S.hovered = name
        why_view.refresh()

    def load_recipe(r: Recipe) -> None:
        S.in_play = list(r.items)
        S.model = r.model or S.model
        S.editing_id = r.id
        S.hovered = None
        chip_refresh["fn"]()
        canvas_view.refresh()
        top_connections.refresh()
        why_view.refresh()
        toolbar_view.refresh()
        drawer["refresh"]()

    def get_drawer_state() -> dict[str, Any]:
        return {
            "in_play": S.in_play,
            "model": S.model,
            "editing_id": S.editing_id,
        }

    # ===================================================================
    # SHELL
    # ===================================================================
    with ui.element("div").style(
        "max-width:1240px; margin:0 auto; padding:18px 20px 40px;"
        " display:flex; flex-direction:column; gap:14px;"
        " font-family:var(--sans); color:var(--ink); font-size:15px;"
    ):
        # ---------------- header ----------------
        _build_header(lambda: drawer["open"]())

        # ---------------- recipe = the query ----------------
        _build_recipe_intro()

        # input bar: chip input + paste toggle + save
        paste_open: dict[str, bool] = {"v": False}

        with ui.element("div").style(
            "display:flex; align-items:center; gap:8px; flex-wrap:wrap;"
        ):
            chip_refresh["fn"] = build_chip_input(
                svc,
                lambda: S.in_play,
                add,
                remove,
                clear_all,
            )

            def _toggle_paste() -> None:
                paste_open["v"] = not paste_open["v"]
                paste_area.refresh()

            ui.button("Paste a list", on_click=_toggle_paste).style(
                "border:1px solid var(--line); background:var(--field);"
                " color:var(--ink); padding:10px 12px; border-radius:10px;"
                " font-size:13px; font-weight:600; box-shadow:none;"
            ).props("flat no-caps")

            ui.button("Save as recipe", on_click=lambda: drawer["open"]()).style(
                "border:none; background:var(--accent); color:#fff;"
                " padding:10px 14px; border-radius:10px; font-size:13px;"
                " font-weight:700; box-shadow:none;"
            ).props("no-caps text-color=white")

        @ui.refreshable
        def paste_area() -> None:
            if paste_open["v"]:

                def _close() -> None:
                    paste_open["v"] = False
                    paste_area.refresh()

                build_paste_scratch(svc, add_many, _close)

        paste_area()

        # ---------------- main two-column grid ----------------
        with ui.element("div").style(
            "display:grid; grid-template-columns:minmax(0,1fr) 340px; gap:14px;"
            " align-items:start;"
        ):
            # ===== canvas card =====
            with ui.element("div").style(
                "background:var(--panel); border:1px solid var(--line);"
                " border-radius:16px; overflow:hidden;"
                " box-shadow:0 1px 2px rgba(0,0,0,.04);"
            ):
                # ---- toolbar (refreshable: model selector depends on fan) ----
                @ui.refreshable
                def toolbar_view() -> None:
                    with ui.element("div").style(
                        "display:flex; align-items:center; gap:10px;"
                        " padding:12px 14px; border-bottom:1px solid var(--line);"
                        " flex-wrap:wrap;"
                    ):
                        # orbit/list toggle
                        ui.toggle(
                            {"orbit": "◉ Orbit", "list": "≣ List"},
                            value=S.view,
                            on_change=lambda e: set_view(e.value),
                        ).props("no-caps dense unelevated").style("font-size:12.5px;")

                        ui.element("div").style("flex:1; min-width:4px;")

                        # model selector OR compare note
                        if S.fan == "single":
                            with ui.element("div").style(
                                "display:flex; align-items:center; gap:8px;"
                            ):
                                ui.toggle(
                                    {m: m for m in MODELS},
                                    value=S.model,
                                    on_change=lambda e: set_model(e.value),
                                ).props("no-caps dense unelevated").style(
                                    "font-size:12.5px;"
                                )
                                ui.label(MODEL_BLURB[S.model]).style(
                                    "font-size:12px; color:var(--ink-soft); font-style:italic;"
                                )
                        else:
                            note = " · ".join(m.upper() for m in _fan_models())
                            ui.label(f"comparing {note}").style(
                                "font-size:12.5px; color:var(--ink-soft); font-family:var(--mono);"
                            )

                        ui.element("div").style("flex:1; min-width:4px;")

                        # k control (replaces the prototype Tweaks panel)
                        with ui.element("div").style(
                            "display:flex; align-items:center; gap:6px;"
                        ):
                            ui.label("Suggestions").style(
                                "font-size:11px; text-transform:uppercase;"
                                " letter-spacing:.06em; color:var(--ink-soft);"
                                " font-family:var(--mono);"
                            )
                            ui.slider(
                                min=6,
                                max=20,
                                step=1,
                                value=S.k,
                                on_change=lambda e: set_k(e.value),
                            ).props("dense").style(
                                "width:90px; accent-color:var(--accent);"
                            )
                            ui.label().bind_text_from(S, "k", lambda v: str(v)).style(
                                "font-family:var(--mono); font-size:12.5px;"
                                " color:var(--ink); width:20px; text-align:right;"
                            )

                        # single/2up/3up
                        ui.toggle(
                            {"single": "Single", "duo": "2-up", "trio": "3-up"},
                            value=S.fan,
                            on_change=lambda e: set_fan(e.value),
                        ).props("no-caps dense unelevated").style("font-size:12.5px;")

                toolbar_view()

                # ---- canvas body ----
                @ui.refreshable
                def canvas_view() -> None:
                    with ui.element("div").style(
                        "min-height:560px; padding:4px; display:flex;"
                    ) as body:
                        if S.fan != "single":
                            fan_models = _fan_models()
                            results_by_model = {m: compute(m) for m in fan_models}
                            build_compare(
                                body,
                                svc,
                                fan_models,
                                results_by_model,
                                S.in_play,
                                add,
                                set_hovered,
                            )
                        elif S.view == "list":
                            results = compute(S.model)
                            with ui.element("div").style(
                                "padding:14px; width:100%;"
                            ) as lw:
                                render_list(lw, svc, results, add, set_hovered)
                        else:
                            results = compute(S.model)
                            render_orbit(
                                body,
                                svc,
                                results,
                                S.in_play,
                                add,
                                set_hovered,
                            )

                canvas_view()

                # ---- footer hint ----
                _build_footer_hint()

            # ===== sidebar =====
            with ui.element("div").style(
                "display:flex; flex-direction:column; gap:12px;"
                " position:sticky; top:14px;"
            ):
                # cuisine-lean card
                @ui.refreshable
                def cuisine_view() -> None:
                    build_cuisine_lean(
                        svc,
                        lambda: S.cuisine,
                        set_cuisine,
                        lambda: S.push,
                        set_push,
                        get_cuisines=lambda: svc.cuisines(S.model),
                    )

                cuisine_view()

                # flavor-lean card
                build_flavor_lean(lambda: S.flavor, set_flavor)

                # WHY card
                with ui.element("div").style(
                    "background:var(--panel); border:1px solid var(--line);"
                    " border-radius:14px; padding:14px; height:230px; overflow:hidden;"
                ):
                    ui.label("Why this pairs").style(
                        "font-size:12px; text-transform:uppercase; letter-spacing:.06em;"
                        " color:var(--ink-soft); font-family:var(--mono); margin-bottom:10px;"
                    )
                    why_container = ui.element("div").style(
                        "height:180px; overflow-y:auto;"
                    )

                    @ui.refreshable
                    def why_view() -> None:
                        model_key = S.model if S.fan == "single" else "core"
                        build_why_panel(
                            why_container,
                            svc,
                            model_key,
                            S.hovered,
                            S.in_play,
                        )

                    why_view()

                # top-connections card (orbit + single only)
                @ui.refreshable
                def top_connections() -> None:
                    if S.view == "orbit" and S.fan == "single":
                        with ui.element("div").style(
                            "background:var(--panel); border:1px solid var(--line);"
                            " border-radius:14px; padding:14px;"
                        ):
                            ui.label("Top connections").style(
                                "font-size:12px; text-transform:uppercase;"
                                " letter-spacing:.06em; color:var(--ink-soft);"
                                " font-family:var(--mono); margin-bottom:10px;"
                            )
                            results = compute(S.model)[:8]
                            tc = ui.element("div")
                            render_list(
                                tc, svc, results, add, set_hovered, compact=False
                            )

                top_connections()

    # ---- recipe drawer (built last; needs handlers) ----
    drawer.update(
        build_recipe_drawer(
            svc,
            store,
            get_drawer_state,
            load_recipe,
            lambda: chip_refresh["fn"](),
        )
    )


# ---------------------------------------------------------------------------
# Entrypoint — registering the page above does NOT start the server.
# `make run-local` runs `uv run python -m app.main`.
# ---------------------------------------------------------------------------
if __name__ in {"__main__", "__mp_main__"}:
    ui.run(port=50000, title="Epicure", reload=True)
