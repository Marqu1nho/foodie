"""tests/test_leans.py — Unit tests for app.leans.build_directions."""

from __future__ import annotations


from app.leans import build_directions
from app.services.epicure_service import EpicureService


def test_no_levers_empty_cuisine(epicure_service: EpicureService) -> None:
    """No push, no flavor, no cuisine -> empty directions."""
    assert build_directions(epicure_service, "core", "", 0, 0) == []


def test_no_levers_with_cuisine_push_zero(epicure_service: EpicureService) -> None:
    """Push == 0 means cuisine direction is off even if cuisine is set."""
    cuisine = epicure_service.cuisines("core")[0]
    assert build_directions(epicure_service, "core", cuisine, 0, 0) == []


def test_cuisine_only(epicure_service: EpicureService) -> None:
    """Cuisine push with flavor=0 yields exactly one cuisine direction."""
    cuisine = epicure_service.cuisines("core")[0]
    result = build_directions(epicure_service, "core", cuisine, 40, 0)
    assert result == [(cuisine, 40.0)]


def test_sweet(epicure_service: EpicureService) -> None:
    """Positive flavor yields one sweet direction at the correct strength."""
    result = build_directions(epicure_service, "core", "", 0, 50)
    assert len(result) == 1
    pole_key, strength = result[0]
    assert pole_key == epicure_service.flavor_poles("core")["sweet"]
    assert strength == 50.0


def test_savory(epicure_service: EpicureService) -> None:
    """Negative flavor yields one savory direction with positive strength."""
    result = build_directions(epicure_service, "core", "", 0, -30)
    assert len(result) == 1
    pole_key, strength = result[0]
    assert pole_key == epicure_service.flavor_poles("core")["savory"]
    assert strength == 30.0


def test_compose_both(epicure_service: EpicureService) -> None:
    """Cuisine push + sweet flavor yields two directions with correct strengths."""
    cuisine = epicure_service.cuisines("core")[0]
    result = build_directions(epicure_service, "core", cuisine, 40, 60)
    assert len(result) == 2
    assert result[0] == (cuisine, 40.0)
    pole_key, strength = result[1]
    assert pole_key == epicure_service.flavor_poles("core")["sweet"]
    assert strength == 60.0


def test_flavor_zero_off(epicure_service: EpicureService) -> None:
    """flavor=0 produces no flavor direction even if poles exist."""
    result = build_directions(epicure_service, "core", "", 0, 0)
    assert result == []


def test_pairings_directed_sanity(epicure_service: EpicureService) -> None:
    """build_directions output fed into pairings_directed returns up to k results."""
    cuisine = epicure_service.cuisines("core")[0]
    dirs = build_directions(epicure_service, "core", cuisine, 40, 30)
    results = epicure_service.pairings_directed("core", ["honey", "orange"], dirs, 5)
    assert 1 <= len(results) <= 5
    for name, score in results:
        assert isinstance(name, str)
        assert isinstance(score, float)
