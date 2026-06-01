def test_true():
    assert True


def test_imports():
    import app.services.epicure_service  # noqa: F401
    import app.services.recipe_store  # noqa: F401
