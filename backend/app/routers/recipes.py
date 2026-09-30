"""Routes for recipes -- the payoff of everything in taxonomy.py."""

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status

from ..db import get_db
from ..models import Recipe, RecipeHidden, RecipeIn, RecipeList, ShoppingSuggestion
from ..recipe_store import RecipeError, create_recipe, set_hidden, update_recipe
from ..recipes import get_recipe, load_recipes, random_makeable, shopping_list

router = APIRouter(prefix="/api/recipes", tags=["recipes"])


def _inventory_count(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) AS c FROM bottle").fetchone()["c"]


@router.get("", response_model=RecipeList)
def list_recipes(
    kind: Literal["cocktail", "shot", "all"] = "cocktail",
    hidden: Literal["exclude", "include", "only"] = "exclude",
    db: sqlite3.Connection = Depends(get_db),
):
    """Recipes sorted makeable first, then most common, then A to Z."""
    recipes = load_recipes(db, kind=None if kind == "all" else kind, hidden=hidden)
    return {
        "inventory_count": _inventory_count(db),
        "makeable_count": sum(1 for r in recipes if r["status"] == "makeable"),
        "one_short_count": sum(1 for r in recipes if r["status"] == "one_short"),
        "recipes": recipes,
    }


@router.post("", response_model=Recipe, status_code=status.HTTP_201_CREATED)
def add_recipe(payload: RecipeIn, db: sqlite3.Connection = Depends(get_db)):
    """A new recipe, written on your phone."""
    try:
        recipe_id = create_recipe(db, payload.model_dump())
    except RecipeError as err:
        raise HTTPException(status_code=400, detail=str(err))
    return get_recipe(db, recipe_id)


@router.get("/random", response_model=Recipe)
def pick_for_me(db: sqlite3.Connection = Depends(get_db)):
    """One cocktail you can actually make, chosen at random."""
    recipe = random_makeable(db)
    if recipe is None:
        raise HTTPException(
            status_code=404,
            detail="Nothing on the shelf makes a complete drink yet.",
        )
    return recipe


@router.get("/shopping-list", response_model=list[ShoppingSuggestion])
def suggest_purchases(limit: int = 5, db: sqlite3.Connection = Depends(get_db)):
    """Bottles ranked by how many new drinks each would unlock."""
    return shopping_list(db, limit=limit)


@router.get("/{recipe_id}", response_model=Recipe)
def recipe_detail(recipe_id: str, db: sqlite3.Connection = Depends(get_db)):
    """One recipe, with every line marked against your shelf."""
    recipe = get_recipe(db, recipe_id)
    if recipe is None:
        raise HTTPException(status_code=404, detail=f"No recipe '{recipe_id}'")
    return recipe


@router.put("/{recipe_id}", response_model=Recipe)
def edit_recipe(recipe_id: str, payload: RecipeIn, db: sqlite3.Connection = Depends(get_db)):
    """Replace a recipe with your edited version."""
    try:
        found = update_recipe(db, recipe_id, payload.model_dump())
    except RecipeError as err:
        raise HTTPException(status_code=400, detail=str(err))
    if not found:
        raise HTTPException(status_code=404, detail=f"No recipe '{recipe_id}'")
    return get_recipe(db, recipe_id)


@router.patch("/{recipe_id}", response_model=Recipe)
def hide_recipe(recipe_id: str, payload: RecipeHidden, db: sqlite3.Connection = Depends(get_db)):
    """Hide a recipe from every list, or bring it back."""
    if not set_hidden(db, recipe_id, payload.hidden):
        raise HTTPException(status_code=404, detail=f"No recipe '{recipe_id}'")
    return get_recipe(db, recipe_id)
