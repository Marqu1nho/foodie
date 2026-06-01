"""
EpicureService: loads all three Epicure models once and exposes query methods.
No NiceGUI imports here — plain data in, plain data out.
"""

from __future__ import annotations

import math

import numpy as np
from app.vendor.epicure import Epicure

_REPOS = {
    "cooc": "Kaikaku/epicure-cooc",
    "core": "Kaikaku/epicure-core",
    "chem": "Kaikaku/epicure-chem",
}

_EPS = 1e-9

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

    def _precompute_groups(self) -> dict[str, str]:
        """For every ingredient in the cooc vocab, find the closest fg_* binary mode."""
        m = self._models["cooc"]
        result: dict[str, str] = {}
        for name in m.vocab:
            hits = m.closest_mode(name, kind="binary", k=1)
            group = "other"
            if hits:
                mode_id = hits[0][0]          # e.g. "fg_Vegetable/M2"
                prefix = mode_id.split("/")[0]  # e.g. "fg_Vegetable"
                if prefix.startswith("fg_"):
                    segment = prefix[3:]       # e.g. "Vegetable"
                    group = _FG_PREFIX_TO_GROUP.get(segment, "other")
            result[name] = group
        return result

    def _model(self, key: str) -> Epicure:
        if key not in self._models:
            raise KeyError(f"Unknown model key '{key}'. Choose from: {list(self._models)}")
        return self._models[key]

    # --- vocabulary ---

    def vocab(self) -> list[str]:
        """Sorted list of ingredient names (shared vocab from cooc model)."""
        return sorted(self._models["cooc"].vocab.keys())

    # --- single-ingredient neighbors ---

    def neighbors(self, model_key: str, name: str, k: int = 15) -> list[tuple[str, float]]:
        """Top-k nearest neighbors for a single ingredient under the given model."""
        return self._model(model_key).neighbors(name, k=k, exclude_self=True)

    # --- multi-ingredient centroid pairings ---

    def pairings(self, model_key: str, names: list[str], k: int = 15) -> list[tuple[str, float]]:
        """
        'Leftovers' centroid query: mean of unit vectors for each input ingredient,
        re-normalized, then cosine similarities against the full embedding matrix.
        Input ingredients are excluded from results.
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

        order = np.argsort(-sims)
        return [(m.itos[int(i)], float(sims[i])) for i in order[:k]]

    # --- cross-model compare ---

    def compare(self, name: str, k: int = 15) -> dict[str, list[tuple[str, float]]]:
        """Neighbors for the same ingredient across all three models."""
        return {key: self._model(key).neighbors(name, k=k, exclude_self=True)
                for key in _REPOS}

    # --- cuisine poles ---

    def cuisines(self) -> list[str]:
        """Cuisine pole keys present in ALL three models, so any selected model
        can be leaned toward without a missing-pole KeyError."""
        sets = [
            {k for k in m.supervised_poles if k.startswith("cuisine:")}
            for m in self._models.values()
        ]
        common = set.intersection(*sets) if sets else set()
        return sorted(common)

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
        q_us = q.replace(" ", "_")   # spaces -> underscores for matching
        q_sp = q.replace("_", " ")   # underscores -> spaces for matching

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

    # --- cuisine-pushed pairings ---

    def pairings_pushed(
        self,
        model_key: str,
        names: list[str],
        cuisine_key: str,
        theta_deg: float,
        k: int = 12,
    ) -> list[tuple[str, float]]:
        """Like pairings(), but rotate the recipe centroid toward a cuisine pole first."""
        m = self._model(model_key)
        if cuisine_key not in m.supervised_poles:
            # Pole not defined for this model — skip the lean, just pair.
            return self.pairings(model_key, names, k)
        vecs = np.stack([m.vec(n, normalised=True) for n in names], axis=0)
        centroid = vecs.mean(axis=0)
        v = _unit_vec(centroid)

        d = np.array(m.supervised_poles[cuisine_key], dtype=np.float32)
        d = _unit_vec(d)

        # Gram-Schmidt: orthogonal component of d relative to v
        d_perp = d - float(d @ v) * v
        n_perp = np.linalg.norm(d_perp)
        if n_perp < 1e-9:
            q = v
        else:
            d_perp = d_perp / n_perp
            theta = math.radians(float(theta_deg))
            q = math.cos(theta) * v + math.sin(theta) * d_perp
            q = _unit_vec(q)

        sims = m.E @ q
        input_indices = [m.vocab[n] for n in names]
        for idx in input_indices:
            sims[idx] = -np.inf

        order = np.argsort(-sims)
        return [(m.itos[int(i)], float(sims[i])) for i in order[:k]]

    # --- why does this pair ---

    def why(
        self,
        model_key: str,
        name: str,
        names: list[str],
    ) -> dict:
        """Ground a 'why does this pair' explanation in real model signals.

        Returns:
            {
                "bridges": [up to 3 in-play ingredient names ranked by cosine sim],
                "shared_modes": [up to 5 {"kind": str, "label": str} dicts],
            }
        """
        if not names:
            return {"bridges": [], "shared_modes": []}

        key = model_key if model_key in self._models else "core"
        m = self._model(key)

        # Bridges: in-play ingredients ranked by cosine sim to `name`
        v_name = m.vec(name, normalised=True)
        bridge_sims = [
            (n, float(m.vec(n, normalised=True) @ v_name))
            for n in names
        ]
        bridge_sims.sort(key=lambda x: -x[1])
        bridges = [n for n, _ in bridge_sims[:3]]

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
        shared: list[dict] = []
        # Build a kind lookup for modes that appear in name's top modes
        mode_kind_map = {mo.mode_id: mo.kind for mo in m.modes}
        # Prefer preferred kinds, then others
        preferred_shared = []
        other_shared = []
        for mid, lbl, _ in name_modes:
            if mid in centroid_top_ids:
                kind = mode_kind_map.get(mid, "")
                entry = {"kind": kind, "label": lbl}
                if kind in _WHY_PREFERRED_KINDS:
                    preferred_shared.append(entry)
                else:
                    other_shared.append(entry)
        shared = (preferred_shared + other_shared)[:5]

        return {"bridges": bridges, "shared_modes": shared}
