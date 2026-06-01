import json
import os
import re
import time
from pathlib import Path


class RecipeStore:
    DEFAULT_GROUPS = ["Meads", "Weeknight meals", "Leftovers", "Experiments"]

    def __init__(self, base_dir: str = "recipes") -> None:
        """Initialize the recipe store with a base directory."""
        # Resolve base_dir relative to project root (two levels above: services -> app -> root)
        _p = Path(base_dir)
        self.base_dir = _p if _p.is_absolute() else Path(__file__).resolve().parents[2] / base_dir
        # Create the base directory if it doesn't exist
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _safe(self, name: str) -> str:
        """Sanitize a group name into a safe folder name."""
        # Strip whitespace
        name = name.strip()
        # Replace anything not alnum/space/-/_ with empty string
        name = re.sub(r'[^\w\s\-]', '', name)
        # Collapse multiple spaces into single space
        name = re.sub(r'\s+', ' ', name)
        return name

    def groups(self) -> list[str]:
        """Return DEFAULT_GROUPS plus any existing subfolders, de-duplicated."""
        groups = set(self.DEFAULT_GROUPS)

        # Scan for existing subfolders
        if self.base_dir.exists():
            for item in self.base_dir.iterdir():
                if item.is_dir():
                    groups.add(item.name)

        # Return with defaults first, then extras sorted
        result = [g for g in self.DEFAULT_GROUPS if g in groups]
        extras = sorted([g for g in groups if g not in self.DEFAULT_GROUPS])
        return result + extras

    def list(self) -> list[dict]:
        """Return all recipes across all group folders, newest first."""
        recipes = []

        if not self.base_dir.exists():
            return recipes

        # Scan all subfolders
        for group_dir in self.base_dir.iterdir():
            if not group_dir.is_dir():
                continue

            # Scan all .json files in the group folder
            for json_file in group_dir.glob('*.json'):
                try:
                    with open(json_file, 'r') as f:
                        recipe = json.load(f)
                        recipes.append(recipe)
                except (json.JSONDecodeError, IOError):
                    # Skip unparseable files gracefully
                    continue

        # Sort by updated timestamp, newest first
        recipes.sort(key=lambda r: r.get('updated', 0), reverse=True)
        return recipes

    def get(self, recipe_id: int) -> dict | None:
        """Get a recipe by ID."""
        if not self.base_dir.exists():
            return None

        # Scan all subfolders for the recipe
        for group_dir in self.base_dir.iterdir():
            if not group_dir.is_dir():
                continue

            json_file = group_dir / f'{recipe_id}.json'
            if json_file.exists():
                try:
                    with open(json_file, 'r') as f:
                        return json.load(f)
                except (json.JSONDecodeError, IOError):
                    return None

        return None

    def save(self, recipe: dict) -> dict:
        """Save a new recipe and return the stored dict with id and updated."""
        # Assign id if not present
        if 'id' not in recipe:
            recipe['id'] = int(time.time() * 1000)

        # Set updated timestamp
        recipe['updated'] = int(time.time())

        # Get the group (with sanitation)
        group = recipe.get('group', 'Meads')
        safe_group = self._safe(group)

        # Create group folder
        group_dir = self.base_dir / safe_group
        group_dir.mkdir(parents=True, exist_ok=True)

        # Write to file
        json_file = group_dir / f"{recipe['id']}.json"
        with open(json_file, 'w') as f:
            json.dump(recipe, f, indent=2)

        return recipe

    def update(self, recipe_id: int, recipe: dict) -> dict | None:
        """Update a recipe by ID, handling group changes."""
        # Find the existing recipe
        existing = self.get(recipe_id)
        if existing is None:
            return None

        # Capture old group before updating
        old_group = existing.get('group', 'Meads')

        # Update the recipe dict with the new values
        existing.update(recipe)
        existing['id'] = recipe_id
        existing['updated'] = int(time.time())

        new_group = existing.get('group', 'Meads')

        # If group changed, delete old file
        if old_group != new_group:
            old_safe_group = self._safe(old_group)
            old_json_file = self.base_dir / old_safe_group / f'{recipe_id}.json'
            if old_json_file.exists():
                try:
                    old_json_file.unlink()
                except OSError:
                    pass

        # Save to new group folder
        safe_group = self._safe(new_group)
        group_dir = self.base_dir / safe_group
        group_dir.mkdir(parents=True, exist_ok=True)

        json_file = group_dir / f'{recipe_id}.json'
        with open(json_file, 'w') as f:
            json.dump(existing, f, indent=2)

        return existing

    def delete(self, recipe_id: int) -> bool:
        """Delete a recipe by ID."""
        if not self.base_dir.exists():
            return False

        # Scan all subfolders for the recipe
        for group_dir in self.base_dir.iterdir():
            if not group_dir.is_dir():
                continue

            json_file = group_dir / f'{recipe_id}.json'
            if json_file.exists():
                try:
                    json_file.unlink()
                    return True
                except OSError:
                    return False

        return False
