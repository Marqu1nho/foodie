"""
ui_components.py — reusable NiceGUI UI pieces for the Epicure food-pairing explorer.
Depends on EpicureService but never imports or instantiates it here — it is injected.
"""

from __future__ import annotations

from typing import Callable

from nicegui import ui

from epicure_service import EpicureService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def render_results(container: ui.element, results: list[tuple[str, float]]) -> None:
    """Clear container and populate it with a ranked result list using ui.table."""
    container.clear()
    with container:
        if not results:
            ui.label("No results.").classes("text-gray-400 italic")
            return
        columns = [
            {"name": "rank", "label": "#", "field": "rank", "align": "left"},
            {"name": "ingredient", "label": "Ingredient", "field": "ingredient", "align": "left"},
            {"name": "score", "label": "Score", "field": "score", "align": "right"},
        ]
        rows = [
            {"rank": i, "ingredient": name.replace("_", " "), "score": f"{score:.3f}"}
            for i, (name, score) in enumerate(results, 1)
        ]
        ui.table(columns=columns, rows=rows, row_key="rank").classes("w-full")


def _model_selector(default: str = "cooc") -> ui.select:
    return ui.select(
        options=["cooc", "core", "chem"],
        value=default,
        label="Model",
    ).classes("w-32")


def _ingredient_select(vocab: list[str], label: str = "Ingredient", multiple: bool = False) -> ui.select:
    return ui.select(
        options=vocab,
        with_input=True,
        multiple=multiple,
        label=label,
    ).classes("w-72" if not multiple else "w-96")


# ---------------------------------------------------------------------------
# Tab: Explore
# ---------------------------------------------------------------------------

def build_explore_tab(svc: EpicureService, vocab: list[str]) -> None:
    """Single ingredient + model -> neighbors."""
    with ui.card().classes("w-full gap-2"):
        ui.label("Find ingredients most similar to a single item.").classes("text-gray-500 text-sm")
        with ui.row().classes("items-end gap-4 flex-wrap"):
            ingredient = _ingredient_select(vocab, "Ingredient")
            model_sel = _model_selector("cooc")
            k_input = ui.number(label="Top-k", value=15, min=1, max=50, step=1).classes("w-24")
            btn = ui.button("Search", icon="search")

        results_box = ui.element("div").classes("mt-2 w-full")

        def run_query():
            name = ingredient.value
            if not name:
                ui.notify("Please select an ingredient.", type="warning")
                return
            try:
                res = svc.neighbors(model_sel.value, name, k=int(k_input.value))
                render_results(results_box, res)
            except Exception as e:
                ui.notify(str(e), type="negative")

        btn.on_click(run_query)


# ---------------------------------------------------------------------------
# Tab: Leftovers
# ---------------------------------------------------------------------------

def build_leftovers_tab(svc: EpicureService, vocab: list[str]) -> None:
    """Multi-ingredient chip-flow -> pairings."""
    selected: list[str] = []

    with ui.card().classes("w-full gap-2"):
        ui.label("Select what you have on hand; get the best pairing suggestions.").classes("text-gray-500 text-sm")

        with ui.row().classes("items-end gap-4 flex-wrap"):
            add_select = ui.select(
                options=vocab,
                with_input=True,
                label="Add ingredient",
            ).classes("w-72")
            model_sel = _model_selector("cooc")
            k_input = ui.number(label="Top-k", value=15, min=1, max=50, step=1).classes("w-24")
            btn = ui.button("Find Pairings", icon="kitchen")

        chips_container = ui.row().classes("flex-wrap gap-2 mt-1")

        def refresh_chips() -> None:
            chips_container.clear()
            with chips_container:
                if not selected:
                    ui.label("No ingredients added yet.").classes("text-gray-400 italic text-sm")
                    return
                for name in list(selected):
                    chip = ui.chip(name.replace("_", " "), removable=True).classes("bg-indigo-100")
                    chip.on("remove", lambda e, n=name: remove_ingredient(n))

        def remove_ingredient(name: str) -> None:
            if name in selected:
                selected.remove(name)
            refresh_chips()

        def on_add(e) -> None:
            value = e.args
            if not value:
                return
            if value not in selected:
                selected.append(value)
            refresh_chips()
            add_select.set_value(None)

        add_select.on("update:model-value", on_add)

        refresh_chips()

        results_box = ui.element("div").classes("mt-2 w-full")

        def run_query():
            if not selected:
                ui.notify("Please add at least one ingredient.", type="warning")
                return
            try:
                res = svc.pairings(model_sel.value, list(selected), k=int(k_input.value))
                render_results(results_box, res)
            except Exception as e:
                ui.notify(str(e), type="negative")

        btn.on_click(run_query)


