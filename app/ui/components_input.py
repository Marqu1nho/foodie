"""components_input.py — INPUT controls for the Epicure NiceGUI app (NiceGUI 3.x).

Exposes three builder functions:
  build_chip_input(svc, get_in_play, on_add, on_remove, on_clear) -> refresh callable
  build_paste_scratch(svc, on_add_many, on_close)
  build_cuisine_lean(svc, get_cuisine, set_cuisine, get_push, set_push)
  build_flavor_lean(get_value, set_value)
  build_protein_toggle(get_value, set_value)
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Callable

from nicegui import ui

from app.ui.common import group_color, title_case

if TYPE_CHECKING:
    from app.services.epicure_service import EpicureService


# ---------------------------------------------------------------------------
# 1. ChipInput
# ---------------------------------------------------------------------------


def build_chip_input(
    svc: EpicureService,
    get_in_play: Callable[[], list[str]],
    on_add: Callable[[str], None],
    on_remove: Callable[[str], None],
    on_clear: Callable[[], None],
) -> Callable[[], None]:
    """Build the type-ahead chip input.

    Returns a `refresh` callable so the orchestrator can re-sync chips after
    external state changes (e.g. loading a saved recipe).

    NiceGUI-specific decisions
    --------------------------
    * The text <input> is rendered once via `ui.input` and never recreated —
      only the chip row and dropdown are refreshable, preserving focus while
      typing.
    * Comma / semicolon detection: we watch the input's `value` via
      `on('update:modelValue', ...)` for the presence of a delimiter character
      rather than relying on keydown alone.  On every value change we strip any
      trailing comma/semicolon, run svc.resolve(), and commit if a match is
      found.  This fires server-side but does not recreate the <input> element.
    * Enter / Backspace / Escape are handled via `.on('keydown', ...)` with a
      JS handler that sends the key name to the server through a `run_javascript`
      -> `element.emit` path.  We use a lightweight JS snippet attached to the
      input element via `on('keydown', ...)` which emits a custom event carrying
      the key string back to Python.
    * The dropdown is an @ui.refreshable region positioned absolutely below the
      chip box.  Clicking a dropdown item calls `commit()` then refreshes.
    * highlighted_index is tracked as a Python-side list[int] (mutable scalar
      wrapper) so the refreshable dropdown can read it.
    """

    # --- mutable local state (not NiceGUI reactive; updated in callbacks) ---
    state: dict[str, Any] = {
        "hi": 0,  # highlighted suggestion index
        "open": False,  # dropdown visible
    }
    input_ref: list[ui.input] = []  # filled once after creation

    def _suggestions(q: str) -> list[str]:
        if not q.strip():
            return []
        already = set(get_in_play())
        return [n for n in svc.search(q.strip(), limit=8) if n not in already]

    def commit(name: str) -> None:
        if not name:
            return
        on_add(name)
        if input_ref:
            input_ref[0].set_value("")
        state["open"] = False
        state["hi"] = 0
        chips_area.refresh()
        dropdown_area.refresh()

    # --- outer container (relative positioning anchor) ---
    with ui.element("div").style(
        "position:relative; flex:1; min-width:280px;"
    ) as container:
        # ---- static bordered field (chips + inline input share one row) ----
        with ui.element("div").style(
            "display:flex; flex-wrap:wrap; gap:6px; align-items:center;"
            " padding:8px;"
            " background:var(--field); border:1px solid var(--line); border-radius:12px;"
            " min-height:46px; cursor:text;"
        ):
            # ---- chips area (refreshable — only chips + optional clear button) ----
            @ui.refreshable
            def chips_area():
                in_play = get_in_play()
                # chips
                for n in in_play:
                    color = group_color(svc.group_of(n))
                    with ui.element("span").style(
                        "display:inline-flex; align-items:center; gap:6px;"
                        " padding:5px 8px 5px 10px;"
                        " background:var(--chip); color:var(--chip-ink);"
                        " border-radius:8px; font-size:14px; font-weight:600;"
                        " border:1px solid var(--chip-line);"
                    ):
                        # colored dot
                        ui.element("span").style(
                            f"width:9px; height:9px; border-radius:9px;"
                            f" flex:0 0 auto; display:inline-block;"
                            f" background:{color};"
                        )
                        ui.label(title_case(n))

                        # × remove button — capture n in closure
                        def _make_remove(name):
                            def _remove():
                                on_remove(name)
                                chips_area.refresh()
                                dropdown_area.refresh()

                            return _remove

                        ui.button("×", on_click=_make_remove(n)).style(
                            "border:none; background:none; color:var(--ink-soft);"
                            " cursor:pointer; font-size:16px; line-height:1;"
                            " padding:0; margin-left:2px; min-width:unset;"
                        ).props("flat dense")

            chips_area()

            # ---- persistent text input (inside the field, after chips) ----
            inp = (
                ui.input(placeholder="type an ingredient, press Enter…")
                .style(
                    "flex:1; min-width:140px; border:none; outline:none;"
                    " background:transparent; color:var(--ink); font-size:15px;"
                    " padding:4px 2px;"
                )
                .props("borderless dense hide-bottom-space")
            )
            input_ref.append(inp)

            # ---- clear-all button (after input, no auto-margin so it stays inline) ----
            @ui.refreshable
            def clear_area():
                in_play = get_in_play()
                if len(in_play) > 1:

                    def _clear():
                        on_clear()
                        if input_ref:
                            input_ref[0].set_value("")
                        state["open"] = False
                        chips_area.refresh()
                        clear_area.refresh()
                        dropdown_area.refresh()

                    ui.button("clear", on_click=_clear).style(
                        "margin-left:4px; border:none; background:none;"
                        " color:var(--ink-soft); cursor:pointer; font-size:12px;"
                        " text-decoration:underline; min-width:unset;"
                    ).props("flat dense")

            clear_area()

        # watch value changes for comma/semicolon delimiter
        def _on_value_change(e: Any) -> None:
            val: str = e.value or ""
            # detect delimiter
            if val and val[-1] in (",", ";"):
                token = val[:-1].strip()
                if token:
                    resolved = svc.resolve(token)
                    if resolved:
                        commit(resolved)
                        return
                # just strip the delimiter even if not resolved
                inp.set_value(val[:-1].strip())
                return
            # refresh suggestions
            state["hi"] = 0
            state["open"] = bool(val.strip())
            dropdown_area.refresh()
            # update placeholder in chips area (minor: skip refresh for perf)

        inp.on_value_change(_on_value_change)

        # keydown: Enter, Backspace, Escape, ArrowDown, ArrowUp
        def _on_keydown(e: Any) -> None:
            key = (e.args or {}).get("key", "")
            q = (inp.value or "").strip()
            sugg = _suggestions(q)
            if key == "Enter":
                if sugg:
                    name = sugg[state["hi"]] if state["hi"] < len(sugg) else sugg[0]
                    commit(name)
                else:
                    resolved = svc.resolve(q)
                    if resolved:
                        commit(resolved)
            elif key == "ArrowDown":
                state["hi"] = min(state["hi"] + 1, len(sugg) - 1)
                state["open"] = True
                dropdown_area.refresh()
            elif key == "ArrowUp":
                state["hi"] = max(state["hi"] - 1, 0)
                dropdown_area.refresh()
            elif key == "Backspace" and not q:
                in_play = get_in_play()
                if in_play:
                    on_remove(in_play[-1])
                    chips_area.refresh()
                    dropdown_area.refresh()
            elif key == "Escape":
                state["open"] = False
                dropdown_area.refresh()

        # Explicitly request the `key` field so NiceGUI serialises it into e.args
        # (a bare .on("keydown") would deliver an empty payload).
        inp.on("keydown", _on_keydown, args=["key"])

        # ---- dropdown (absolutely positioned below chip box) ----
        @ui.refreshable
        def dropdown_area():
            q = (inp.value or "").strip()
            sugg = _suggestions(q) if state["open"] else []
            if not sugg:
                return
            with ui.element("div").style(
                "position:absolute; top:calc(100% + 6px); left:0; right:0; z-index:30;"
                " background:var(--panel); border:1px solid var(--line); border-radius:12px;"
                " overflow:hidden; box-shadow:0 18px 50px -16px rgba(0,0,0,.35);"
            ):
                for i, n in enumerate(sugg):
                    color = group_color(svc.group_of(n))
                    is_hi = i == state["hi"]
                    row_bg = "background:var(--hover);" if is_hi else ""

                    def _make_commit(name):
                        def _do():
                            commit(name)

                        return _do

                    with (
                        ui.element("div")
                        .style(
                            f"display:flex; align-items:center; gap:9px; padding:9px 12px;"
                            f" cursor:pointer; font-size:14px; {row_bg}"
                        )
                        .on("click", _make_commit(n))
                    ):
                        ui.element("span").style(
                            f"width:9px; height:9px; border-radius:9px;"
                            f" flex:0 0 auto; display:inline-block; background:{color};"
                        )
                        ui.label(title_case(n))
                        ui.label(svc.group_of(n)).style(
                            "margin-left:auto; font-size:11px; color:var(--ink-soft);"
                        )

        dropdown_area()

    def refresh() -> None:
        """Re-sync the chips region after external state changes."""
        chips_area.refresh()
        clear_area.refresh()
        dropdown_area.refresh()

    return refresh


# ---------------------------------------------------------------------------
# 2. PasteScratch
# ---------------------------------------------------------------------------


def build_paste_scratch(
    svc: EpicureService,
    on_add_many: Callable[[list[str]], None],
    on_close: Callable[[], None],
) -> None:
    """Build the paste-a-list panel inline at the current NiceGUI context."""

    # mutable parsed state
    parsed: dict[str, list[str]] = {"out": [], "miss": []}

    def _parse(text: str) -> tuple[list[str], list[str]]:
        tokens = re.split(r"[\n,;]+", text)
        out: list[str] = []
        miss: list[str] = []
        seen: set[str] = set()
        for tok in tokens:
            tok = tok.strip()
            if not tok:
                continue
            resolved = svc.resolve(tok)
            if resolved and resolved not in seen:
                out.append(resolved)
                seen.add(resolved)
            elif not resolved:
                miss.append(tok)
        return out, miss

    with ui.element("div").style(
        "background:var(--panel); border:1px solid var(--line); border-radius:12px;"
        " padding:12px; margin-top:8px;"
    ):
        # header row
        with ui.row().style(
            "justify-content:space-between; align-items:center;"
            " font-size:13px; color:var(--ink-soft); margin-bottom:8px;"
        ):
            ui.label("Paste a list — one per line, or comma-separated")
            ui.button("×", on_click=on_close).style(
                "border:none; background:none; color:var(--ink-soft);"
                " cursor:pointer; font-size:18px; line-height:1; min-width:unset;"
            ).props("flat dense")

        # textarea
        ta = (
            ui.textarea(placeholder="e.g.\nchicken, rice, garlic\nlemon\nspinach")
            .style(
                "width:100%; min-height:96px; resize:vertical;"
                " border:1px solid var(--line); border-radius:10px;"
                " background:var(--field); color:var(--ink);"
                " padding:10px; font-size:14px; outline:none;"
            )
            .props("borderless autofocus")
        )

        # footer: count, unknowns, Add button
        @ui.refreshable
        def footer_area():
            out = parsed["out"]
            miss = parsed["miss"]
            with ui.row().style(
                "align-items:center; gap:12px; margin-top:8px; flex-wrap:wrap;"
            ):
                ui.label(
                    f"{len(out)} matched" + (f" · {len(miss)} unknown" if miss else "")
                ).style("font-size:12px; color:var(--ink); font-weight:600;")
                if miss:
                    preview = ", ".join(miss[:4]) + ("…" if len(miss) > 4 else "")
                    ui.label(f"skipping: {preview}").style(
                        "font-size:12px; color:var(--ink-soft); font-style:italic;"
                    )

                def _add():
                    if out:
                        on_add_many(list(out))
                        on_close()

                ui.button(f"Add {len(out)}", on_click=_add).style(
                    "margin-left:auto; border:none; background:var(--accent);"
                    " color:var(--accent-ink); padding:7px 14px; border-radius:8px;"
                    " font-weight:700; cursor:pointer; font-size:13px;"
                    + (" opacity:0.4;" if not out else "")
                ).props("flat" if not out else "")

        footer_area()

        def _on_ta_change(e: Any) -> None:
            out, miss = _parse(e.value or "")
            parsed["out"] = out
            parsed["miss"] = miss
            footer_area.refresh()

        ta.on_value_change(_on_ta_change)


# ---------------------------------------------------------------------------
# 3. CuisineLean
# ---------------------------------------------------------------------------


def build_cuisine_lean(
    svc: EpicureService,
    get_cuisine: Callable[[], str],
    set_cuisine: Callable[[str], None],
    get_push: Callable[[], int],
    set_push: Callable[[int], None],
    get_cuisines: Callable[[], list[str]] | None = None,
) -> None:
    """Build the 'Lean toward a cuisine' sidebar card inline at current context."""

    def _friendly(full_key: str) -> str:
        """'cuisine:South_Asian' -> 'South Asian'"""
        label: str = full_key.removeprefix("cuisine:")
        return label.replace("_", " ")

    def _push_label(val: int) -> str:
        if val == 0:
            return "off"
        if val <= 25:
            return "subtle"
        if val <= 50:
            return "medium"
        return "bold"

    cuisines = (
        get_cuisines() if get_cuisines is not None else svc.cuisines()
    )  # list of full keys like "cuisine:South_Asian"

    with ui.element("div").style(
        "background:var(--panel); border:1px solid var(--line); border-radius:14px;"
        " padding:14px; display:flex; flex-direction:column; gap:8px;"
    ):
        # title
        ui.label("Lean toward a cuisine").style(
            "font-size:12px; text-transform:uppercase; letter-spacing:.06em;"
            " color:var(--ink-soft); font-family:var(--mono); margin-bottom:2px;"
        )
        # helper subtext (from app.jsx cardSub)
        ui.label(
            "Optional — nudge your suggestions toward a cuisine's flavour profile "
            "to surface adjuncts you'd never reach for."
        ).style(
            "font-size:12.5px; color:var(--ink-soft); line-height:1.45; margin-top:-4px;"
        )

        # select
        cuisine_options = {_friendly(c): c for c in cuisines}
        current_friendly = (
            _friendly(get_cuisine())
            if get_cuisine()
            else (_friendly(cuisines[0]) if cuisines else "")
        )

        sel = (
            ui.select(
                options=list(cuisine_options.keys()),
                value=current_friendly,
            )
            .style(
                "width:100%; padding:9px 10px; border-radius:9px;"
                " border:1px solid var(--line); background:var(--field);"
                " color:var(--ink); font-size:14px;"
            )
            .props("outlined dense options-dense")
        )

        def _on_select(e: Any) -> None:
            full_key: str = cuisine_options.get(e.value, "")
            if full_key:
                set_cuisine(full_key)

        sel.on_value_change(_on_select)

        # slider row
        with ui.row().style("align-items:center; gap:10px; width:100%;"):
            push_label_el = ui.label(_push_label(get_push())).style(
                "font-family:var(--mono); font-size:12.5px; color:var(--ink);"
                " width:52px; text-align:right; text-transform:uppercase; letter-spacing:.03em;"
                " order:2;"
            )

            slider = (
                ui.slider(min=0, max=80, step=1, value=get_push())
                .style("flex:1; accent-color:var(--accent); order:1;")
                .props("dense")
            )

            def _on_slider(e: Any) -> None:
                val: int = int(e.value)
                set_push(val)
                push_label_el.set_text(_push_label(val))

            slider.on_value_change(_on_slider)


# ---------------------------------------------------------------------------
# 4. FlavorLean (Sweet ↔ Savory)
# ---------------------------------------------------------------------------


def build_flavor_lean(
    get_value: Callable[[], int],
    set_value: Callable[[int], None],
) -> None:
    """Build the 'Sweet ↔ savory' bipolar slider sidebar card inline at current context."""

    def _flavor_label(val: int) -> str:
        """Return a label like 'sweet · bold' or 'savory · subtle' or 'off'."""
        if val == 0:
            return "off"
        magnitude: int = abs(val)
        if magnitude <= 25:
            strength = "subtle"
        elif magnitude <= 50:
            strength = "medium"
        else:
            strength = "bold"
        side = "sweet" if val > 0 else "savory"
        return f"{side} · {strength}"

    with ui.element("div").style(
        "background:var(--panel); border:1px solid var(--line); border-radius:14px;"
        " padding:14px; display:flex; flex-direction:column; gap:8px;"
    ):
        # title
        ui.label("Sweet ↔ savory").style(
            "font-size:12px; text-transform:uppercase; letter-spacing:.06em;"
            " color:var(--ink-soft); font-family:var(--mono); margin-bottom:2px;"
        )
        # helper subtext
        ui.label(
            "Optional — nudge the whole recipe toward sweeter or more savory pairings."
        ).style(
            "font-size:12.5px; color:var(--ink-soft); line-height:1.45; margin-top:-4px;"
        )

        # slider row with end labels
        with ui.row().style("align-items:center; gap:10px; width:100%;"):
            # left label: "savory"
            ui.label("savory").style(
                "font-family:var(--mono); font-size:11px; color:var(--ink-soft);"
                " text-transform:lowercase; letter-spacing:.03em; flex:0 0 auto;"
            )

            # slider (flex:1)
            slider = (
                ui.slider(min=-80, max=80, step=1, value=get_value())
                .style("flex:1; accent-color:var(--accent);")
                .props("dense")
            )

            # right label: "sweet"
            ui.label("sweet").style(
                "font-family:var(--mono); font-size:11px; color:var(--ink-soft);"
                " text-transform:lowercase; letter-spacing:.03em; flex:0 0 auto;"
            )

        # flavor strength label
        flavor_label_el = ui.label(_flavor_label(get_value())).style(
            "font-family:var(--mono); font-size:12.5px; color:var(--ink);"
            " text-align:center; text-transform:uppercase; letter-spacing:.03em;"
        )

        def _on_slider(e: Any) -> None:
            val: int = int(e.value)
            set_value(val)
            flavor_label_el.set_text(_flavor_label(val))

        slider.on_value_change(_on_slider)


# ---------------------------------------------------------------------------
# 5. ProteinToggle
# ---------------------------------------------------------------------------


def build_protein_toggle(
    get_value: Callable[[], bool],
    set_value: Callable[[bool], None],
) -> None:
    """Build the 'Protein sources only' toggle sidebar card inline at current context.

    Restricts the suggestion list to high-protein ingredients (identified via
    the model's usda_protein_g poles).  This is a similarity-based approximation
    — 'lean toward protein sources,' not an exhaustive filter.  See
    EpicureService._PROTEIN_THRESHOLD for the chosen cut-off and its trade-offs.
    """
    with ui.element("div").style(
        "background:var(--panel); border:1px solid var(--line); border-radius:14px;"
        " padding:14px; display:flex; flex-direction:column; gap:8px;"
    ):
        # title row: switch + label
        with ui.row().style("align-items:center; gap:10px;"):
            sw = ui.switch(value=get_value()).style("accent-color:var(--accent);")
            ui.label("Protein sources only").style(
                "font-size:12px; text-transform:uppercase; letter-spacing:.06em;"
                " color:var(--ink-soft); font-family:var(--mono);"
            )
        # helper subtext
        ui.label(
            "Show only high-protein ingredients in suggestions. "
            "Similarity-based — lean toward protein sources, not exhaustive."
        ).style(
            "font-size:12.5px; color:var(--ink-soft); line-height:1.45; margin-top:-4px;"
        )
        sw.on_value_change(lambda e: set_value(bool(e.value)))
