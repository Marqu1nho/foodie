"""
EpicureService: loads all three Epicure models once and exposes query methods.
No NiceGUI imports here — plain data in, plain data out.
"""

from __future__ import annotations

import os

os.environ.setdefault(
    "HF_HUB_OFFLINE", "1"
)  # models are pre-cached; skip Hub metadata checks (faster boot, no unauthenticated-request warning)

import math
from typing import TypedDict

import numpy as np
from app.vendor.epicure import Epicure

# ---------------------------------------------------------------------------
# Flavor-pole validation seeds
# ---------------------------------------------------------------------------
# These are used at init to pick the best validated sweet/savory pole per model.
# IMPORTANT: supervised-pole names lie — a pole labeled "sweet" may actually
# capture savory compounds.  We validate by scoring candidates against seed
# ingredients whose vocab membership is checked at runtime.
#
# Sweet candidates: keys starting with 'sweet_score'
# Savory candidates: keys starting with 'umami_score' or 'cf_savory'
#
# Validated-in-CORE references (from inspecting top-10 nearest ingredients):
#   SWEET  ~ 'sweet_score/Sweet fruits, nuts and cocktail spirits'
#   SAVORY ~ 'umami_score/Savory vegetables, cheeses, and seafood'
#          or 'cf_savory/Mediterranean savory pantry staples'
_SWEET_SEEDS = [
    "honey",
    "vanilla",
    "sugar",
    "brown_sugar",
    "maple_syrup",
    "honey_mustard",
    "molasses",
    "agave",
    "powdered_sugar",
    "cane_sugar",
    "date",
    "fig",
    "peach",
    "mango",
    "pineapple",
]
_SAVORY_SEEDS = [
    "soy_sauce",
    "miso",
    "parmesan",
    "mushroom",
    "olive_oil",
    "anchovy",
    "fish_sauce",
    "worcestershire_sauce",
    "tamari",
    "cheese",
    "nutritional_yeast",
    "capers",
    "sun_dried_tomato",
    "tahini",
    "miso_paste",
]
_FLAVOR_POLE_TOP_N = 20  # how many nearest neighbors to inspect per candidate
_FLAVOR_POLE_MIN_SCORE = 1  # minimum seed hits to accept a candidate


class WhyMode(TypedDict):
    """A single shared signal entry from why()."""

    kind: str
    label: str


class WhyResult(TypedDict):
    """Return type for EpicureService.why()."""

    bridges: list[str]
    shared_modes: list[WhyMode]


_REPOS = {
    "cooc": "Kaikaku/epicure-cooc",
    "core": "Kaikaku/epicure-core",
    "chem": "Kaikaku/epicure-chem",
}

_EPS = 1e-9

# ---------------------------------------------------------------------------
# Protein-sources filter
# ---------------------------------------------------------------------------
# Build an averaged protein direction from all supervised_poles whose key
# starts with 'usda_protein_g'.  Each ingredient's protein_score is the
# dot-product of its unit embedding against that averaged direction.
#
# Threshold 0.64 was chosen empirically against the CORE vocab:
#   INCLUDED: tofu (0.75), chickpea (0.74), lentil (0.72), cashew (0.70),
#             black_bean (0.69), shrimp (0.65)
#   EXCLUDED: basil (0.63), cheese (0.63), sugar (0.55), honey (0.51),
#             vanilla (0.41)
# The set size is ~491 items at this threshold.  Animal proteins such as
# chicken/beef/pork/egg score 0.57-0.59 and fall below the threshold — this
# is an acknowledged limitation; the filter is "lean toward protein sources,"
# not exhaustive.
_PROTEIN_THRESHOLD: float = 0.64

# Map fg_ prefix segment -> coarse group key
_FG_PREFIX_TO_GROUP: dict[str, str] = {
    "Beverage": "beverage",
    "Dairy": "dairy",
    "Fruit": "fruit",
    "Grain": "grain",
    "Pantry": "pantry",
    "Spice": "spice",
    "Vegetable": "vegetable",
}