# ---------------------------------------------------------------------------
# Tab: Compare
# ---------------------------------------------------------------------------

def build_compare_tab(svc: EpicureService, vocab: list[str]) -> None:
    """One ingredient -> three side-by-side columns (cooc | core | chem)."""
    with ui.card().classes("w-full gap-2"):
        ui.label("Compare how three different models view the same ingredient.").classes("text-gray-500 text-sm")
        with ui.row().classes("items-end gap-4 flex-wrap"):
            ingredient = _ingredient_select(vocab, "Ingredient")
            k_input = ui.number(label="Top-k", value=15, min=1, max=50, step=1).classes("w-24")
            btn = ui.button("Compare", icon="compare")

        # Three fixed columns
        with ui.grid(columns=3).classes("w-full gap-2 mt-2"):
            col_cooc = ui.element("div").classes("border rounded p-2 min-h-[200px]")
            col_core = ui.element("div").classes("border rounded p-2 min-h-[200px]")
            col_chem = ui.element("div").classes("border rounded p-2 min-h-[200px]")

        cols = {"cooc": col_cooc, "core": col_core, "chem": col_chem}

        def run_query():
            name = ingredient.value
            if not name:
                ui.notify("Please select an ingredient.", type="warning")
                return
            try:
                results = svc.compare(name, k=int(k_input.value))
                for key, col in cols.items():
                    col.clear()
                    with col:
                        ui.label(key.upper()).classes("font-bold text-center text-indigo-700 mb-1 block")
                        inner = ui.element("div").classes("w-full")
                    render_results(inner, results[key])
            except Exception as e:
                ui.notify(str(e), type="negative")

        btn.on_click(run_query)


# ---------------------------------------------------------------------------
# Tab: Mead (slerp toward a cuisine)
# ---------------------------------------------------------------------------

def build_mead_tab(svc: EpicureService, vocab: list[str]) -> None:
    """Ingredient + cuisine pole + theta -> slerp results. Default model = chem."""
    cuisines = svc.cuisines()
    cuisine_labels = [c.replace("cuisine:", "").replace("_", " ") for c in cuisines]
    cuisine_map = dict(zip(cuisine_labels, cuisines))  # display label -> full key

    with ui.card().classes("w-full gap-2"):
        ui.label(
            "Rotate an ingredient toward a cuisine using spherical interpolation (SLERP). "
            "θ=0° returns the ingredient's own neighbors; higher angles push toward the cuisine pole."
        ).classes("text-gray-500 text-sm")

        with ui.row().classes("items-end gap-4 flex-wrap"):
            ingredient = _ingredient_select(vocab, "Seed Ingredient")
            model_sel = _model_selector("chem")
            cuisine_sel = ui.select(
                options=cuisine_labels,
                value=cuisine_labels[0] if cuisine_labels else None,
                label="Cuisine",
            ).classes("w-48")
            k_input = ui.number(label="Top-k", value=15, min=1, max=50, step=1).classes("w-24")

        with ui.row().classes("items-center gap-4 mt-2 flex-wrap"):
            ui.label("θ (degrees):").classes("text-sm")
            theta_slider = ui.slider(min=0, max=90, value=30, step=1).classes("w-64")
            theta_display = ui.label("30°").classes("w-10 text-sm font-mono")
            theta_slider.on("update:model-value", lambda e: theta_display.set_text(f"{int(e.args)}°"))
            btn = ui.button("Explore", icon="explore")

        results_box = ui.element("div").classes("mt-2 w-full")

        def run_query():
            name = ingredient.value
            if not name:
                ui.notify("Please select a seed ingredient.", type="warning")
                return
            cuisine_label = cuisine_sel.value
            if not cuisine_label:
                ui.notify("Please select a cuisine.", type="warning")
                return
            cuisine_key = cuisine_map.get(cuisine_label, cuisine_label)
            try:
                res = svc.slerp_cuisine(
                    model_key=model_sel.value,
                    seed=name,
                    cuisine_key=cuisine_key,
                    theta_deg=float(theta_slider.value),
                    k=int(k_input.value),
                )
                render_results(results_box, res)
            except Exception as e:
                ui.notify(str(e), type="negative")

        btn.on_click(run_query)
