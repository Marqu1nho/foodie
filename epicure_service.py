"""
EpicureService: loads all three Epicure models once and exposes query methods.
No NiceGUI imports here — plain data in, plain data out.
"""

from __future__ import annotations

import numpy as np
from epicure import Epicure

_REPOS = {
    "cooc": "Kaikaku/epicure-cooc",
    "core": "Kaikaku/epicure-core",
    "chem": "Kaikaku/epicure-chem",
}

_EPS = 1e-9


class EpicureService:
    def __init__(self) -> None:
        print("Loading Epicure models (this may take a moment)...")
        self._models: dict[str, Epicure] = {
            key: Epicure.from_pretrained(repo) for key, repo in _REPOS.items()
        }
        print("All models loaded.")

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
        """Full cuisine pole keys (e.g. 'cuisine:South_Asian') from the cooc model."""
        return self._models["cooc"].list_supervised_poles(prefix="cuisine:")

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
