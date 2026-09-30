"""Routes for the ingredient taxonomy."""

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db
from ..models import Ingredient, Suggestion
from ..taxonomy import ancestor_ids, descendant_ids, suggest_ingredient

router = APIRouter(prefix="/api/ingredients", tags=["ingredients"])


@router.get("", response_model=list[Ingredient])
def list_ingredients(db: sqlite3.Connection = Depends(get_db)):
    """The whole tree, flat."""
    rows = db.execute(
        "SELECT id, name, parent_id, assumed_on_hand FROM ingredient ORDER BY name"
    ).fetchall()
    return [dict(row) for row in rows]


@router.get("/suggest", response_model=Suggestion)
def suggest(product_name: str, db: sqlite3.Connection = Depends(get_db)):
    """Guess a category from a product name."""
    ingredient_id = suggest_ingredient(db, product_name)
    name = None
    if ingredient_id:
        row = db.execute(
            "SELECT name FROM ingredient WHERE id = ?", (ingredient_id,)
        ).fetchone()
        name = row["name"] if row else None
    return {
        "product_name": product_name,
        "ingredient_id": ingredient_id,
        "ingredient_name": name,
    }


@router.get("/{ingredient_id}/subtree", response_model=list[str])
def subtree(ingredient_id: str, db: sqlite3.Connection = Depends(get_db)):
    """Every category that would satisfy a requirement for this one."""
    ids = descendant_ids(db, ingredient_id)
    if not ids:
        raise HTTPException(status_code=404, detail=f"No ingredient '{ingredient_id}'")
    return ids


@router.get("/{ingredient_id}/ancestors", response_model=list[str])
def ancestors(ingredient_id: str, db: sqlite3.Connection = Depends(get_db)):
    """The chain from this category up to its root."""
    ids = ancestor_ids(db, ingredient_id)
    if not ids:
        raise HTTPException(status_code=404, detail=f"No ingredient '{ingredient_id}'")
    return ids
