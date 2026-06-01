from __future__ import annotations

from pathlib import Path
from typing import Generator

import pytest

from app.services.epicure_service import EpicureService
from app.services.recipe_store import RecipeStore


@pytest.fixture(scope="session")
def epicure_service() -> EpicureService:
    """Session-scoped EpicureService — models load once for the whole suite."""
    return EpicureService()


@pytest.fixture
def recipe_store(tmp_path: Path) -> Generator[RecipeStore, None, None]:
    """Function-scoped RecipeStore pointed at an isolated temp directory."""
    store = RecipeStore(base_dir=str(tmp_path.resolve()))
    yield store
