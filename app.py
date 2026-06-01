"""
app.py — thin orchestrator for the Epicure food-pairing explorer.
Instantiates EpicureService once, wires the four tab panels, then starts NiceGUI.
No model or query logic lives here.
"""

from nicegui import ui

from epicure_service import EpicureService
from ui_components import (
    build_compare_tab,
    build_explore_tab,
    build_leftovers_tab,
    build_mead_tab,
)

svc = EpicureService()
vocab = svc.vocab()


@ui.page("/")
def index():
    ui.query("body").classes("bg-gray-50")
    with ui.column().classes("w-full max-w-5xl mx-auto p-4 gap-4"):
        ui.label("Epicure — Food Ingredient Pairing Explorer").classes(
            "text-2xl font-bold text-indigo-800"
        )
        ui.label(
            "Powered by the Epicure ingredient embedding models (cooc · core · chem)."
        ).classes("text-gray-500 text-sm -mt-2")

        with ui.tabs().classes("w-full") as tabs:
            tab_explore = ui.tab("Explore")
            tab_leftovers = ui.tab("Leftovers")
            tab_compare = ui.tab("Compare")
            tab_mead = ui.tab("Mead")

        with ui.tab_panels(tabs, value=tab_explore).classes("w-full"):
            with ui.tab_panel(tab_explore):
                build_explore_tab(svc, vocab)
            with ui.tab_panel(tab_leftovers):
                build_leftovers_tab(svc, vocab)
            with ui.tab_panel(tab_compare):
                build_compare_tab(svc, vocab)
            with ui.tab_panel(tab_mead):
                build_mead_tab(svc, vocab)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(port=50000, title="Epicure", reload=True)