# Preferred mode kinds for why() shared_modes
_WHY_PREFERRED_KINDS = {"cuisine", "food_group", "factor", "cf_sensory"}


def _unit_vec(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    return v / max(n, _EPS)


class EpicureService:
    def __init__(self) -> None:
        print("Loading Epicure models (this may take a moment)...")
        self._models: dict[str, Epicure] = {
            key: Epicure.from_pretrained(repo) for key, repo in _REPOS.items()
        }
        print("All models loaded.")
        self._group_by_name = self._precompute_groups()
        # Precompute validated sweet/savory poles for each model.
        self._flavor_poles: dict[str, dict[str, str]] = {
            key: self._compute_flavor_poles(self._models[key]) for key in _REPOS
        }
        # Precompute the protein-sources set from the CORE model.
        self._protein_sources: set[str] = self._compute_protein_sources(
            self._models["core"]
        )

    def _precompute_groups(self) -> dict[str, str]:
        """For every ingredient in the cooc vocab, find the closest fg_* binary mode."""
        m = self._models["cooc"]
        result: dict[str, str] = {}
        for name in m.vocab:
            hits = m.closest_mode(name, kind="binary", k=1)
            group = "other"
            if hits:
                mode_id = hits[0][0]  # e.g. "fg_Vegetable/M2"
                prefix = mode_id.split("/")[0]  # e.g. "fg_Vegetable"
                if prefix.startswith("fg_"):
                    segment = prefix[3:]  # e.g. "Vegetable"
                    group = _FG_PREFIX_TO_GROUP.get(segment, "other")
            result[name] = group
        return result

    @staticmethod
    def _score_pole_candidate(
        m: Epicure,
        pole_key: str,
        seeds: list[str],
    ) -> int:
        """Return how many seed ingredients appear in the top-N nearest to the pole vec."""
        pole_vec = _unit_vec(np.array(m.supervised_poles[pole_key], dtype=np.float32))
        sims = m.E @ pole_vec
        order = np.argsort(-sims)
        top_names = {m.itos[int(i)] for i in order[:_FLAVOR_POLE_TOP_N]}
        # Only count seeds that exist in vocab
        valid_seeds = {s for s in seeds if s in m.vocab}
        return len(valid_seeds & top_names)

    def _compute_flavor_poles(self, m: Epicure) -> dict[str, str]:
        """Pick the best validated sweet and savory pole for a single model."""
        result: dict[str, str] = {}

        # Sweet: candidates start with 'sweet_score'
        sweet_candidates = [
            k for k in m.supervised_poles if k.startswith("sweet_score")
        ]
        best_sweet_key: str | None = None
        best_sweet_score = -1
        for candidate in sweet_candidates:
            score = self._score_pole_candidate(m, candidate, _SWEET_SEEDS)
            if score > best_sweet_score:
                best_sweet_score = score
                best_sweet_key = candidate
        if best_sweet_key is not None and best_sweet_score >= _FLAVOR_POLE_MIN_SCORE:
            result["sweet"] = best_sweet_key

        # Savory: candidates start with 'umami_score' or 'cf_savory'
        savory_candidates = [
            k
            for k in m.supervised_poles
            if k.startswith("umami_score") or k.startswith("cf_savory")
        ]
        best_savory_key: str | None = None
        best_savory_score = -1
        for candidate in savory_candidates:
            score = self._score_pole_candidate(m, candidate, _SAVORY_SEEDS)
            if score > best_savory_score:
                best_savory_score = score
                best_savory_key = candidate
        if best_savory_key is not None and best_savory_score >= _FLAVOR_POLE_MIN_SCORE:
            result["savory"] = best_savory_key

        return result

    @staticmethod
    def _compute_protein_sources(m: Epicure) -> set[str]:
        """Build the protein-sources set from the model's usda_protein_g poles.

        Averages unit-normalised pole vectors for every supervised_poles key
        starting with 'usda_protein_g', then scores each vocab ingredient by
        cosine similarity to that averaged direction.  Ingredients whose score
        meets or exceeds _PROTEIN_THRESHOLD are included.
        """
        pole_keys = [k for k in m.supervised_poles if k.startswith("usda_protein_g")]
        if not pole_keys:
            return set()
        vecs = []
        for pk in pole_keys:
            v = np.array(m.supervised_poles[pk], dtype=np.float32)
            vecs.append(_unit_vec(v))
        p = _unit_vec(np.mean(vecs, axis=0))
        sims = m.E @ p
        return {
            name for i, name in m.itos.items() if float(sims[i]) >= _PROTEIN_THRESHOLD
        }

    def _model(self, key: str) -> Epicure:
        if key not in self._models:
            raise KeyError(
                f"Unknown model key '{key}'. Choose from: {list(self._models)}"
            )
        return self._models[key]

    # --- vocabulary ---

    def vocab(self) -> list[str]:
        """Sorted list of ingredient names (shared vocab from cooc model)."""
        return sorted(self._models["cooc"].vocab.keys())

    def protein_sources(self) -> set[str]:
        """Return the precomputed set of high-protein ingredient names.

        Built at init from the CORE model's usda_protein_g poles; see
        _PROTEIN_THRESHOLD for the chosen cutoff and its trade-offs.
        Returns the internal set directly (caller should not mutate it).
        """
        return self._protein_sources

    # --- single-ingredient neighbors ---

    def neighbors(
        self, model_key: str, name: str, k: int = 15
    ) -> list[tuple[str, float]]:
        """Top-k nearest neighbors for a single ingredient under the given model."""
        return self._model(model_key).neighbors(name, k=k, exclude_self=True)

    # --- multi-ingredient centroid pairings ---

    def pairings(
        self,
        model_key: str,
        names: list[str],
        k: int = 15,
        restrict_to: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        """
        'Leftovers' centroid query: mean of unit vectors for each input ingredient,
        re-normalized, then cosine similarities against the full embedding matrix.
        Input ingredients are excluded from results.

        If ``restrict_to`` is provided, only ingredients whose names appear in
        that set are eligible to be returned (filtered before top-k selection).
        """
        m = self._model(model_key)
        vecs = np.stack([m.vec(n, normalised=True) for n in names], axis=0)
        centroid = vecs.mean(axis=0)
        norm = np.linalg.norm(centroid)
        centroid = centroid / max(norm, _EPS)

        sims = m.E @ centroid
        input_indices = [m.vocab[n] for n in names]
        for idx in input_indices:
            sims[idx] = -np.inf

        if restrict_to is not None:
            for i, name in m.itos.items():
                if name not in restrict_to:
                    sims[i] = -np.inf

        order = np.argsort(-sims)
        return [(m.itos[int(i)], float(sims[i])) for i in order[:k]]

    # --- cross-model compare ---

    def compare(self, name: str, k: int = 15) -> dict[str, list[tuple[str, float]]]:
        """Neighbors for the same ingredient across all three models."""
        return {
            key: self._model(key).neighbors(name, k=k, exclude_self=True)
            for key in _REPOS
        }

    # --- flavor poles ---

    def flavor_poles(self, model_key: str) -> dict[str, str]:
        """Return the validated best pole keys for sweet/savory for the given model.

        Keys present in the returned dict: "sweet" and/or "savory".
        Each value is a supervised-pole key present in that model's supervised_poles.
        A key is omitted if no candidate clears the minimum seed-hit bar.

        Determination is done at __init__ time (precomputed once per model) by
        scoring candidate poles against seed ingredient sets — see module-level
        _SWEET_SEEDS / _SAVORY_SEEDS.
        """
        if model_key not in self._flavor_poles:
            raise KeyError(
                f"Unknown model key '{model_key}'. Choose from: {list(self._models)}"
            )
        return dict(self._flavor_poles[model_key])

    # --- cuisine poles ---

    def cuisines(self, model_key: str = "core") -> list[str]:
        """Cuisine pole keys available in the given model, sorted."""
        m = self._model(model_key)
        return sorted(k for k in m.supervised_poles if k.startswith("cuisine:"))

    # --- slerp toward a cuisine ---

    def slerp_cuisine(
        self,
        model_key: str,
        seed: str,
        cuisine_key: str,
        theta_deg: float = 30.0,
        k: int = 15,
    ) -> list[tuple[str, float]]:
        """Rotate seed ingredient toward a cuisine pole by theta_deg on the unit sphere."""
        return self._model(model_key).slerp(
            seed=seed,
            direction=cuisine_key,
            theta_deg=theta_deg,
            k=k,
            exclude_seed=True,
        )

    # --- fuzzy search ---

    def search(self, query: str, limit: int = 8) -> list[str]:
        """Fuzzy type-ahead over the cooc vocab.

        Matches where the name starts with the query come before names that merely
        contain it.  Underscores and spaces are treated as equivalent so that
        "sesame o" matches "sesame_oil".
        """
        if not query:
            return []
        q = query.lower()
        q_us = q.replace(" ", "_")  # spaces -> underscores for matching
        q_sp = q.replace("_", " ")  # underscores -> spaces for matching

        starts: list[str] = []
        contains: list[str] = []
        for name in self._models["cooc"].vocab:
            n_norm = name.lower()
            n_sp = n_norm.replace("_", " ")
            if n_norm.startswith(q_us) or n_sp.startswith(q_sp):
                starts.append(name)
            elif q_us in n_norm or q_sp in n_sp:
                contains.append(name)
        return (sorted(starts) + sorted(contains))[:limit]

    # --- token resolver ---

    def resolve(self, token: str) -> str | None:
        """Resolve a free-typed token to a real vocab name.

        Exact match (lowercase + spaces to underscores) wins; otherwise the first
        search hit; otherwise None.
        """
        if not token:
            return None
        canonical = token.lower().replace(" ", "_")
        vocab = self._models["cooc"].vocab
        if canonical in vocab:
            return canonical
        hits = self.search(token, limit=1)
        return hits[0] if hits else None

    # --- food group ---

    def group_of(self, name: str) -> str:
        """Return the coarse food-group category key for the named ingredient."""
        return self._group_by_name.get(name, "other")

    def groups(self) -> list[str]:
        """Sorted distinct group keys present in the precomputed map."""
        return sorted(set(self._group_by_name.values()))

    # --- composable directed pairings ---

    def pairings_directed(
        self,
        model_key: str,
        names: list[str],
        directions: list[tuple[str, float]],
        k: int = 12,
        restrict_to: set[str] | None = None,
    ) -> list[tuple[str, float]]:
        """Rotate a recipe centroid by a composed weighted sum of pole directions.

        Each entry in ``directions`` is a (pole_key, strength) pair.  Poles not
        present in the model's supervised_poles are silently skipped (defensive).
        Directions with strength <= 0 are also skipped.

        The rotation angle theta_deg is derived as sqrt(sum(strength_i^2)) over
        contributing directions, capped at 80 degrees.  This means a single
        direction (pole, theta) is equivalent to pairings_pushed(pole, theta).

        If no valid directions remain after filtering, falls back to plain
        pairings().  If names is empty returns [].

        If ``restrict_to`` is provided, only ingredients whose names appear in
        that set are eligible to be returned (filtered before top-k selection).
        """
        if not names:
            return []

        m = self._model(model_key)

        # Build recipe centroid.
        vecs = np.stack([m.vec(n, normalised=True) for n in names], axis=0)
        centroid = vecs.mean(axis=0)
        v = _unit_vec(centroid)

        # Accumulate weighted pole directions.
        D = np.zeros_like(v)
        sum_sq: float = 0.0
        for pole_key, strength in directions:
            if strength <= 0:
                continue
            if pole_key not in m.supervised_poles:
                continue
            pole_vec = np.array(m.supervised_poles[pole_key], dtype=np.float32)
            D = D + strength * _unit_vec(pole_vec)
            sum_sq += float(strength) ** 2

        # If D is ~zero (no valid directions) fall back to plain pairings.
        if np.linalg.norm(D) < _EPS:
            return self.pairings(model_key, names, k, restrict_to=restrict_to)

        d = _unit_vec(D)
        theta_deg = min(80.0, math.sqrt(sum_sq))

        # Gram-Schmidt: orthogonal component of d relative to v.
        d_perp = d - float(d @ v) * v
        n_perp = np.linalg.norm(d_perp)
        if n_perp < _EPS:
            q = v
        else:
            d_perp = d_perp / n_perp
            theta = math.radians(theta_deg)
            q = math.cos(theta) * v + math.sin(theta) * d_perp
            q = _unit_vec(q)

        sims = m.E @ q
        input_indices = [m.vocab[n] for n in names]
        for idx in input_indices:
            sims[idx] = -np.inf

        if restrict_to is not None:
            for i, name in m.itos.items():
                if name not in restrict_to:
                    sims[i] = -np.inf

        order = np.argsort(-sims)
        return [(m.itos[int(i)], float(sims[i])) for i in order[:k]]

    # --- cuisine-pushed pairings (delegates to pairings_directed) ---

    def pairings_pushed(
        self,
        model_key: str,
        names: list[str],
        cuisine_key: str,
        theta_deg: float,
        k: int = 12,
    ) -> list[tuple[str, float]]:
        """Like pairings(), but rotate the recipe centroid toward a pole first.

        Delegates to pairings_directed() with a single direction, preserving the
        existing API and missing-pole fallback behaviour.
        """
        return self.pairings_directed(
            model_key, names, [(cuisine_key, float(theta_deg))], k
        )

    # --- why does this pair ---

    def why(
        self,
        model_key: str,
        name: str,
        names: list[str],
    ) -> WhyResult:
        """Ground a 'why does this pair' explanation in real model signals.

        Returns:
            {
                "bridges": [up to 3 in-play ingredient names ranked by cosine sim],
                "shared_modes": [up to 5 {"kind": str, "label": str} dicts],
            }
        """
        if not names:
            return WhyResult(bridges=[], shared_modes=[])

        key = model_key if model_key in self._models else "core"
        m = self._model(key)

        # Bridges: in-play ingredients ranked by cosine sim to `name`
        v_name = m.vec(name, normalised=True)
        bridge_sims: list[tuple[str, float]] = [
            (n, float(m.vec(n, normalised=True) @ v_name)) for n in names
        ]
        bridge_sims.sort(key=lambda x: -x[1])
        bridges: list[str] = [n for n, _ in bridge_sims[:3]]

        # Shared modes: intersect top-8 modes of `name` with top-8 modes of centroid
        name_modes = m.closest_mode(name, k=8)

        # Build centroid of in-play ingredients
        vecs = np.stack([m.vec(n, normalised=True) for n in names], axis=0)
        centroid = _unit_vec(vecs.mean(axis=0))
        # Score all modes against centroid
        centroid_scored: list[tuple[str, str, float]] = []
        for mo in m.modes:
            score = float(mo.pole @ centroid / max(np.linalg.norm(mo.pole), _EPS))
            centroid_scored.append((mo.mode_id, mo.label, score))
        centroid_scored.sort(key=lambda x: -x[2])
        centroid_top_ids = {mid for mid, _, _ in centroid_scored[:8]}

        # Intersect
        shared: list[WhyMode] = []
        # Build a kind lookup for modes that appear in name's top modes
        mode_kind_map: dict[str, str] = {mo.mode_id: mo.kind for mo in m.modes}
        # Prefer preferred kinds, then others
        preferred_shared: list[WhyMode] = []
        other_shared: list[WhyMode] = []
        for mid, lbl, _ in name_modes:
            if mid in centroid_top_ids:
                kind = mode_kind_map.get(mid, "")
                entry = WhyMode(kind=kind, label=lbl)
                if kind in _WHY_PREFERRED_KINDS:
                    preferred_shared.append(entry)
                else:
                    other_shared.append(entry)
        shared = (preferred_shared + other_shared)[:5]

        return WhyResult(bridges=bridges, shared_modes=shared)
