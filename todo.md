# TODO

## Next phase
- [ ] **Redo protein feature: curated list + "start from a protein" flow**
  - Current protein filter is a rough model-cluster lean — the embeddings don't encode true protein content (confirmed: chicken/beef/egg rank low across all `usda_protein_g` poles; balsamic_vinegar/baijiu rank high).
  - Refined intent: start from a **main protein source** when building a **savory** dish — pick a protein as the seed/first basket ingredient and pair outward, not just filter the suggestion list.
  - Plan: (1) replace model-derived `protein_sources()` with a **curated** set of real protein-source vocab items (meats, poultry, fish/seafood, eggs, dairy, tofu/soy, legumes, nuts/seeds) — the `restrict_to` plumbing already exists, so it's a one-line swap. (2) Add a "start from a protein" quick-pick affordance to seed the recipe; pairs naturally with the savory side of the sweet/savory lever.
- [ ] **Remove Paste a list**
  - this is cumbersom since we don't quite get the fuzzy search
  - high margi for error
  - clutters up the space
