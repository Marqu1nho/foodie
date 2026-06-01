"""
Behavior-focused tests for EpicureService.
Uses the session-scoped `epicure_service` fixture from conftest.py.
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# SEARCH / RESOLVE
# ---------------------------------------------------------------------------


def test_search_prefix_first(epicure_service):
    results = epicure_service.search("sesame", limit=8)
    assert len(results) <= 8
    # All returned names must contain 'sesame'
    for name in results:
        assert "sesame" in name.lower()
    # Prefix matches (name starts with 'sesame') must come before substring-only matches
    prefix_indices = [i for i, n in enumerate(results) if n.lower().startswith("sesame")]
    substring_indices = [i for i, n in enumerate(results) if not n.lower().startswith("sesame")]
    if prefix_indices and substring_indices:
        assert max(prefix_indices) < min(substring_indices), (
            "Prefix matches must all appear before substring-only matches"
        )


def test_search_space_underscore(epicure_service):
    results = epicure_service.search("sesame o", limit=8)
    names_lower = [n.lower() for n in results]
    assert "sesame_oil" in names_lower, (
        "Query with space 'sesame o' should match 'sesame_oil' (underscore/space equivalence)"
    )


def test_search_empty(epicure_service):
    assert epicure_service.search("") == []
    assert epicure_service.search("   ") == []


def test_resolve_exact_and_spaces(epicure_service):
    assert epicure_service.resolve("sesame_oil") == "sesame_oil"
    # Case + space->underscore normalisation
    assert epicure_service.resolve("Sesame Oil") == "sesame_oil"


def test_resolve_fuzzy_and_miss(epicure_service):
    # A partial prefix for a real ingredient should resolve to something in vocab
    result = epicure_service.resolve("sesame")
    vocab = epicure_service.vocab()
    assert result is not None
    assert result in vocab

    # A clearly nonsense token should return None
    assert epicure_service.resolve("zzzznotathing") is None


# ---------------------------------------------------------------------------
# GROUPS
# ---------------------------------------------------------------------------


def test_group_of_known(epicure_service):
    all_groups = epicure_service.groups()
    assert isinstance(all_groups, list)
    assert len(all_groups) > 0

    honey_group = epicure_service.group_of("honey")
    assert isinstance(honey_group, str)
    assert len(honey_group) > 0
    assert honey_group in all_groups

    chicken_group = epicure_service.group_of("chicken")
    assert isinstance(chicken_group, str)
    assert len(chicken_group) > 0
    assert chicken_group in all_groups


# ---------------------------------------------------------------------------
# NEIGHBORS / PAIRINGS
# ---------------------------------------------------------------------------


def test_neighbors_shape(epicure_service):
    results = epicure_service.neighbors("cooc", "garlic", 5)
    assert len(results) == 5
    names = [n for n, _ in results]
    scores = [s for _, s in results]
    # Self must be excluded
    assert "garlic" not in names
    # Scores must be non-increasing
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1] - 1e-9, "Scores must be in non-increasing order"


def test_pairings_excludes_inputs(epicure_service):
    inputs = ["apple", "cinnamon"]
    results = epicure_service.pairings("core", inputs, 10)
    assert len(results) <= 10
    names = [n for n, _ in results]
    for inp in inputs:
        assert inp not in names, f"Input ingredient '{inp}' should be excluded from pairings"
    scores = [s for _, s in results]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1] - 1e-9, "Scores must be in non-increasing order"


def test_pairings_pushed_theta0_matches_pairings(epicure_service):
    """theta_deg=0 means no rotation; result should match plain pairings()."""
    names = ["honey", "orange"]
    cuisine = epicure_service.cuisines("core")[0]
    k = 8

    base = epicure_service.pairings("core", names, k)
    pushed = epicure_service.pairings_pushed("core", names, cuisine, 0.0, k)

    base_names = [n for n, _ in base]
    pushed_names = [n for n, _ in pushed]
    assert base_names == pushed_names, (
        "pairings_pushed with theta=0 should return same ordered names as pairings()"
    )


def test_pairings_pushed_changes_with_theta(epicure_service):
    """A large rotation should change the result list."""
    names = ["honey", "orange"]
    cuisine = epicure_service.cuisines("core")[0]
    k = 8

    base = epicure_service.pairings("core", names, k)
    pushed = epicure_service.pairings_pushed("core", names, cuisine, 60.0, k)

    base_names = [n for n, _ in base]
    pushed_names = [n for n, _ in pushed]
    assert base_names != pushed_names, (
        "pairings_pushed with theta=60 should differ from unrotated pairings"
    )


def test_pairings_pushed_missing_pole_fallback(epicure_service):
    """Unknown cuisine_key must not raise and must equal plain pairings()."""
    names = ["honey", "orange"]
    fake_cuisine = "cuisine:NotARealPole"
    k = 8

    base = epicure_service.pairings("core", names, k)
    fallback = epicure_service.pairings_pushed("core", names, fake_cuisine, 30.0, k)

    assert [n for n, _ in base] == [n for n, _ in fallback], (
        "Missing pole should fall back to plain pairings result"
    )


# ---------------------------------------------------------------------------
# COMPARE / CUISINES / WHY
# ---------------------------------------------------------------------------


def test_compare_keys(epicure_service):
    result = epicure_service.compare("basil", 5)
    assert set(result.keys()) == {"cooc", "core", "chem"}
    for key, lst in result.items():
        assert isinstance(lst, list)
        assert len(lst) <= 5
        for item in lst:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], float)


def test_cuisines_per_model(epicure_service):
    for model_key in ("core", "cooc", "chem"):
        result = epicure_service.cuisines(model_key)
        assert isinstance(result, list), f"cuisines('{model_key}') should return a list"
        assert len(result) > 0, f"cuisines('{model_key}') should not be empty"
        for key in result:
            assert key.startswith("cuisine:"), (
                f"All cuisine keys should start with 'cuisine:', got: {key!r}"
            )


def test_why_structure(epicure_service):
    result = epicure_service.why("core", "cinnamon", ["honey", "orange"])
    assert "bridges" in result
    assert "shared_modes" in result

    bridges = result["bridges"]
    assert isinstance(bridges, list)
    # bridges should be a subset of the in-play names
    for b in bridges:
        assert b in ["honey", "orange"], f"Bridge {b!r} not in input names"

    shared_modes = result["shared_modes"]
    assert isinstance(shared_modes, list)
    for mode in shared_modes:
        assert isinstance(mode, dict)
        assert "kind" in mode
        assert "label" in mode

    # Empty names input -> empty bridges and shared_modes
    empty_result = epicure_service.why("core", "cinnamon", [])
    assert empty_result["bridges"] == []
    assert empty_result["shared_modes"] == []
