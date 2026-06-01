from __future__ import annotations


def test_true() -> None:
    assert True


def test_imports() -> None:
    import app.services.epicure_service  # noqa: F401
    import app.services.recipe_store  # noqa: F401
