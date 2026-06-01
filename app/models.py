"""Typed domain models for the Epicure app."""

from __future__ import annotations

from pydantic import BaseModel


class Recipe(BaseModel):
    """A saved recipe. The user's ingredient basket plus metadata."""

    id: int | None = None
    name: str
    group: str
    items: list[str]
    model: str
    notes: str = ""
    updated: int | None = None
