import json
import time

from app.models import Recipe
from app.services.recipe_store import RecipeStore


class TestRecipeStoreBasics:
    """Test basic RecipeStore functionality."""

    def test_groups_includes_defaults(self, recipe_store):
        """groups() contains all DEFAULT_GROUPS."""
        groups = recipe_store.groups()
        for default_group in RecipeStore.DEFAULT_GROUPS:
            assert default_group in groups

    def test_save_assigns_id_and_updated(self, recipe_store):
        """Saving a Recipe without id returns one with an int id and int updated."""
        recipe_input = Recipe(
            name="Test Recipe",
            group="Meads",
            items=["item1", "item2"],
            model="test_model",
            notes="test notes",
        )

        result = recipe_store.save(recipe_input)

        # Check that id was assigned
        assert isinstance(result.id, int)
        assert result.id > 0

        # Check that updated was set
        assert isinstance(result.updated, int)
        assert result.updated > 0

        # Check that the file exists on disk
        group_dir = recipe_store.base_dir / "Meads"
        json_file = group_dir / f"{result.id}.json"
        assert json_file.exists()

        # Verify file contents
        with open(json_file, "r") as f:
            stored = json.load(f)
        assert stored["id"] == result.id
        assert stored["updated"] == result.updated

    def test_get_roundtrips(self, recipe_store):
        """Save then get(id) returns an equivalent recipe."""
        recipe_input = Recipe(
            name="Honey Wine",
            group="Meads",
            items=["honey", "water", "yeast"],
            model="traditional",
            notes="sweet and golden",
        )

        saved = recipe_store.save(recipe_input)
        recipe_id = saved.id

        retrieved = recipe_store.get(recipe_id)

        assert retrieved is not None
        assert retrieved.name == "Honey Wine"
        assert retrieved.items == ["honey", "water", "yeast"]
        assert retrieved.group == "Meads"
        assert retrieved.model == "traditional"
        assert retrieved.notes == "sweet and golden"
        assert retrieved.id == recipe_id

    def test_list_newest_first(self, recipe_store):
        """list() is sorted by 'updated' descending (newest first)."""
        # Create three recipes with explicit ids to guarantee distinct ids
        # and spacing in time to ensure distinct updated timestamps
        recipe1 = Recipe(
            id=1000,
            name="Recipe 1",
            group="Meads",
            items=["a"],
            model="m1",
            notes="first",
        )
        recipe_store.save(recipe1)
        time.sleep(1.0)  # Ensure distinct timestamps

        recipe2 = Recipe(
            id=2000,
            name="Recipe 2",
            group="Weeknight meals",
            items=["b"],
            model="m2",
            notes="second",
        )
        recipe_store.save(recipe2)
        time.sleep(1.0)

        recipe3 = Recipe(
            id=3000,
            name="Recipe 3",
            group="Leftovers",
            items=["c"],
            model="m3",
            notes="third",
        )
        recipe_store.save(recipe3)

        recipes = recipe_store.list()

        # Assert all three are present
        recipe_ids = [r.id for r in recipes]
        assert 1000 in recipe_ids
        assert 2000 in recipe_ids
        assert 3000 in recipe_ids

        # Assert newest (recipe3) is first
        assert recipes[0].id == 3000

        # Assert ordering is descending by updated
        for i in range(len(recipes) - 1):
            assert recipes[i].updated >= recipes[i + 1].updated

    def test_update_in_place(self, recipe_store):
        """save, then update(id, {...changed...}) keeps same id and reflects changes."""
        recipe_input = Recipe(
            name="Original Name",
            group="Meads",
            items=["item1"],
            model="model1",
            notes="original notes",
        )

        saved = recipe_store.save(recipe_input)
        recipe_id = saved.id
        original_updated = saved.updated

        # Wait a moment to ensure updated timestamp changes
        time.sleep(0.01)

        # Update with changed name and notes (dict patch)
        update_dict = {
            "name": "Updated Name",
            "notes": "updated notes",
        }
        updated = recipe_store.update(recipe_id, update_dict)

        assert updated is not None
        assert updated.id == recipe_id
        assert updated.name == "Updated Name"
        assert updated.notes == "updated notes"
        assert updated.group == "Meads"  # Group unchanged
        assert updated.items == ["item1"]  # Items unchanged
        assert updated.updated >= original_updated

        # Verify via get()
        retrieved = recipe_store.get(recipe_id)
        assert retrieved.name == "Updated Name"
        assert retrieved.notes == "updated notes"
        assert retrieved.id == recipe_id

    def test_update_group_move(self, recipe_store):
        """Update with group change moves file and removes old one."""
        recipe_input = Recipe(
            name="Mead to Experiment",
            group="Meads",
            items=["honey", "water"],
            model="test",
            notes="moving groups",
        )

        saved = recipe_store.save(recipe_input)
        recipe_id = saved.id

        # Verify it's in Meads folder
        old_file = recipe_store.base_dir / "Meads" / f"{recipe_id}.json"
        assert old_file.exists()

        # Update to Experiments group
        updated = recipe_store.update(recipe_id, {"group": "Experiments"})

        assert updated is not None
        assert updated.group == "Experiments"

        # Old file should be gone
        assert not old_file.exists()

        # New file should exist in Experiments
        new_file = recipe_store.base_dir / "Experiments" / f"{recipe_id}.json"
        assert new_file.exists()

        # Get should still work and return the new group
        retrieved = recipe_store.get(recipe_id)
        assert retrieved.group == "Experiments"

        # list() should show it in the new group
        recipes = recipe_store.list()
        matching = [r for r in recipes if r.id == recipe_id]
        assert len(matching) == 1
        assert matching[0].group == "Experiments"

    def test_delete(self, recipe_store):
        """delete(id) returns True, get() is None, list() no longer contains it."""
        recipe_input = Recipe(
            name="To Delete",
            group="Meads",
            items=["x"],
            model="test",
            notes="doomed",
        )

        saved = recipe_store.save(recipe_input)
        recipe_id = saved.id

        # Verify it exists
        assert recipe_store.get(recipe_id) is not None

        # Delete it
        result = recipe_store.delete(recipe_id)
        assert result is True

        # Verify it's gone
        assert recipe_store.get(recipe_id) is None

        # Verify it's not in list
        recipes = recipe_store.list()
        assert recipe_id not in [r.id for r in recipes]

    def test_delete_missing_id_returns_false(self, recipe_store):
        """delete(missing_id) returns False."""
        result = recipe_store.delete(99999)
        assert result is False

    def test_bad_json_skipped(self, recipe_store):
        """list() ignores unparseable JSON files."""
        # Create a group folder and add a bad JSON file
        group_dir = recipe_store.base_dir / "Meads"
        group_dir.mkdir(parents=True, exist_ok=True)

        bad_file = group_dir / "bad_recipe.json"
        with open(bad_file, "w") as f:
            f.write("{this is not valid json")

        # Save a good recipe
        recipe_input = Recipe(
            name="Good Recipe",
            group="Meads",
            items=["a"],
            model="test",
            notes="valid",
        )
        recipe_store.save(recipe_input)

        # list() should not raise and should skip the bad file
        recipes = recipe_store.list()
        assert len(recipes) == 1
        assert recipes[0].name == "Good Recipe"

    def test_safe_group_name(self, recipe_store):
        """Recipes with odd characters in group name are sanitized and retrievable."""
        # Use a group name with special characters
        recipe_input = Recipe(
            name="Special Group Recipe",
            group="Group!@#$%^&*()With Weird Chars",
            items=["x"],
            model="test",
            notes="weird group",
        )

        saved = recipe_store.save(recipe_input)
        recipe_id = saved.id

        # The stored group should be preserved on the recipe
        assert saved.group == "Group!@#$%^&*()With Weird Chars"

        # But it should still be retrievable
        retrieved = recipe_store.get(recipe_id)
        assert retrieved is not None
        assert retrieved.id == recipe_id
        assert retrieved.name == "Special Group Recipe"

        # Verify it appears in list()
        recipes = recipe_store.list()
        matching = [r for r in recipes if r.id == recipe_id]
        assert len(matching) == 1


class TestRecipeStoreEdgeCases:
    """Test edge cases and error handling."""

    def test_get_nonexistent_returns_none(self, recipe_store):
        """get() on a nonexistent id returns None."""
        result = recipe_store.get(99999)
        assert result is None

    def test_update_nonexistent_returns_none(self, recipe_store):
        """update() on a nonexistent id returns None."""
        result = recipe_store.update(99999, {"name": "new"})
        assert result is None

    def test_empty_list_is_empty(self, recipe_store):
        """list() on empty store returns empty list."""
        recipes = recipe_store.list()
        assert recipes == []

    def test_recipe_preserves_all_fields(self, recipe_store):
        """Saved recipe preserves all provided fields."""
        recipe_input = Recipe(
            name="Complex Recipe",
            group="Weeknight meals",
            items=["item1", "item2", "item3"],
            model="advanced_model",
            notes="This is a complex recipe with many notes",
        )

        saved = recipe_store.save(recipe_input)

        # All fields should be present
        assert saved.name == recipe_input.name
        assert saved.group == recipe_input.group
        assert saved.items == recipe_input.items
        assert saved.model == recipe_input.model
        assert saved.notes == recipe_input.notes
