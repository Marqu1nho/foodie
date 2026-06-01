Build a local fastapi w/ custom html (or NiceGUI 3.0) app for exploring food-ingredient pairings using the Epicure embedding models. Personal kitchen + mead-brewing tool — local only, no auth, no database.

# FIRST BIT IS TO DECIDE THE STACK!
- I've got some experience w/ niceGUI
- but curious about fastapi w/ custom html?
- or something that is rust/or go - (think ultra blazing fast since I'm just going to do this locally for mah-self)

## Background
Epicure is a family of three ingredient-embedding models on Hugging Face (repo prefix `Kaikaku/epicure-`):
- `epicure-cooc` — co-occurrence: "what do I cook this with"
- `epicure-chem` — flavor chemistry: "what shares aroma compounds"
- `epicure-core` — a blend of both
Each is a ~2MB skip-gram embedding over ~1,790 canonical ingredients (300-dim vectors). They ship a custom loader `epicure.py` and load via `Epicure.from_pretrained("Kaikaku/epicure-cooc")`.

## CRITICAL FIRST STEP — read the API, don't assume it
Before writing any app code, fetch and READ `epicure.py` to learn the real API. Get it with:
    hf download Kaikaku/epicure-cooc epicure.py --local-dir .
Confirm from the source: the `from_pretrained` signature, what `neighbors()` returns, whether raw per-ingredient vectors are accessible (needed for multi-ingredient centroid queries), and the `slerp()` / `closest_mode()` signatures. Build against the actual API, not the README examples.
If the loader does NOT expose raw vectors, load `embeddings.safetensors` (key `embeddings`, a 1790x300 matrix) and `vocab.json` directly for the centroid math — explicit, no hacks.

Ensure all three models are cached (idempotent):
    hf download Kaikaku/epicure-cooc
    hf download Kaikaku/epicure-core
    hf download Kaikaku/epicure-chem

## Stack & setup
- Python via `uv` (uv venv + uv pip install). Deps: nicegui huggingface_hub safetensors numpy.
- NiceGUI, run on port 50000.
- Load all three models once at startup into memory (~6MB total — trivial, no lazy loading, no async needed for queries).

## Architecture (follow this)
- `app.py` — thin entry/orchestrator ONLY: build the page, wire UI to the service, call ui.run(). No model or query logic inline.
- `epicure_service.py` — loads the three models once; exposes clean query functions: single-ingredient neighbors, multi-ingredient pairing (centroid of input vectors then neighbors, excluding the inputs), and cuisine-pole slerp exploration. Returns plain data — lists of (ingredient, score).
- `ui_components.py` — the NiceGUI UI pieces.
- Keep the vendored `epicure.py` at project root.

## Features
1. Ingredient input with autocomplete against the model vocab. Only allow known ingredients (prevents out-of-vocab errors). Support multiple ingredients.
2. "Use my leftovers" mode — enter what you have on hand; compute the centroid of those vectors and return the top-K ingredients that pair with the group (excluding the inputs). Answers "I've got X, Y, Z — what should I add."
3. Compare-across-models view (the key feature) — for one query, show cooc / core / chem results side by side in three columns, so the contrast between recipe-habit pairings and flavor-chemistry pairings is visible at a glance.
4. Mead exploration mode — single-ingredient explorer for brewing: enter a base (honey, a fruit, a spice) and browse neighbors, with chem as the default model since molecular pairings are the more inspiring signal for novel adjuncts. If the loader exposes cuisine-pole slerp, add a "push toward [cuisine]" control as a bonus.

## UX
- Clean and minimal; results as ranked lists showing the similarity score.
- Model selector (cooc/core/chem) where a single model is used; the compare view shows all three.

Start by reading epicure.py, then scaffold the structure, then build features in order.