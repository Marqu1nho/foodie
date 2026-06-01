"""components_panels.py — WHY panel, COMPARE view, and RECIPE BOOK drawer.

Three NiceGUI 3.x builders:
  build_why_panel(container, svc, model_key, name, in_play) -> None
  build_compare(container, svc, fan_models, results_by_model, in_play, on_add, on_hover) -> None
  build_recipe_drawer(svc, store, get_state, on_load, refresh_after_change) -> dict
"""

from __future__ import annotations

from typing import Any, Callable

from nicegui import ui

from app.ui.common import group_color, title_case
from app.services.recipe_store import RecipeStore

# Model explanations (mirrors prototype MODEL_BLURB)
MODEL_BLURB: dict[str, str] = {
    "cooc": "what you cook it with",
    "core": "a blend of both",
    "chem": "what shares aroma compounds",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dot(group: str, size: int = 9) -> None:
    """Render a tiny colored circle for an ingredient group."""
    color = group_color(group)
    ui.element("span").style(
        f"display:inline-block;width:{size}px;height:{size}px;"
        f"border-radius:50%;background:{color};flex:0 0 auto;"
    )


# ---------------------------------------------------------------------------
# 1. WHY PANEL
# ---------------------------------------------------------------------------

def build_why_panel(
    container,
    svc,
    model_key: str,
    name: str | None,
    in_play: list[str],
) -> None:
    """Populate *container* with the Why-this-pairs explanation."""
    container.clear()
    with container:
        if not name or not in_play:
            ui.label("Hover a suggestion to see why it pairs.").style(
                "color:var(--ink-soft);font-style:italic;font-size:13.5px;line-height:1.5;"
            )
            return

        data = svc.why(model_key, name, in_play)
        bridges: list[str] = data.get("bridges", [])
        shared_modes: list[dict] = data.get("shared_modes", [])

        # Header: color dot + "Why {Title}?"
        with ui.row().style("display:flex;align-items:center;gap:7px;font-size:15px;color:var(--ink);"):
            group = svc.group_of(name)
            _dot(group)
            ui.html(f"Why <b>{title_case(name)}</b>?")

        # Bridges line
        if bridges:
            parts = " · ".join(title_case(b) for b in bridges[:3])
            ui.label(f"bridges  {parts}").style(
                "font-size:12.5px;color:var(--ink-soft);"
            )

        # Shared signals block
        if shared_modes:
            with ui.column().style("display:flex;flex-direction:column;gap:5px;"):
                ui.label("shared signals").style(
                    "font-size:11px;text-transform:uppercase;letter-spacing:.06em;"
                    "color:var(--ink-soft);font-family:var(--mono);"
                )
                with ui.row().style("display:flex;flex-wrap:wrap;gap:5px;"):
                    for mode in shared_modes:
                        kind = mode.get("kind", "")
                        label = mode.get("label", "")
                        # Kind-based styling: chem-like = accent tint; cooc = chip
                        if kind == "chem":
                            tag_style = (
                                "font-size:12px;padding:3px 8px;border-radius:6px;"
                                "font-weight:600;white-space:nowrap;"
                                "background:color-mix(in oklch,var(--accent) 16%,transparent);"
                                "color:var(--accent);"
                            )
                        else:
                            tag_style = (
                                "font-size:12px;padding:3px 8px;border-radius:6px;"
                                "font-weight:600;white-space:nowrap;"
                                "background:var(--chip);color:var(--chip-ink);"
                                "border:1px solid var(--chip-line);"
                            )
                        with ui.element("span").style(tag_style):
                            ui.label(label)
                        if kind:
                            ui.label(kind).style(
                                "font-size:10px;color:var(--ink-soft);align-self:center;"
                            )
        else:
            ui.label("A faint, exploratory link — little shared signal.").style(
                "font-size:12.5px;color:var(--ink-soft);font-style:italic;"
            )


# ---------------------------------------------------------------------------
# 2. COMPARE VIEW (2-up / 3-up fan grid)
# ---------------------------------------------------------------------------

def build_compare(
    container,
    svc,
    fan_models: list[str],
    results_by_model: dict[str, list],
    in_play: list[str],
    on_add: Callable,
    on_hover: Callable,
) -> None:
    """Populate *container* with a CSS grid: one column per model."""
    container.clear()
    n_cols = len(fan_models)
    with container:
        with ui.element("div").style(
            f"display:grid;grid-template-columns:repeat({n_cols},1fr);gap:0;width:100%;"
        ):
            for m in fan_models:
                with ui.element("div").style(
                    "padding:12px;border-right:1px solid var(--line);"
                ):
                    # Column header
                    with ui.element("div").style(
                        "display:flex;flex-direction:column;gap:1px;"
                        "margin-bottom:8px;padding-bottom:8px;"
                        "border-bottom:1px dashed var(--line);"
                    ):
                        ui.label(m.upper()).style(
                            "font-family:var(--mono);font-weight:800;font-size:14px;"
                            "color:var(--accent);letter-spacing:.04em;"
                        )
                        ui.label(MODEL_BLURB.get(m, "")).style(
                            "font-size:11.5px;color:var(--ink-soft);font-style:italic;"
                        )

                    # Body: delegate to viz.render_list (lazy import)
                    from app.ui.viz import render_list  # noqa: PLC0415
                    col_container = ui.element("div")
                    render_list(
                        col_container,
                        svc,
                        results_by_model.get(m, []),
                        on_add,
                        on_hover,
                        compact=True,
                    )


# ---------------------------------------------------------------------------
# 3. RECIPE BOOK DRAWER
# ---------------------------------------------------------------------------

def build_recipe_drawer(
    svc,
    store: RecipeStore,
    get_state: Callable[[], dict],
    on_load: Callable[[dict], None],
    refresh_after_change: Callable[[], None],
) -> dict:
    """Build a slide-over drawer.

    Returns {"open": callable, "refresh": callable}.
    """

    # ---- mutable state ----
    _open: list[bool] = [False]          # wrapped in list for closure mutation
    _collapsed: dict[str, bool] = {}      # group-key -> collapsed flag
    _form: dict[str, Any] = {
        "name": "",
        "group": "",
        "notes": "",
        "new_group": "",
        "adding_group": False,
    }

    # ---- root elements (created once) ----
    scrim_el: list[Any] = [None]
    panel_el: list[Any] = [None]

    def _do_open() -> None:
        _open[0] = True
        _refresh_inner()

    def _do_close() -> None:
        _open[0] = False
        _refresh_inner()

    @ui.refreshable
    def _drawer_content() -> None:
        state = get_state()
        in_play: list[str] = state.get("in_play", [])
        model_key: str = state.get("model", "core")
        editing_id = state.get("editing_id", None)

        all_recipes = store.list()
        all_groups = store.groups()
        editing_recipe = next((r for r in all_recipes if r.get("id") == editing_id), None)

        # ---- Pre-fill form when editing changes ----
        if editing_recipe and not _form["name"]:
            _form["name"] = editing_recipe.get("name", "")
            _form["group"] = editing_recipe.get("group", all_groups[0] if all_groups else "")
            _form["notes"] = editing_recipe.get("notes", "")

        # Resolved group
        resolved_group = (
            _form["new_group"].strip()
            if _form["adding_group"] and _form["new_group"].strip()
            else _form["group"] or (all_groups[0] if all_groups else "")
        )
        can_save = bool(_form["name"].strip() and in_play)

        # ---- Header ----
        with ui.row().style(
            "display:flex;justify-content:space-between;align-items:center;"
            "font-size:17px;font-weight:700;color:var(--ink);"
        ):
            ui.label("Recipe book")
            ui.button("×", on_click=_do_close).style(
                "border:none;background:none;color:var(--ink-soft);"
                "cursor:pointer;font-size:22px;line-height:1;box-shadow:none;"
            )

        # ---- Edit banner ----
        if editing_recipe:
            ui.html(
                f"&#9998; Tweaking <b>{editing_recipe['name']}</b> — "
                "change ingredients, then update or fork a new version."
            ).style(
                "font-size:12.5px;line-height:1.4;color:var(--accent);"
                "background:color-mix(in oklch,var(--accent) 12%,transparent);"
                "border-radius:9px;padding:9px 11px;"
            )

        # ---- Section: Your recipe / Editing recipe ----
        ui.label("Editing recipe" if editing_recipe else "Your recipe").style(
            "font-size:11px;text-transform:uppercase;letter-spacing:.07em;"
            "color:var(--ink-soft);font-family:var(--mono);margin-top:8px;"
        )

        # ---- Draft chips ----
        if not in_play:
            ui.label("Add ingredients, then save them as a recipe.").style(
                "font-size:13px;color:var(--ink-soft);font-style:italic;"
            )
        else:
            with ui.row().style("display:flex;flex-wrap:wrap;gap:6px;"):
                for n in in_play:
                    group = svc.group_of(n)
                    color = group_color(group)
                    with ui.element("span").style(
                        "display:inline-flex;align-items:center;gap:6px;"
                        "padding:5px 9px;background:var(--chip);color:var(--chip-ink);"
                        "border-radius:8px;font-size:13px;font-weight:600;"
                        "border:1px solid var(--chip-line);"
                    ):
                        ui.element("span").style(
                            f"display:inline-block;width:9px;height:9px;"
                            f"border-radius:50%;background:{color};flex:0 0 auto;"
                        )
                        ui.label(title_case(n))

        # ---- Save form (only when in_play non-empty) ----
        if in_play:
            with ui.column().style(
                "display:flex;flex-direction:column;gap:8px;"
                "padding-bottom:6px;border-bottom:1px solid var(--line);"
            ):
                # Name input
                name_inp = ui.input(placeholder="recipe name…", value=_form["name"]).style(
                    "border:1px solid var(--line);border-radius:8px;"
                    "background:var(--field);color:var(--ink);"
                    "padding:9px 11px;font-size:14px;outline:none;width:100%;"
                )
                name_inp.on("input", lambda e: _form.update({"name": e.args}))

                # Group label
                ui.label("Group").style(
                    "font-size:11.5px;font-weight:700;color:var(--ink);margin-top:2px;"
                )

                # Group chips
                with ui.row().style("display:flex;flex-wrap:wrap;gap:6px;"):
                    for g in all_groups:
                        active = (not _form["adding_group"]) and (resolved_group == g)
                        btn_style = (
                            "border:none;background:var(--accent);color:var(--accent-ink);"
                            if active else
                            "border:1px solid var(--line);background:var(--field);color:var(--ink-soft);"
                        )
                        def _make_group_click(grp: str):
                            def _click():
                                _form.update({"group": grp, "adding_group": False})
                                _drawer_content.refresh()
                            return _click
                        ui.button(g, on_click=_make_group_click(g)).style(
                            btn_style + "border-radius:20px;padding:5px 12px;"
                            "font-size:12.5px;font-weight:600;cursor:pointer;white-space:nowrap;"
                        )

                    # "+ New" chip
                    new_btn_style = (
                        "border:none;background:var(--accent);color:var(--accent-ink);"
                        if _form["adding_group"] else
                        "border:1px solid var(--line);background:var(--field);color:var(--ink-soft);"
                    )
                    def _toggle_new():
                        _form.update({"adding_group": not _form["adding_group"]})
                        _drawer_content.refresh()
                    ui.button("+ New", on_click=_toggle_new).style(
                        new_btn_style + "border-radius:20px;padding:5px 12px;"
                        "font-size:12.5px;font-weight:600;cursor:pointer;"
                    )

                if _form["adding_group"]:
                    ng_inp = ui.input(
                        placeholder="new group name…", value=_form["new_group"]
                    ).style(
                        "border:1px solid var(--line);border-radius:8px;"
                        "background:var(--field);color:var(--ink);"
                        "padding:9px 11px;font-size:14px;outline:none;width:100%;"
                    )
                    ng_inp.on("input", lambda e: _form.update({"new_group": e.args}))

                # Notes label
                with ui.row().style("display:flex;align-items:baseline;gap:4px;"):
                    ui.label("Notes").style(
                        "font-size:11.5px;font-weight:700;color:var(--ink);"
                    )
                    ui.label("optional — method, yeast, ABV target…").style(
                        "font-size:11.5px;font-weight:400;color:var(--ink-soft);font-style:italic;"
                    )

                notes_ta = ui.textarea(
                    placeholder="e.g. 1.5 lb honey / gal · 71B yeast · target 12% ABV · age 3 mo",
                    value=_form["notes"],
                ).style(
                    "border:1px solid var(--line);border-radius:8px;"
                    "background:var(--field);color:var(--ink);"
                    "padding:9px 11px;font-size:13px;outline:none;"
                    "min-height:54px;resize:vertical;"
                )
                notes_ta.on("input", lambda e: _form.update({"notes": e.args}))

                # Save / Update buttons
                def _do_save(as_new: bool = False) -> None:
                    if not can_save:
                        return
                    current_state = get_state()
                    payload: dict = {
                        "name": _form["name"].strip(),
                        "group": resolved_group,
                        "items": list(current_state.get("in_play", [])),
                        "model": current_state.get("model", "core"),
                        "notes": _form["notes"].strip(),
                    }
                    if editing_recipe and not as_new:
                        store.update(editing_recipe["id"], payload)
                    else:
                        store.save(payload)
                    _form.update({"name": "", "notes": "", "adding_group": False, "new_group": ""})
                    refresh_after_change()
                    _drawer_content.refresh()

                with ui.row().style("display:flex;gap:8px;margin-top:2px;"):
                    opacity = "1" if can_save else "0.4"
                    if editing_recipe:
                        ui.button(
                            f'Update "{editing_recipe["name"]}"',
                            on_click=lambda: _do_save(False),
                        ).style(
                            f"border:none;background:var(--accent);color:var(--accent-ink);"
                            f"border-radius:8px;padding:9px 14px;font-weight:700;"
                            f"cursor:pointer;font-size:13px;opacity:{opacity};"
                        )
                        ui.button(
                            "Save as new",
                            on_click=lambda: _do_save(True),
                        ).style(
                            "border:1px solid var(--line);background:var(--field);"
                            "color:var(--ink);border-radius:8px;padding:9px 14px;"
                            "font-weight:600;cursor:pointer;font-size:13px;white-space:nowrap;"
                        )
                    else:
                        ui.button(
                            f"Save to {resolved_group or '…'}",
                            on_click=lambda: _do_save(False),
                        ).style(
                            f"flex:1;border:none;background:var(--accent);"
                            f"color:var(--accent-ink);border-radius:8px;padding:9px 14px;"
                            f"font-weight:700;cursor:pointer;font-size:13px;opacity:{opacity};"
                        )

        # ---- Saved recipes ----
        n_saved = len(all_recipes)
        ui.label(f"Saved ({n_saved})").style(
            "font-size:11px;text-transform:uppercase;letter-spacing:.07em;"
            "color:var(--ink-soft);font-family:var(--mono);margin-top:8px;"
        )

        if not all_recipes:
            ui.label(
                "Nothing saved yet. Groups act like folders — "
                "in the real app they map to folders on disk."
            ).style("font-size:13px;color:var(--ink-soft);font-style:italic;")
        else:
            # Build group -> recipes mapping
            by_group: dict[str, list[dict]] = {}
            for r in all_recipes:
                g = r.get("group") or "Ungrouped"
                by_group.setdefault(g, []).append(r)

            group_order = [
                g for g in all_groups if g in by_group
            ] + [g for g in by_group if g not in all_groups]

            for g in group_order:
                recipes_in_group = by_group.get(g, [])
                is_open = not _collapsed.get(g, False)

                with ui.column().style("display:flex;flex-direction:column;gap:6px;"):
                    # Group header
                    def _make_toggle(grp: str):
                        def _toggle():
                            _collapsed[grp] = not _collapsed.get(grp, False)
                            _drawer_content.refresh()
                        return _toggle

                    with ui.row().style(
                        "display:flex;align-items:center;gap:8px;cursor:pointer;"
                        "color:var(--ink);font-size:13.5px;font-weight:700;padding:4px 0;"
                    ).on("click", _make_toggle(g)):
                        ui.label("▾" if is_open else "▸").style(
                            "font-size:10px;color:var(--ink-soft);width:10px;"
                        )
                        ui.label(g)
                        ui.label(str(len(recipes_in_group))).style(
                            "font-size:11px;font-family:var(--mono);"
                            "color:var(--ink-soft);background:var(--field);"
                            "border-radius:10px;padding:0 7px;"
                        )

                    if is_open:
                        for r in recipes_in_group:
                            r_id = r.get("id")
                            is_editing_this = r_id == editing_id
                            item_style = (
                                "border:1px solid var(--accent);"
                                "box-shadow:0 0 0 1px var(--accent);"
                                if is_editing_this else
                                "border:1px solid var(--line);"
                            )
                            with ui.column().style(
                                item_style +
                                "border-radius:10px;padding:11px;"
                                "background:var(--field);"
                                "display:flex;flex-direction:column;gap:7px;"
                            ):
                                # Top row: name + model badge
                                with ui.row().style(
                                    "display:flex;align-items:center;gap:7px;"
                                ):
                                    ui.label(r.get("name", "")).style(
                                        "flex:1;font-weight:700;color:var(--ink);"
                                    )
                                    ui.label(r.get("model", "").upper()).style(
                                        "font-size:10px;font-family:var(--mono);"
                                        "color:var(--ink-soft);"
                                        "border:1px solid var(--line);"
                                        "padding:1px 5px;border-radius:5px;"
                                    )

                                # Ingredient chips
                                items: list[str] = r.get("items", [])
                                if items:
                                    with ui.row().style(
                                        "display:flex;flex-wrap:wrap;gap:4px;"
                                    ):
                                        for n in items:
                                            ing_group = svc.group_of(n)
                                            dot_color = group_color(ing_group)
                                            with ui.element("span").style(
                                                "display:inline-flex;align-items:center;"
                                                "gap:5px;font-size:11.5px;padding:2px 7px;"
                                                "background:var(--chip);color:var(--chip-ink);"
                                                "border-radius:6px;"
                                            ):
                                                ui.element("span").style(
                                                    f"display:inline-block;width:7px;height:7px;"
                                                    f"border-radius:50%;background:{dot_color};"
                                                    f"flex:0 0 auto;"
                                                )
                                                ui.label(title_case(n))

                                # Notes
                                notes_text = r.get("notes", "")
                                if notes_text:
                                    ui.label(notes_text).style(
                                        "font-size:12px;color:var(--ink-soft);"
                                        "line-height:1.4;font-style:italic;"
                                        "border-left:2px solid var(--line);padding-left:8px;"
                                    )

                                # Action buttons
                                def _make_load(recipe: dict):
                                    def _load():
                                        on_load(recipe)
                                        refresh_after_change()
                                        _do_close()
                                    return _load

                                def _make_duplicate(recipe: dict):
                                    def _dup():
                                        copy = {k: v for k, v in recipe.items() if k != "id"}
                                        copy["name"] = recipe.get("name", "") + " copy"
                                        store.save(copy)
                                        refresh_after_change()
                                        _drawer_content.refresh()
                                    return _dup

                                def _make_delete(rid):
                                    def _del():
                                        store.delete(rid)
                                        refresh_after_change()
                                        _drawer_content.refresh()
                                    return _del

                                with ui.row().style(
                                    "display:flex;align-items:center;gap:8px;margin-top:1px;"
                                ):
                                    ui.button(
                                        "Load & tweak", on_click=_make_load(r)
                                    ).style(
                                        "border:none;background:var(--accent);"
                                        "color:var(--accent-ink);border-radius:6px;"
                                        "padding:5px 11px;cursor:pointer;"
                                        "font-size:12px;font-weight:700;"
                                    )
                                    ui.button(
                                        "Duplicate", on_click=_make_duplicate(r)
                                    ).style(
                                        "border:1px solid var(--line);"
                                        "background:var(--field);color:var(--ink);"
                                        "border-radius:6px;padding:5px 10px;"
                                        "cursor:pointer;font-size:12px;font-weight:600;"
                                    )
                                    ui.button(
                                        "Delete", on_click=_make_delete(r_id)
                                    ).style(
                                        "border:none;background:none;"
                                        "color:var(--ink-soft);cursor:pointer;"
                                        "font-size:12px;text-decoration:underline;"
                                        "margin-left:auto;"
                                    )

    def _refresh_inner() -> None:
        """Toggle visibility and re-render drawer content."""
        if scrim_el[0] is not None:
            is_visible = _open[0]
            scrim_el[0].style(
                f"opacity:{'1' if is_visible else '0'};"
                f"pointer-events:{'auto' if is_visible else 'none'};"
            )
            panel_el[0].style(
                f"transform:{'translateX(0)' if is_visible else 'translateX(20px)'};"
            )
        _drawer_content.refresh()

    # ---- Build the DOM structure once at call-time ----
    scrim = ui.element("div").style(
        "position:fixed;inset:0;z-index:50;"
        "background:rgba(0,0,0,.35);"
        "transition:opacity .25s;"
        "display:flex;justify-content:flex-end;"
        "opacity:0;pointer-events:none;"
    )
    scrim_el[0] = scrim

    with scrim.on("click", _do_close):
        pass

    with scrim:
        panel = ui.element("div").style(
            "width:432px;max-width:92vw;height:100%;"
            "background:var(--panel);border-left:1px solid var(--line);"
            "padding:18px;overflow-y:auto;"
            "transform:translateX(20px);transition:transform .25s;"
            "display:flex;flex-direction:column;gap:10px;"
        )
        panel_el[0] = panel

        # Stop click propagation so scrim click doesn't close when clicking panel
        panel.on("click.stop", lambda: None)

        with panel:
            _drawer_content()

    return {
        "open": _do_open,
        "refresh": _drawer_content.refresh,
    }
